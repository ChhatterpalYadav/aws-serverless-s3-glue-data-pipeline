import json
import logging
from decimal import Decimal

import boto3

from utils.config import Config
from utils.dynamodb_utils import FileConfigRepository
from utils.response import LambdaResponse

logger = logging.getLogger()
logger.setLevel(logging.INFO)

s3_client = boto3.client("s3", region_name=Config.AWS_REGION)
repository = FileConfigRepository()


def _parse_s3_event_from_sns(sns_record: dict) -> dict:
    
    message_str = sns_record["Sns"]["Message"]
    return json.loads(message_str)


def _fetch_extra_metadata(bucket_name: str, object_key: str, version_id: str) -> dict:
    
    head = s3_client.head_object(Bucket=bucket_name, Key=object_key, VersionId=version_id)
    tagging = s3_client.get_object_tagging(Bucket=bucket_name, Key=object_key, VersionId=version_id)

    tags = {tag["Key"]: tag["Value"] for tag in tagging.get("TagSet", [])}

    return {
        "content_type": head.get("ContentType", "unknown"),
        "last_modified_date": head["LastModified"].isoformat(),
        "tags": tags,
    }


def _build_config_item(s3_record: dict, extra_metadata: dict) -> dict:
    
    bucket_name = s3_record["s3"]["bucket"]["name"]
    object_key = s3_record["s3"]["object"]["key"]
    version_id = s3_record["s3"]["object"].get("versionId", "null")
    file_size = s3_record["s3"]["object"]["size"]
    etag = s3_record["s3"]["object"]["eTag"]
    event_time = s3_record["eventTime"]

    return {
        "object_key": object_key,
        "version_id": version_id,
        "bucket_name": bucket_name,
        "file_size": Decimal(str(file_size)),
        "etag": etag,
        "event_time": event_time,
        "status": "PENDING",
        **extra_metadata,
    }


def handler(event, context):
    
    processed = []
    failed = []

    for sns_record in event.get("Records", []):
        try:
            s3_event = _parse_s3_event_from_sns(sns_record)

            for s3_record in s3_event.get("Records", []):
                bucket_name = s3_record["s3"]["bucket"]["name"]
                object_key = s3_record["s3"]["object"]["key"]
                version_id = s3_record["s3"]["object"].get("versionId", "null")

                extra_metadata = _fetch_extra_metadata(bucket_name, object_key, version_id)
                config_item = _build_config_item(s3_record, extra_metadata)

                repository.save_config(config_item)
                processed.append(object_key)
                logger.info(f"Saved config for '{object_key}' (version {version_id})")

        except Exception as exc:
            logger.error(f"Failed to process SNS record: {exc}", exc_info=True)
            failed.append(str(exc))

    if failed and not processed:
        return LambdaResponse.error(f"All records failed: {failed}")

    return LambdaResponse.success("Config save complete", {"processed": processed, "failed": failed})
