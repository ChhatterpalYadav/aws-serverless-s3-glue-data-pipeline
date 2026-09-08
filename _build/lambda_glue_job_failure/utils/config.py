import os


class Config:
    """
    Centralizes all environment-variable driven settings in ONE place.

    Why this exists: without it, every Lambda would scatter
    os.environ.get(...) calls across its own file. If we ever rename
    an env var, we'd have to hunt through every Lambda to fix it.
    With this class, only this file changes.
    """

    AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")
    DYNAMODB_TABLE_NAME = os.environ.get("DYNAMODB_TABLE_NAME", "DNBAssignment3FileConfig")
    GLUE_DATABASE_NAME = os.environ.get("GLUE_DATABASE_NAME", "dnb_assignment3_database")
    ATHENA_OUTPUT_BUCKET_NAME = os.environ.get("ATHENA_OUTPUT_BUCKET_NAME", "")
    FAILURE_TOPIC_ARN = os.environ.get("FAILURE_TOPIC_ARN", "")
