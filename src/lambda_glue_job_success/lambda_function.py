import logging
import time

import boto3

from utils.config import Config
from utils.dynamodb_utils import FileConfigRepository
from utils.response import LambdaResponse

logger = logging.getLogger()
logger.setLevel(logging.INFO)

glue_client = boto3.client("glue", region_name=Config.AWS_REGION)
athena_client = boto3.client("athena", region_name=Config.AWS_REGION)
repository = FileConfigRepository()

FILE_TYPE_TO_CRAWLER = {
    "text": "TextFilesCrawler",
    "csv": "CSVFilesCrawler",
    "json": "JSONFilesCrawler",
}

MAX_CRAWLER_WAIT_SECONDS = 280
CRAWLER_POLL_INTERVAL_SECONDS = 10


def _file_type_from_job_name(job_name: str) -> str:
    """Our Glue job names are '<type>_<sizetier>', e.g. 'csv_0_5kb' -> 'csv'."""
    return job_name.split("_")[0]


def _start_crawler_if_not_running(crawler_name: str):
    crawler = glue_client.get_crawler(Name=crawler_name)["Crawler"]
    if crawler["State"] == "READY":
        glue_client.start_crawler(Name=crawler_name)
        logger.info(f"Started crawler '{crawler_name}'")
    else:
        logger.info(f"Crawler '{crawler_name}' already {crawler['State']}, not starting again")


def _wait_for_crawler_ready(crawler_name: str) -> bool:
    """
    Crawlers run asynchronously - we poll its state until it returns
    to READY (finished), or give up after MAX_CRAWLER_WAIT_SECONDS so
    this Lambda doesn't run forever. This is the "crawler can wait for
    5 mins if state is not ready" behavior from your assignment.
    """
    waited_seconds = 0
    while waited_seconds < MAX_CRAWLER_WAIT_SECONDS:
        state = glue_client.get_crawler(Name=crawler_name)["Crawler"]["State"]
        if state == "READY":
            return True
        time.sleep(CRAWLER_POLL_INTERVAL_SECONDS)
        waited_seconds += CRAWLER_POLL_INTERVAL_SECONDS

    logger.warning(f"Crawler '{crawler_name}' did not finish within {MAX_CRAWLER_WAIT_SECONDS}s")
    return False


def _find_table_for_file_type(database_name: str, file_type: str):
    """
    Finds the Glue Catalog table the crawler created for this file
    type, by checking which table's S3 location contains the matching
    folder (e.g. '/csv/'). Avoids hardcoding an assumed table name,
    since Glue's auto-naming behavior can vary.
    """
    tables = glue_client.get_tables(DatabaseName=database_name)["TableList"]
    for table in tables:
        location = table.get("StorageDescriptor", {}).get("Location", "")
        if f"/{file_type}/" in location:
            return table["Name"]
    return None


def handler(event, context):
    """
    Triggered by the EventBridge rule watching for Glue Job State
    Change events with state=SUCCEEDED, across all 9 job names.
    """
    detail = event.get("detail", {})
    job_name = detail.get("jobName")
    job_run_id = detail.get("jobRunId")

    logger.info(f"Glue job '{job_name}' (run {job_run_id}) succeeded")

    file_type = _file_type_from_job_name(job_name)
    crawler_name = FILE_TYPE_TO_CRAWLER.get(file_type)

    if not crawler_name:
        return LambdaResponse.error(f"No crawler mapped for file type '{file_type}' (job '{job_name}')")

    _start_crawler_if_not_running(crawler_name)
    crawler_finished = _wait_for_crawler_ready(crawler_name)

    if not crawler_finished:
        return LambdaResponse.error(f"Crawler '{crawler_name}' did not finish in time")

    table_name = _find_table_for_file_type(Config.GLUE_DATABASE_NAME, file_type)
    if not table_name:
        return LambdaResponse.error(f"No table found for file type '{file_type}' in database '{Config.GLUE_DATABASE_NAME}'")

    query = f'SELECT * FROM "{Config.GLUE_DATABASE_NAME}"."{table_name}"'
    query_execution = athena_client.start_query_execution(
        QueryString=query,
        QueryExecutionContext={"Database": Config.GLUE_DATABASE_NAME},
        ResultConfiguration={"OutputLocation": f"s3://{Config.ATHENA_OUTPUT_BUCKET_NAME}/"},
    )
    query_execution_id = query_execution["QueryExecutionId"]
    logger.info(f"Started Athena query '{query_execution_id}' against table '{table_name}'")

    # Best-effort: mark the underlying file's DynamoDB record PROCESSED.
    config_item = repository.find_by_job_run_id(job_run_id)
    if config_item:
        repository.update_status(config_item["object_key"], config_item["version_id"], "PROCESSED")

    return LambdaResponse.success(
        "Crawler and Athena query complete",
        {"crawler_name": crawler_name, "table_name": table_name, "query_execution_id": query_execution_id},
    )
