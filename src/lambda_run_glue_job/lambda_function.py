import logging
import time

import boto3

from utils.config import Config
from utils.dynamodb_utils import FileConfigRepository
from utils.response import LambdaResponse
from utils.sns_utils import parse_s3_event_from_sns

logger = logging.getLogger()
logger.setLevel(logging.INFO)

glue_client = boto3.client("glue", region_name=Config.AWS_REGION)
repository = FileConfigRepository()


CONTENT_TYPE_TO_FILE_TYPE = {
    "text/plain": "text",
    "application/json": "json",
    "text/csv": "csv",
}

EXTENSION_TO_FILE_TYPE = {
    "txt": "text",
    "json": "json",
    "csv": "csv",
}


def _determine_file_type(content_type: str, object_key: str) -> str:
    
    file_type = CONTENT_TYPE_TO_FILE_TYPE.get(content_type)
    if file_type:
        return file_type

    extension = object_key.lower().rsplit(".", 1)[-1]
    return EXTENSION_TO_FILE_TYPE.get(extension, "unknown")


def _determine_size_tier(file_size) -> str:
    """file_size arrives from DynamoDB as a Decimal - int() handles that fine."""
    file_size = int(file_size)

    if file_size < 5 * 1024:
        return "0_5kb"
    if file_size < 10 * 1024:
        return "5_10kb"
    return "above_10kb"


def _get_config_with_retry(object_key: str, version_id: str, max_attempts: int = 5, delay_seconds: float = 1.0) -> dict:
    
    for attempt in range(1, max_attempts + 1):
        config_item = repository.get_config(object_key, version_id)
        if config_item:
            return config_item

        logger.info(f"Config for '{object_key}' not ready yet (attempt {attempt}/{max_attempts}), waiting...")
        time.sleep(delay_seconds)

    raise RuntimeError(f"Config for '{object_key}' (version {version_id}) never appeared in DynamoDB")


def handler(event, context):
    
    started = []
    failed = []

    for sns_record in event.get("Records", []):
        try:
            s3_event = parse_s3_event_from_sns(sns_record)

            for s3_record in s3_event.get("Records", []):
                bucket_name = s3_record["s3"]["bucket"]["name"]
                object_key = s3_record["s3"]["object"]["key"]
                version_id = s3_record["s3"]["object"].get("versionId", "null")

                config_item = _get_config_with_retry(object_key, version_id)

                file_type = _determine_file_type(config_item.get("content_type", ""), object_key)
                size_tier = _determine_size_tier(config_item["file_size"])

                if file_type == "unknown":
                    raise ValueError(f"Could not determine file type for '{object_key}'")

                glue_job_name = f"{file_type}_{size_tier}"

                response = glue_client.start_job_run(
                    JobName=glue_job_name,
                    Arguments={
                        "--SOURCE_BUCKET": bucket_name,
                        "--SOURCE_KEY": object_key,
                        "--SOURCE_VERSION_ID": version_id,
                    },
                )

                job_run_id = response["JobRunId"]

                repository.update_status(
                    object_key, version_id, "GLUE_JOB_STARTED",
                    extra_attributes={"glue_job_name": glue_job_name, "glue_job_run_id": job_run_id},
                )

                started.append({"object_key": object_key, "glue_job_name": glue_job_name, "job_run_id": job_run_id})
                logger.info(f"Started Glue job '{glue_job_name}' for '{object_key}' (run id {job_run_id})")

        except Exception as exc:
            logger.error(f"Failed to process SNS record: {exc}", exc_info=True)
            failed.append(str(exc))

    if failed and not started:
        return LambdaResponse.error(f"All records failed: {failed}")

    return LambdaResponse.success("Glue job dispatch complete", {"started": started, "failed": failed})
