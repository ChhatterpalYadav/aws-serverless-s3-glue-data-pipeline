import os
import shutil
import zipfile

import boto3

AWS_REGION = os.environ.get("AWS_REGION", "ap-south-1")

sts_client = boto3.client("sts", region_name=AWS_REGION)
ACCOUNT_ID = sts_client.get_caller_identity()["Account"]
CODE_BUCKET_NAME = f"dnb-assignment3-code-v2-{ACCOUNT_ID}"

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD_DIR = os.path.join(PROJECT_ROOT, "_build")


def ensure_code_bucket_exists():
    
    s3_client = boto3.client("s3", region_name=AWS_REGION)
    existing_buckets = [b["Name"] for b in s3_client.list_buckets()["Buckets"]]

    if CODE_BUCKET_NAME in existing_buckets:
        print(f"Code bucket '{CODE_BUCKET_NAME}' already exists.")
        return

    print(f"Creating code bucket '{CODE_BUCKET_NAME}'...")
    if AWS_REGION == "us-east-1":
        # us-east-1 is a special case in the S3 API: it does NOT
        # accept a LocationConstraint - every other region requires one.
        s3_client.create_bucket(Bucket=CODE_BUCKET_NAME)
    else:
        s3_client.create_bucket(
            Bucket=CODE_BUCKET_NAME,
            CreateBucketConfiguration={"LocationConstraint": AWS_REGION},
        )


def build_zip_for_lambda(lambda_folder_name: str) -> str:
    
    lambda_src_dir = os.path.join(PROJECT_ROOT, "src", lambda_folder_name)
    zip_staging_dir = os.path.join(BUILD_DIR, lambda_folder_name)

    if os.path.exists(zip_staging_dir):
        shutil.rmtree(zip_staging_dir)
    os.makedirs(zip_staging_dir)

    shutil.copy(
        os.path.join(lambda_src_dir, "lambda_function.py"),
        os.path.join(zip_staging_dir, "lambda_function.py"),
    )
    shutil.copytree(
        os.path.join(PROJECT_ROOT, "utils"),
        os.path.join(zip_staging_dir, "utils"),
    )

    zip_path = os.path.join(BUILD_DIR, f"{lambda_folder_name}.zip")
    if os.path.exists(zip_path):
        os.remove(zip_path)

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for root, _dirs, files in os.walk(zip_staging_dir):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                arcname = os.path.relpath(file_path, zip_staging_dir)
                zip_file.write(file_path, arcname)

    print(f"Built {zip_path}")
    return zip_path


def upload_zip(zip_path: str, s3_key: str):
    s3_client = boto3.client("s3", region_name=AWS_REGION)
    s3_client.upload_file(zip_path, CODE_BUCKET_NAME, s3_key)
    print(f"Uploaded to s3://{CODE_BUCKET_NAME}/{s3_key}")


def upload_plain_file(local_path: str, s3_key: str):
    
    s3_client = boto3.client("s3", region_name=AWS_REGION)
    s3_client.upload_file(local_path, CODE_BUCKET_NAME, s3_key)
    print(f"Uploaded to s3://{CODE_BUCKET_NAME}/{s3_key}")


LAMBDA_FOLDERS = [
    "lambda_save_s3_config",
    "lambda_run_glue_job",
    "lambda_glue_job_success",
    "lambda_glue_job_failure",
]

GLUE_SCRIPTS = ["csv_job.py", "json_job.py", "text_job.py"]


if __name__ == "__main__":
    ensure_code_bucket_exists()

    for lambda_folder in LAMBDA_FOLDERS:
        zip_path = build_zip_for_lambda(lambda_folder)
        upload_zip(zip_path, f"{lambda_folder}.zip")

    upload_plain_file(os.path.join(PROJECT_ROOT, "utils", "glue_utils.py"), "glue_utils.py")
    for glue_script in GLUE_SCRIPTS:
        upload_plain_file(os.path.join(PROJECT_ROOT, "glue_jobs", glue_script), glue_script)
