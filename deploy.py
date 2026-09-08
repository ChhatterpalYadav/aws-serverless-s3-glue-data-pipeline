import os

import boto3
from botocore.exceptions import ClientError

from scripts.package_lambda import (
    AWS_REGION,
    CODE_BUCKET_NAME,
    PROJECT_ROOT,
    GLUE_SCRIPTS,
    LAMBDA_FOLDERS,
    ensure_code_bucket_exists,
    build_zip_for_lambda,
    upload_zip,
    upload_plain_file,
)

STACK_NAME = "dnb-assignment3-stack"
TEMPLATE_PATH = os.path.join(PROJECT_ROOT, "infrastructure", "template.yaml")


def package_and_upload_everything():
    ensure_code_bucket_exists()

    for lambda_folder in LAMBDA_FOLDERS:
        zip_path = build_zip_for_lambda(lambda_folder)
        upload_zip(zip_path, f"{lambda_folder}.zip")

    upload_plain_file(os.path.join(PROJECT_ROOT, "utils", "glue_utils.py"), "glue_utils.py")
    for glue_script in GLUE_SCRIPTS:
        upload_plain_file(os.path.join(PROJECT_ROOT, "glue_jobs", glue_script), glue_script)


def _stack_exists(cf_client) -> bool:
    try:
        cf_client.describe_stacks(StackName=STACK_NAME)
        return True
    except ClientError:
        return False


def deploy_stack(notification_email: str):
    cf_client = boto3.client("cloudformation", region_name=AWS_REGION)

    with open(TEMPLATE_PATH, "r") as template_file:
        template_body = template_file.read()

    common_kwargs = {
        "StackName": STACK_NAME,
        "TemplateBody": template_body,
        "Parameters": [
            {"ParameterKey": "CodeBucketName", "ParameterValue": CODE_BUCKET_NAME},
            {"ParameterKey": "NotificationEmail", "ParameterValue": notification_email},
        ],
        "Capabilities": ["CAPABILITY_NAMED_IAM"],
    }

    if _stack_exists(cf_client):
        print(f"Updating existing stack '{STACK_NAME}'...")
        try:
            cf_client.update_stack(**common_kwargs)
        except ClientError as exc:
            if "No updates are to be performed" in str(exc):
                print("No changes to deploy.")
                return
            raise
        waiter = cf_client.get_waiter("stack_update_complete")
    else:
        print(f"Creating new stack '{STACK_NAME}'...")
        cf_client.create_stack(**common_kwargs)
        waiter = cf_client.get_waiter("stack_create_complete")

    print("Waiting for stack operation to complete (this can take several minutes)...")
    waiter.wait(StackName=STACK_NAME)
    print(f"Stack '{STACK_NAME}' deployed successfully.")


if __name__ == "__main__":
    notification_email = os.environ.get("NOTIFICATION_EMAIL")
    if not notification_email:
        notification_email = input("Enter the email address to receive pipeline failure notifications: ").strip()

    package_and_upload_everything()
    deploy_stack(notification_email)
