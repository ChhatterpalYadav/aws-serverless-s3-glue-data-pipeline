AWS Serverless S3-to-Glue Data Processing Pipeline

📌 Project Overview

This project implements a **serverless data processing pipeline on AWS** that automatically processes files uploaded to an Amazon S3 bucket.

The pipeline detects the uploaded file type and size, stores file metadata in DynamoDB, selects the appropriate AWS Glue job, transforms the data, and makes the processed data available through the AWS Glue Data Catalog and Amazon Athena.

The solution also includes **success and failure handling** using Amazon EventBridge, AWS Lambda, Amazon SNS, and DynamoDB.



🏗️ Architecture


                         ┌──────────────────┐
                         │    Amazon S3     │
                         │   Input Bucket   │
                         └────────┬─────────┘
                                  │
                         Object Created Event
                                  │
                                  ▼
                         ┌──────────────────┐
                         │   Amazon SNS     │
                         │    S3 Event      │
                         │      Topic       │
                         └────────┬─────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │                           │
                    ▼                           ▼
          ┌──────────────────┐        ┌──────────────────┐
          │ Save S3 Config   │        │ Run Glue Job     │
          │     Lambda       │        │     Lambda       │
          └────────┬─────────┘        └────────┬─────────┘
                   │                           │
                   ▼                           ▼
          ┌──────────────────┐        ┌──────────────────┐
          │    DynamoDB      │        │    AWS Glue      │
          │  File Config     │        │      Job         │
          └──────────────────┘        └────────┬─────────┘
                                               │
                         ┌─────────────────────┼─────────────────────┐
                         │                     │                     │
                         ▼                     ▼                     ▼
                    ┌─────────┐           ┌─────────┐           ┌─────────┐
                    │   CSV   │           │  JSON   │           │  TEXT   │
                    │   Job   │           │   Job   │           │   Job   │
                    └────┬────┘           └────┬────┘           └────┬────┘
                         │                     │                     │
                         └─────────────────────┼─────────────────────┘
                                               ▼
                                      ┌──────────────────┐
                                      │ Processed Data   │
                                      │       S3         │
                                      └────────┬─────────┘
                                               │
                                               ▼
                                      ┌──────────────────┐
                                      │  Glue Crawler    │
                                      └────────┬─────────┘
                                               │
                                               ▼
                                      ┌──────────────────┐
                                      │ Glue Data Catalog│
                                      └────────┬─────────┘
                                               │
                                               ▼
                                      ┌──────────────────┐
                                      │     Athena       │
                                      │     Queries      │
                                      └──────────────────┘


        Glue Job Failure
               │
               ▼
        ┌──────────────┐
        │ EventBridge  │
        └──────┬───────┘
               │
               ▼
        ┌──────────────────┐
        │ Failure Lambda   │
        └────────┬─────────┘
                 │
          ┌──────┴──────┐
          ▼             ▼
      DynamoDB         SNS
                         │
                         ▼
                       Email




🔄 End-to-End Workflow

1. File Upload

A user uploads a file to the configured Amazon S3 input bucket.

Supported file types include:

- CSV
- JSON
- TXT / Text


2. S3 Event Notification

When an object is created in S3, an event is generated and published to an Amazon SNS topic.

The SNS topic distributes the event to the required Lambda functions.


3. Save File Configuration

The `lambda_save_s3_config` Lambda processes the S3 event and stores information about the uploaded file in DynamoDB.

The stored information includes details such as:

- S3 object key
- Version ID
- File type
- File size
- Processing information

The DynamoDB table used by the project is:

DNBAssignment3FileConfig


4. Determine the Appropriate Glue Job

The `lambda_run_glue_job` Lambda determines which AWS Glue job should process the file.

The selection is based on:

File Type + File Size


The supported size categories are:

| File Size | Category |

| 0–5 KB | Small |
| 5–10 KB | Medium |
| Above 10 KB | Large |

Therefore, the project supports separate Glue processing paths for:

CSV  → 0–5 KB
CSV  → 5–10 KB
CSV  → Above 10 KB

JSON → 0–5 KB
JSON → 5–10 KB
JSON → Above 10 KB

