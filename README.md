# Log Analysis Pipeline

A real-time log analysis pipeline built on AWS, a Lambda function generates realistic application log events every minute and streams them through Kinesis Firehose into partitioned S3 storage, where Athena runs SQL queries directly against the raw data without loading it into a database. CloudWatch alarms monitor Lambda error rates and Firehose delivery delays. The entire pipeline is provisioned with Terraform.

---

## What It Does

- **Log generation** — Lambda generates 100 realistic application log events per invocation, triggered every minute via EventBridge
- **Streaming ingestion** — Kinesis Firehose buffers and delivers logs to S3 with automatic partitioning by year/month/day
- **Serverless analytics** — Athena queries the S3 data directly using SQL via a Glue catalog table — no database required
- **Observability** — CloudWatch alarms fire on Lambda error spikes or Firehose delivery delays exceeding 15 minutes
- **Analysis queries** — error rate by status code, slowest endpoints by average response time, error breakdown by service, and request volume by hour

---

## Architecture

```
                    ┌─────────────────────────────────────────────────┐
                    │                   AWS                           │
                    │                                                 │
                    │  EventBridge (rate: 1 minute)                   │
                    │       │                                         │
                    │       ▼                                         │
                    │  Lambda (log_generator)                         │
                    │  Generates 100 log events per invocation        │
                    │       │                                         │
                    │       ▼                                         │
                    │  Kinesis Data Firehose                          │
                    │  Buffers → delivers every 60s or 5MB            │
                    │       │                                         │
                    │       ▼                                         │
                    │  S3 (logs bucket)                               │
                    │  logs/year=YYYY/month=MM/day=DD/                │
                    │       │                                         │
                    │       ▼                                         │
                    │  AWS Glue Data Catalog                          │
                    │  (schema definition for Athena)                 │
                    │       │                                         │
                    │       ▼                                         │
                    │  Amazon Athena                                  │
                    │  SQL queries directly against S3                │
                    │                                                 │
                    │  CloudWatch Alarms                              │
                    │  Lambda errors + Firehose delivery delay        │
                    └─────────────────────────────────────────────────┘

All infrastructure provisioned via Terraform
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Log Generation | AWS Lambda (Python 3.11) |
| Scheduling | AWS EventBridge (rate: 1 minute) |
| Streaming Ingestion | AWS Kinesis Data Firehose |
| Storage | AWS S3 (partitioned by date) |
| Schema Catalog | AWS Glue Data Catalog |
| Analytics | Amazon Athena (serverless SQL) |
| Observability | AWS CloudWatch Alarms |
| Infrastructure as Code | Terraform |
| Language | Python 3.11 |

---

## Project Structure

```
log-analysis-pipeline/
├── terraform/
│   ├── main.tf             # All AWS resources — S3, Firehose, Lambda, EventBridge, Glue, Athena, IAM, CloudWatch
│   ├── variables.tf        # Configurable variables (region, retention days, buffer size/interval)
│   └── outputs.tf          # S3 buckets, Firehose stream name, Glue database, Athena workgroup
├── lambda/
│   └── log_generator.py    # Generates realistic HTTP log events and streams to Firehose in batches of 100
├── scripts/
│   ├── setup_athena.py     # Creates Athena external table over S3 log data via Glue catalog
│   └── query_logs.py       # Runs 4 analytical SQL queries against the log data via Athena
├── .gitignore
└── README.md
```

---

## Log Event Schema

Each log event contains the following fields streamed as JSON:

| Field | Type | Description |
|---|---|---|
| timestamp | string | ISO 8601 UTC timestamp |
| level | string | INFO / WARN / ERROR |
| method | string | HTTP method (GET, POST, PUT, DELETE) |
| endpoint | string | API endpoint path |
| status_code | int | HTTP response status code |
| response_time_ms | int | Response time in milliseconds |
| ip_address | string | Simulated client IP |
| user_agent | string | Browser or client identifier |
| request_id | string | Unique request identifier |
| service | string | Originating microservice name |

---

## How to Deploy

### Prerequisites
- [AWS account](https://aws.amazon.com) with IAM credentials configured
- [Terraform](https://developer.hashicorp.com/terraform/install) installed
- [AWS CLI](https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html) installed and configured
- [Python 3.11+](https://www.python.org/downloads/) and boto3 installed

### Steps

**1. Clone the repository**
```bash
git clone https://github.com/AhnafHy/log-analysis-pipeline.git
cd log-analysis-pipeline
```

**2. Deploy infrastructure**
```bash
cd terraform
terraform init
terraform apply
```
Note the output values — you'll need `logs_bucket`, `glue_database`, and `athena_workgroup`.

**3. Trigger the Lambda manually to generate initial logs**

Go to AWS Console → Lambda → `log-analysis-pipeline-generator` → Test → run 5–10 times.

**4. Wait 2–3 minutes for Firehose to deliver to S3**

Check AWS Console → S3 → your logs bucket → confirm partitioned folders appear under `logs/`.

**5. Install boto3**
```bash
pip install boto3
```

**6. Create the Athena table**
```bash
cd ..
python scripts/setup_athena.py YOUR_LOGS_BUCKET YOUR_GLUE_DATABASE YOUR_ATHENA_WORKGROUP
```

**7. Run the analysis queries**
```bash
python scripts/query_logs.py YOUR_GLUE_DATABASE YOUR_ATHENA_WORKGROUP
```

**8. Clean up**
```bash
cd terraform
terraform destroy
```

---

## Analysis Queries

The pipeline runs four analytical queries against the log data:

**1. Error rate by status code** — counts and percentage breakdown of every HTTP status code across all log events

**2. Top 5 slowest endpoints** — average and maximum response time per endpoint and method combination, ordered by slowest first

**3. Error breakdown by service** — ERROR and WARN level counts grouped by microservice, showing which services are generating the most failures

**4. Request volume by hour** — total request count and error count per hour, showing traffic patterns and error spikes over time

---

## Screenshots

**S3 partitioned log storage — logs landing by year/month/day:**

<img width="1619" height="454" alt="S3 data" src="https://github.com/user-attachments/assets/5b6cf6bb-b89d-46da-acd2-d82d3398088c" />

**Athena SQL query results — error rates, response times, service breakdown:**

<img width="905" height="895" alt="SQL query terminal output" src="https://github.com/user-attachments/assets/350999e3-e507-4f5c-8942-5fb873327280" />

**CloudWatch metrics — Firehose IncomingRecords over time:**

<img width="628" height="232" alt="CloudWatch metrics 1" src="https://github.com/user-attachments/assets/14bc26e4-721f-4351-921d-862980fa2b77" />

<img width="628" height="236" alt="CloudWatch metrics 2" src="https://github.com/user-attachments/assets/0fcf47c0-f986-44ee-b2df-d81b3eeacb86" />

---

## Key Concepts Demonstrated

- **Streaming data ingestion** — Kinesis Firehose as a managed streaming pipeline with automatic buffering, batching, and S3 delivery
- **Serverless analytics** — Athena querying raw S3 data directly via SQL without ETL or database loading — pay per query scanned
- **Date partitioning** — S3 prefix structure `year=/month=/day=/` enables Athena partition pruning for efficient queries
- **Glue catalog integration** — external table definition maps JSON schema to S3 data for Athena consumption
- **EventBridge scheduling** — Lambda triggered on a 1-minute rate schedule simulating continuous log ingestion
- **Infrastructure as code** — all pipeline components provisioned and reproducible via Terraform
- **Observability** — CloudWatch alarms on both Lambda error rate and Firehose delivery freshness
