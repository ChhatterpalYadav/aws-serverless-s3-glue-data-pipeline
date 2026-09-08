import json


def parse_s3_event_from_sns(sns_record: dict) -> dict:
    """
    Shared by every Lambda subscribed to S3EventTopic.

    SNS wraps the real S3 event as a JSON STRING inside
    sns_record["Sns"]["Message"] - this must be json.loads()'d before
    any S3 fields (bucket, key, version) can be read from it.
    """
    message_str = sns_record["Sns"]["Message"]
    return json.loads(message_str)