TEXT → 0–5 KB
TEXT → 5–10 KB
TEXT → Above 10 KB

This results in **9 Glue processing jobs**.

🔁 DynamoDB Retry Mechanism

Because the S3 event is delivered through SNS to multiple Lambda functions, there can be a timing difference between the Lambda that stores the file configuration and the Lambda that retrieves it.

To handle this situation, the Glue-triggering Lambda uses a retry mechanism when retrieving the configuration from DynamoDB.

Conceptually:

Run Glue Lambda
       │
       ▼
Check DynamoDB
       │
       ├── Configuration found
       │        ↓
       │    Start Glue Job
       │
       └── Configuration not found
                ↓
             Wait
                ↓
           Retry lookup


This improves the reliability of the event-driven architecture.


⚙️ AWS Glue Processing

The project contains separate Glue Python Shell scripts for the supported file formats:

csv_job.py
json_job.py
text_job.py

Each job:

1. Receives the required input information.
2. Reads the source file from S3.
3. Processes the data.
4. Applies the required transformation.
5. Adds the required country code information.
6. Writes the processed data back to S3.


🌎 Country Code Transformation

The processing logic maps country names to their corresponding country codes.

For example:

India          → IN
United States  → US

The country mapping is maintained in the application logic.

If a country is not found in the mapping, the processing logic uses:

XX

as the country code.

Therefore, the processed data contains the additional:

country_code

field.

🗄️ DynamoDB

The project uses Amazon DynamoDB to maintain file configuration and processing-related information.

Table

DNBAssignment3FileConfig

Primary Key

The table uses a composite key consisting of:

Partition Key : object_key
Sort Key      : version_id

Using the S3 object key and version ID allows different versions of the same S3 object to be tracked independently.

📢 Amazon SNS

Amazon SNS is used for event distribution and failure notifications.

S3 Event Flow

S3
 ↓
SNS Topic
 ↓
Lambda Functions


Failure Notification Flow

Glue Failure
     ↓
EventBridge
     ↓
Failure Lambda
     ↓
SNS
     ↓
Email Notification

This allows operational failures to be communicated automatically.

🚨 Glue Job Failure Handling

AWS Glue job failures are captured through Amazon EventBridge.

The flow is:

AWS Glue Job
     │
     │ FAILED
     ▼
Amazon EventBridge
     │
     ▼
Glue Job Failure Lambda
     │
     ├── Update DynamoDB
     │
     └── Publish SNS Notification
                  │
                  ▼
             Email Alert

This provides a centralized failure-handling mechanism without requiring manual monitoring.


✅ Glue Job Success Handling

Successful Glue jobs are also handled using EventBridge.

The flow is:

AWS Glue Job
     │
     │ SUCCEEDED
     ▼
Amazon EventBridge
     │
     ▼
Success Lambda
     │
     ▼
Glue Crawler
     │
     ▼
Glue Data Catalog
     │
     ▼
Amazon Athena

The crawler discovers the processed data structure and updates the AWS Glue Data Catalog.

🔍 AWS Glue Crawlers

The project uses Glue Crawlers to discover and catalog the processed datasets.

The crawler configuration is organized according to the supported data types:

TextFilesCrawler
CSVFilesCrawler
JSONFilesCrawler

The crawlers populate metadata in the AWS Glue Data Catalog.

📊 Amazon Athena

Amazon Athena can query the processed datasets using the metadata stored in the AWS Glue Data Catalog.

The overall analytical flow is:

S3 Processed Data
       ↓
Glue Crawler
       ↓
Glue Data Catalog
       ↓
Athena
       ↓
SQL Queries

This enables serverless querying without managing database servers.


📁 Project Structure

aws-serverless-s3-glue-data-pipeline/
│
├── src/
│   ├── lambda_save_s3_config/
│   ├── lambda_run_glue_job/
│   ├── lambda_glue_job_success/
│   ├── lambda_glue_job_failure/
│   └── utils/
│
├── glue_jobs/
│   ├── csv_job.py
│   ├── json_job.py
│   └── text_job.py
│
├── scripts/
│   └── package_lambda.py
│
├── tests/
│   └── ...
│
├── deploy.py
├── template.yaml
├── requirements.txt
├── requirements-dev.txt
├── .gitignore
└── README.md


