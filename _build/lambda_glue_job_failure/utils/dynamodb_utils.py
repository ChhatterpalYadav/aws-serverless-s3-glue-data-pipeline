import boto3

from utils.config import Config


class FileConfigRepository:
    """
    Wraps ALL DynamoDB access for the file-config table behind one
    small class, instead of scattering boto3 calls across every
    Lambda. This is the "repository pattern" - Lambdas call
    save_config()/get_config() and don't need to know DynamoDB even
    exists underneath. If we ever swapped DynamoDB for another
    database, only this file would need to change.
    """

    def __init__(self, table_name: str = None, region: str = None):
        # boto3.resource (not .client) gives a higher-level, more
        # Pythonic interface for DynamoDB - e.g. put_item() accepts
        # plain Python dicts instead of DynamoDB's verbose
        # {"S": "value"} / {"N": "5"} type-wrapped format.
        dynamodb = boto3.resource("dynamodb", region_name=region or Config.AWS_REGION)
        self._table = dynamodb.Table(table_name or Config.DYNAMODB_TABLE_NAME)

    def save_config(self, item: dict) -> None:
        """
        Writes (or overwrites) one file's config record.

        put_item is naturally idempotent for a given (object_key,
        version_id) pair: if this Lambda gets retried for the same
        event - which SNS/Lambda can do on transient failures - we
        simply re-write the same item. No duplicates, no corrupted
        state. This is a key piece of the "resiliency" requirement.
        """
        self._table.put_item(Item=item)

    def get_config(self, object_key: str, version_id: str) -> dict | None:
        """
        Fetches one file's config by its composite key.
        Returns None (not an exception) when nothing is found, so
        callers can explicitly handle "not processed yet" instead of
        crashing on a missing key.
        """
        response = self._table.get_item(
            Key={"object_key": object_key, "version_id": version_id}
        )
        return response.get("Item")

    def update_status(self, object_key: str, version_id: str, status: str, extra_attributes: dict = None) -> None:
        """
        Updates just the status field (and optionally a few extra
        fields) WITHOUT rewriting the whole item. Used to track a
        file's progress through the pipeline over time:
        PENDING -> GLUE_JOB_STARTED -> PROCESSED / FAILED.

        Note: "status" is a DynamoDB RESERVED WORD (it's part of
        DynamoDB's own query language), so it can't be used directly
        in an UpdateExpression. We must alias it with a placeholder
        (#status) via ExpressionAttributeNames - this is a DynamoDB
        quirk you'll hit again with other common words like "name",
        "size", "data", "date".
        """
        update_expression_parts = ["#status = :status"]
        expression_attribute_names = {"#status": "status"}
        expression_attribute_values = {":status": status}

        if extra_attributes:
            for key, value in extra_attributes.items():
                update_expression_parts.append(f"#{key} = :{key}")
                expression_attribute_names[f"#{key}"] = key
                expression_attribute_values[f":{key}"] = value

        self._table.update_item(
            Key={"object_key": object_key, "version_id": version_id},
            UpdateExpression="SET " + ", ".join(update_expression_parts),
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
        )

    def find_by_job_run_id(self, job_run_id: str) -> dict | None:
        """
        Best-effort lookup of a file's config record by the Glue job
        run id that was processing it. Uses a table SCAN (checks every
        item) rather than a fast key lookup, because job_run_id isn't
        part of our key schema. Fine at this project's scale - for a
        high-volume production table, you'd add a Global Secondary
        Index on glue_job_run_id instead of scanning.
        """
        response = self._table.scan(
            FilterExpression="glue_job_run_id = :job_run_id",
            ExpressionAttributeValues={":job_run_id": job_run_id},
        )
        items = response.get("Items", [])
        return items[0] if items else None
