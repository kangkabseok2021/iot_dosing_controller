# Cloud-Native Python Backend on AWS — ECS Fargate + RDS + Terraform

A production-grade Python microservice demonstrating the full AWS cloud consulting stack: a FastAPI service ingests OEM sensor events, persists to RDS PostgreSQL via async SQLAlchemy 2.0, and archives raw JSON to S3 (fire-and-forget). Terraform provisions complete AWS infrastructure across four modules. 15 pytest pass at 93% coverage — S3 tested with moto, database with aiosqlite, API with httpx ASGITransport.

---

## Architecture

```
POST /api/v1/events  (plant_id, sensor_id, timestamp, value, unit)
       │  201 + SensorEventResponse
┌──────▼──────────────────────────────────────────────────────────┐
│  FastAPI  (app/main.py)                                          │
│  SensorEventCreate Pydantic validation (unit enum: 7 values)    │
│  asyncio.create_task(_archive_and_update) — fire-and-forget     │
└──────┬──────────────────────────────────────────────────────────┘
       │ async SQLAlchemy 2.0
┌──────▼──────────────────────────────────────────────────────────┐
│  EventRepository  (app/repository.py)                           │
│  insert · get_by_id · list_events(plant_id, sensor_id, limit)   │
│  set_s3_key · COUNT(*) + SELECT in one round-trip               │
└──────┬──────────────────────────────────────────────────────────┘
       │ asyncpg → RDS PostgreSQL 16 (private subnet)
┌──────▼──────────────────────────────────────────────────────────┐
│  SensorEvent ORM (app/db/models.py)                             │
│  id UUID · plant_id · sensor_id · timestamp · value · unit      │
│  created_at server_default · raw_s3_key nullable                │
│  indexes: (plant_id, ts DESC), (sensor_id, ts DESC)             │
└──────────────────────────────────────────────────────────────────┘

S3Archiver  (app/archival.py)  ── runs in asyncio.to_thread ──────
  key = events/{date}/{plant_id}/{event_id}.json
  boto3.put_object(SSE=AES256)  →  None on any exception (silent)
  get_raw(key) → json.loads for replay / audit
```

---

## Data Models

### SensorEventCreate

```python
class SensorEventCreate(BaseModel):
    plant_id:  str    # Field(min_length=1, max_length=64)
    sensor_id: str    # Field(min_length=1, max_length=64)
    timestamp: datetime
    value:     float
    unit: Literal["bar", "°C", "rpm", "V", "A", "kPa", "Hz"]
```

### SensorEventResponse

```python
class SensorEventResponse(BaseModel):
    id:         UUID
    plant_id:   str
    sensor_id:  str
    timestamp:  datetime
    value:      float
    unit:       str
    created_at: datetime
    raw_s3_key: str | None    # populated async after S3 archival
    model_config = {"from_attributes": True}
```

### PaginatedEvents

```python
class PaginatedEvents(BaseModel):
    items:  list[SensorEventResponse]
    total:  int
    limit:  int
    offset: int
```

---

## REST API

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/events` | Ingest sensor event → 201 + `SensorEventResponse`; 422 if unit not in enum |
| `GET` | `/api/v1/events` | Paginated list; optional `?plant_id=&sensor_id=&limit=&offset=` |
| `GET` | `/api/v1/events/{event_id}` | Single event; 404 if not found |
| `GET` | `/health` | `{status: "ok"}` |
| `GET` | `/metrics` | Prometheus exposition format |

---

## Terraform — 4 AWS Modules

```
terraform/
├── main.tf          # root — wires modules, S3 remote state + DynamoDB lock
├── variables.tf     # env, aws_region, db_instance_class, ecs_desired_count, ecr_image_tag
├── outputs.tf       # alb_dns_name, rds_endpoint (sensitive), s3_bucket_name, ecr_repo_url
└── modules/
    ├── vpc/         # aws_vpc · 2 public + 2 private subnets · IGW · NAT gateway · route tables
    ├── ecs/         # ECR + lifecycle · ECS cluster (ContainerInsights) · task def (Fargate 512/1024)
    │               # ALB + target group + listener · ECS service · security groups
    ├── rds/         # random_password → SSM SecureString · db_subnet_group · SG (5432 from ECS only)
    │               # aws_db_instance (postgres 16.1, encrypted, private, backup 7d)
    └── s3_iam/      # aws_s3_bucket (versioned, AES256, public access blocked)
                    # Lifecycle: GLACIER after 90 days · IAM role policy (s3:PutObject/GetObject + logs)
```

**Remote state:** `backend "s3"` with `encrypt = true` + `dynamodb_table` for state locking — prevents concurrent `terraform apply`.

**Least-privilege IAM:** ECS task role gets `s3:PutObject + s3:GetObject` on `bucket/events/*` only, plus CloudWatch log writes. No S3:* or broad policies.

---

## Quick Start

```bash
cd aws_sensor_api
uv sync

# Run tests (no real AWS needed)
uv run pytest tests/ -v

# Run locally (SQLite for dev)
DATABASE_URL=sqlite+aiosqlite:///./dev.db \
S3_BUCKET=local-test \
uv run uvicorn app.main:app --reload --port 8080

# Provision AWS infrastructure
cd terraform
terraform init
terraform plan -var env=dev
terraform apply -var env=dev

# Post a sensor event
curl -X POST http://<alb-dns>/api/v1/events \
  -H "Content-Type: application/json" \
  -d '{"plant_id":"PLT-001","sensor_id":"TEMP-A","timestamp":"2026-01-15T08:00:00Z","value":85.3,"unit":"°C"}'
```

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DATABASE_URL` | `postgresql+asyncpg://...` | SQLAlchemy async DSN |
| `S3_BUCKET` | `oem-sensor-events` | Target S3 bucket name |
| `AWS_REGION` | `eu-central-1` | AWS region for S3 client |
| `LOG_LEVEL` | `INFO` | Python logging level |

---

## Testing

```bash
cd aws_sensor_api
uv run pytest tests/ -v
```

**15 tests — no real AWS, no real PostgreSQL, no network.**

| Suite | n | What it validates |
|---|---|---|
| `test_api` | 5 | POST valid → 201, POST invalid unit → 422, GET list total, GET by id, GET missing → 404 |
| `test_repository` | 5 | insert+retrieve, plant_id filter, pagination total, set_s3_key persists, missing → None |
| `test_archival` | 5 | uploads to mocked S3, key contains plant_id + event_id, get_raw round-trip, failure → None, key ends .json |

### Key mock patterns

```python
# SQLite replaces PostgreSQL — same ORM code, zero infra
TEST_DB_URL = "sqlite+aiosqlite:///:memory:"
app.dependency_overrides[get_session] = _get_test_session

# moto mocks all boto3 S3 calls — no credentials needed
@pytest.fixture
def s3_bucket():
    with mock_aws():
        boto3.client("s3", region_name="eu-central-1").create_bucket(
            Bucket=TEST_BUCKET,
            CreateBucketConfiguration={"LocationConstraint": "eu-central-1"},
        )
        yield TEST_BUCKET
```

### Why boto3 + asyncio.to_thread instead of aioboto3

`asyncio.to_thread` wraps the synchronous boto3 call in a thread-pool executor — non-blocking on the event loop, no extra dependency, and fully supported by moto. `aioboto3` requires an async context manager that breaks moto's simple `@mock_aws` decorator.
