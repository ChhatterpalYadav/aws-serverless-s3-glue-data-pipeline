import sys

import boto3
from awsglue.utils import getResolvedOptions

s3_client = boto3.client("s3")

# ASSUMPTION - verify against your actual assignment materials:
# a hardcoded country -> ISO 3166-1 alpha-2 code mapping. Glue jobs
# run in an isolated environment without general internet access, so
# we keep this as a plain Python dict rather than depending on an
# external library or a live lookup. Extend this list as needed -
# anything not found falls back to UNKNOWN_COUNTRY_CODE.
COUNTRY_TO_CODE = {
    "india": "IN",
    "united states": "US",
    "united kingdom": "GB",
    "canada": "CA",
    "australia": "AU",
    "germany": "DE",
    "france": "FR",
    "japan": "JP",
    "china": "CN",
    "brazil": "BR",
    "south africa": "ZA",
    "italy": "IT",
    "spain": "ES",
    "russia": "RU",
    "mexico": "MX",
    "singapore": "SG",
    "united arab emirates": "AE",
    "netherlands": "NL",
    "new zealand": "NZ",
    "south korea": "KR",
}

UNKNOWN_COUNTRY_CODE = "XX"


def get_job_arguments(job_specific_args=None):
    """
    Every one of our Glue jobs needs to know WHICH file to process
    (passed in by LambdaRunGlueJob) and WHERE to write the result.
    getResolvedOptions is AWS Glue's own helper for reading the
    --ArgumentName style arguments a job was started with - it's
    Glue's equivalent of Python's argparse for a regular script.
    """
    required_args = ["SOURCE_BUCKET", "SOURCE_KEY", "SOURCE_VERSION_ID", "OUTPUT_BUCKET"]
    if job_specific_args:
        required_args += job_specific_args
    return getResolvedOptions(sys.argv, required_args)


def read_source_object(bucket: str, key: str, version_id: str) -> bytes:
    """Downloads the exact file (and exact S3 version) that triggered this job."""
    response = s3_client.get_object(Bucket=bucket, Key=key, VersionId=version_id)
    return response["Body"].read()


def enrich_with_country_code(record: dict) -> dict:
    """
    Adds the 4th output field, country_code, based on the 3rd input
    field, country - this is the actual data transformation your
    assignment specifies for every file type.
    """
    country_name = record.get("country", "").strip().lower()
    record["country_code"] = COUNTRY_TO_CODE.get(country_name, UNKNOWN_COUNTRY_CODE)
    return record


def write_output_object(bucket: str, key: str, content: bytes):
    """Writes the transformed output into the crawler bucket, where the Glue Crawlers will later discover it."""
    s3_client.put_object(Bucket=bucket, Key=key, Body=content)
