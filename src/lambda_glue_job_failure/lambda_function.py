import logging

import boto3

from utils.config import Config
from utils.dynamodb_utils import FileConfigRepository
from utils.response import LambdaResponse

logger = logging.getLogger()
logger.setLevel(logging.INFO)

sns_client = boto3.client("sns", region_name=Config.AWS_REGION)
repository = FileConfigRepository()


def handler(event, context):

    detail = event.get("detail", {})
    job_name = detail.get("jobName")
    job_run_id = detail.get("jobRunId")
    error_message = detail.get("message", "No error message provided by Glue")

    logger.error(f"Glue job '{job_name}' (run {job_run_id}) FAILED: {error_message}")

    config_item = repository.find_by_job_run_id(job_run_id)
    if config_item:
        repository.update_status(config_item["object_key"], config_item["version_id"], "FAILED")

    message = (
        f"Glue job FAILED\n\n"
        f"Job name: {job_name}\n"
        f"Job run ID: {job_run_id}\n"
        f"Error: {error_message}\n"
    )

    sns_client.publish(
        TopicArn=Config.FAILURE_TOPIC_ARN,
        Subject=f"Pipeline failure: {job_name}",
        Message=message,
    )

    return LambdaResponse.success("Failure notification sent", {"job_name": job_name, "job_run_id": job_run_id})