🧩 AWS Services Used

| AWS Service | Purpose |

| Amazon S3 | File storage and event source |
| Amazon SNS | Event distribution and notifications |
| AWS Lambda | Serverless application logic |
| Amazon DynamoDB | File configuration and processing metadata |
| AWS Glue | Serverless ETL/data processing |
| AWS Glue Crawler | Data discovery and cataloging |
| AWS Glue Data Catalog | Metadata management |
| Amazon EventBridge | Glue job event handling |
| Amazon Athena | SQL-based data analysis |
| AWS IAM | Permissions and access control |
| AWS CloudFormation | Infrastructure as Code |

☁️ Infrastructure as Code

The AWS infrastructure is defined using:

template.yaml

CloudFormation is responsible for provisioning and configuring the required AWS resources.

This makes the infrastructure reproducible and reduces the need for manually creating AWS resources through the AWS Console.

🚀 Deployment

The project includes deployment automation.

The main deployment script is:

deploy.py

Lambda packaging is handled through:

scripts/package_lambda.py

The general deployment process is:

Source Code
    ↓
Package Lambda Functions
    ↓
Upload Required Artifacts
    ↓
CloudFormation Deployment
    ↓
AWS Infrastructure
    ↓
Serverless Data Pipeline

🧪 Testing

The project contains automated tests for the application components.

Testing focuses on validating functionality without requiring every test execution to interact with live AWS resources.

AWS service behavior can be mocked where appropriate.

🔐 Security Considerations

The project follows a serverless AWS architecture and uses IAM roles to provide AWS resources with the permissions required to perform their operations.

Sensitive configuration values should not be committed to Git.

Environment-specific or secret configuration should be managed through appropriate AWS configuration and secret-management mechanisms.

The repository should not contain:

- AWS access keys
- AWS secret keys
- `.env` files containing credentials
- Generated deployment packages
- Local virtual environments
- Temporary build files

🎯 Key Features

- Fully serverless architecture
- Automatic S3 file processing
- Event-driven processing using SNS
- File metadata storage using DynamoDB
- File type and size based Glue job selection
- CSV, JSON and text processing
- Country-to-country-code transformation
- DynamoDB retry mechanism
- Glue success handling
- Glue failure handling
- Automatic failure notifications
- Glue Crawlers and Data Catalog integration
- Athena-based querying
- Infrastructure as Code using CloudFormation
- Automated Lambda packaging and deployment

💡 Design Highlights

Event-Driven Architecture

The system reacts automatically to events rather than requiring a continuously running server.

S3 Event
   ↓
SNS
   ↓
Lambda
   ↓
Glue
   ↓
S3
   ↓
Crawler
   ↓
Athena

Serverless

The solution uses managed AWS services such as Lambda, Glue, DynamoDB, SNS, EventBridge and Athena, reducing infrastructure-management requirements.

Fault Handling

Glue failures are captured through EventBridge and routed to a dedicated Lambda function that records the failure and sends an SNS notification.

Scalable Processing

The architecture separates file ingestion, metadata management, transformation, cataloging and querying into independent services.

📌 Project Outcome

The completed solution provides an automated AWS data-processing pipeline where a file uploaded to S3 can travel through the complete lifecycle:

Upload
  ↓
Event Detection
  ↓
Metadata Storage
  ↓
File Classification
  ↓
Glue Job Selection
  ↓
Data Transformation
  ↓
Processed Data Storage
  ↓
Crawler
  ↓
Glue Data Catalog
  ↓
Athena Query

At the same time, failures are automatically detected and reported:

Glue Failure
    ↓
EventBridge
    ↓
Failure Lambda
    ↓
DynamoDB + SNS
    ↓
Notification


👨‍💻 Technologies

Python
AWS Lambda
Amazon S3
Amazon SNS
Amazon DynamoDB
AWS Glue
AWS Glue Data Catalog
AWS Glue Crawlers
Amazon EventBridge
Amazon Athena
AWS CloudFormation
Boto3
