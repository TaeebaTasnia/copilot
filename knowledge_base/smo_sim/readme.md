# maveric_platform_smo_sim

## Project layout

```text
maveric_platform_smo_sim/
  design/openapi.yaml
  design/HLD.md
  design/LLD.md
  design/schemas.sql:
    db/migrations/
      00_enums.sql
      20_baselines.sql
      21_ue_datasets.sql
  app/lib/
    envelope.py
    tracing.py
    logging.py
    s3wrap.py
    redis_idem.py         # optional
    kafka.py              # optional
  app/main.py
  app/api/v1/routes.py
  Agent.md
```

## Database configuration

- The service reads `DATABASE_URL` from the environment. Both `postgres://` and `postgresql://` forms are supported.
- Passwords that include reserved URL characters (for example `@`) are accepted; the DSN is normalised so SQLAlchemy sees a correctly percent-encoded credential.
- When `DATABASE_URL` is empty the service runs in a read-only/mock mode without touching Postgres.

## Object storage configuration

- The SMO simulator validates and purges baseline/UE dataset artefacts under `S3_BUCKET` or, when supplied, the location described by `S3_BUCKET_ARN`. `S3_PREFIX` scopes all tenant artefacts beneath the configured hierarchy.
- `S3_ASSUME_ROLE_ARN`, `S3_ASSUME_ROLE_EXTERNAL_ID`, and `S3_ASSUME_ROLE_SESSION_NAME` let the purge helpers assume a dedicated IAM role; the boto3 client is refreshed automatically if AWS returns `NoCredentialsError` during list/delete operations.
- `S3_REGION` remains optional (defaults to `us-east-1`). `S3_ENDPOINT_URL` is only required for MinIO/local deployments and is ignored when an ARN is used.
- Baseline/UE dataset URLs accepted by the API may be HTTPS, `s3://`, or full S3 ARNs. Relative keys are automatically normalised with `S3_PREFIX`, and deletes skip any URLs that fall outside the effective bucket/prefix to avoid cross-tenant purges.

## JSON payload conventions

- All body payloads must be valid JSON. Wrap string fields—such as `baseline_id`,
  `dataset_id`, and storage URLs—in double quotes to avoid decoder failures. The
  API returns a 422 response with guidance if the JSON is malformed.

## R1 interface alignment (SMO-5)

See [`r1-plan.md`](./r1-plan.md) for the complete R1 interface implementation plan, including scope, platform impacts, implementation checklist, and deliverables.

### Implementation Status

**✅ Phase 1 Complete: Service Management & Exposure APIs (Spec §6)**

The R1 interface has been implemented following the O-RAN R1AP specification. All endpoints are tenant-scoped and follow the pattern `/tenants/{tenant_id}/roneint/...`.

**Endpoints implemented:**
- **Service Registration API (v1)**: `app/api/v1/endpoints/r1_interface.py`
  - Register, query, get, update, partially update, and deregister service APIs
- **Service Discovery API (v1)**: Discover service APIs with filtering
- **Service Events Subscription API (v1)**: Subscribe/unsubscribe to service event notifications
- **Bootstrap API (v1)**: Get bootstrap information for service discovery

**Models & Schemas:**
- Pydantic models: `app/models/r1_models.py`
- SQLAlchemy schemas: `app/schemas/r1_schemas.py`
- Database tables: `r1_service_publications`, `r1_service_discoveries`, `r1_service_subscriptions`, `r1_bootstrap_endpoints`

**Features:**
- SemVer `Version` headers in all responses (per spec §5.2)
- Tenant scoping via RLS policies
- ProblemDetails error responses (RFC 7807)
- Full OpenAPI documentation in `design/openapi.yaml`

**Configuration:**
- All R1 endpoints are automatically registered via `app/api/v1/routes.py`
- Database tables are created automatically on startup (via `app/main.py`)
- RLS policies enforce tenant isolation

**🔄 Phase 2 Pending**: Data Management & Exposure APIs (Spec §7)  
**🔄 Phase 3 Pending**: RAN OAM Services (Spec §8)

## E2 interface implementation

See [`e2_spec.md`](./e2_spec.md) and [`E2-Data-Pipeline-Explanation.md`](./E2-Data-Pipeline-Explanation.md) for the complete E2 interface specification and data pipeline documentation.

### Implementation Status

**✅ Phase 1 Complete: E2AP, E2SM-KPM, and E2SM-RC APIs**

The E2 interface has been implemented following the O-RAN E2AP, E2SM-KPM, and E2SM-RC specifications. All endpoints are tenant-scoped and follow the pattern `/tenants/{tenant_id}/etwoint/...`.

**Endpoints implemented:**
- **E2AP Control Plane APIs (v1)**: `app/api/v1/endpoints/e2_interface.py`
  - E2 Node registration and management (register, list, get, delete)
  - Subscription management (create, list, delete subscriptions)
- **E2SM-KPM APIs (v1)**: Key Performance Measurements
  - Cell-level measurements retrieval
  - UE-level measurements retrieval
  - Network topology retrieval
- **E2SM-RC APIs (v1)**: RAN Control
  - Cell configuration management (get, update)
  - Control action execution and status tracking

**Models & Schemas:**
- Pydantic models: `app/models/e2_models.py`
- SQLAlchemy schemas: `app/schemas/e2_schemas.py`
- Database tables: `e2_nodes`, `e2_subscriptions`, `e2_cell_measurements`, `e2_ue_measurements`, `e2_topology`, `e2_cell_configs`, `e2_control_actions`

**Features:**
- Tenant scoping via RLS policies
- Support for E2 Node registration with RAN Functions
- Measurement data collection and storage
- Topology and configuration management
- Control action execution and tracking

**Configuration:**
- All E2 endpoints are automatically registered via `app/api/v1/routes.py`
- Database tables are created automatically on startup (via `app/main.py`)
- RLS policies enforce tenant isolation

**Data Flow:**
- E2 Nodes → RIC (via E2 Interface) → SMO Sim (via R1 Interface) → CSV Storage
- See `E2-Data-Pipeline-Explanation.md` for detailed data flow documentation

## example app/lib/envelope.py snippet:

```python
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, List, Dict

@dataclass
class Success:
    success: bool = True
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")
    message: str | None = None
    data: Any = None
    errors: list = field(default_factory=list)

def wrap(data: Any, message: str | None = None) -> dict:
    return Success(message=message, data=data).__dict__
```

app/lib/tracing.py: (initialize OTEL tracer; add tenant/request attrs—stub)

## OpenAPI (SMO Sim fragment):

```yaml
openapi: 3.0.3
info: { title: SMO Sim API, version: 0.4.3 }
servers: [ { url: http://localhost:8002/v1 } ]
security: [{ jwt: [] }]
paths:
  /tenants/{tenant_id}/baselines:
    parameters: [ { $ref: '#/components/parameters/tenant_id' } ]
    get:
      tags: [Baselines]
      summary: List baselines
      responses:
        '200':
          description: OK
          content: { application/json: { schema: { $ref: '#/components/schemas/BaselinesListResponse' } } }
    post:
      tags: [Baselines]
      summary: Create baseline (real topology URLs)
      requestBody: { content: { application/json: { schema: { $ref: '#/components/schemas/BaselineCreateRealTopologyRequest' }}}}
      responses:
        '201': { description: Created, content: { application/json: { schema: { $ref: '#/components/schemas/BaselineResponse' }}}}

  /tenants/{tenant_id}/baselines/{baseline_id}:
    parameters:
      - $ref: '#/components/parameters/tenant_id'
      - name: baseline_id
        in: path
        required: true
        schema: { type: string }
    get:
      tags: [Baselines]
      summary: Get baseline
      responses:
        '200': { description: OK, content: { application/json: { schema: { $ref: '#/components/schemas/BaselineResponse' }}}}
    put:
      tags: [Baselines]
      summary: Update baseline
      requestBody: { content: { application/json: { schema: { $ref: '#/components/schemas/BaselineUpdateRequest' }}}}
      responses:
        '200': { description: Updated, content: { application/json: { schema: { $ref: '#/components/schemas/BaselineResponse' }}}}
    delete:
      tags: [Baselines]
      summary: Delete baseline (S3 + Postgres)
      responses:
        '204': { description: Deleted }
        '401': { $ref: '#/components/responses/Unauthorized' }
        '404': { $ref: '#/components/responses/NotFound' }
        '500': { $ref: '#/components/responses/ServerError' }
      description: |
        Synthetic topology generation is handled by the `maveric_platform_data_sim` service at
        `/tenants/{tenant_id}/utils/topology/generate`. This service only manages CRUD for
        baselines registered by clients. The `/utils/traffic-load/generate` and
        `/utils/mobility/generate` endpoints are also hosted exclusively by Data Sim; SMO Sim no
        longer exposes duplicate handlers.

  /tenants/{tenant_id}/ue-data/datasets:
    parameters: [ { $ref: '#/components/parameters/tenant_id' } ]
    get:
      tags: [UE Data]
      summary: List UE datasets
      responses:
        '200': { description: OK, content: { application/json: { schema: { $ref: '#/components/schemas/UEDatasetsListResponse' }}}}

  /tenants/{tenant_id}/ue-data/datasets/{dataset_id}:
    parameters:
      - { $ref: '#/components/parameters/tenant_id' }
      - name: dataset_id
        in: path
        required: true
        schema: { type: string }
    delete:
      tags: [UE Data]
      summary: Delete UE dataset (S3 + Postgres)
      responses:
        '204': { description: Deleted }
        '401': { $ref: '#/components/responses/Unauthorized' }
        '404': { $ref: '#/components/responses/NotFound' }
        '500': { $ref: '#/components/responses/ServerError' }

  /tenants/{tenant_id}/ue-data/upload:
    parameters: [ { $ref: '#/components/parameters/tenant_id' } ]
    post:
      tags: [UE Data]
      summary: Register a real UE dataset by URL
      requestBody: { content: { application/json: { schema: { $ref: '#/components/schemas/UEDatasetUploadRequest' }}}}
      responses:
        '201': { description: Registered, content: { application/json: { schema: { $ref: '#/components/schemas/UEDatasetResponse' }}}}

components:
  securitySchemes: { jwt: { type: http, scheme: bearer, bearerFormat: JWT } }
  parameters:
    tenant_id: { name: tenant_id, in: path, required: true, schema: { type: string, format: uuid } }
  responses:
    Unauthorized:
      description: Unauthorized
      content: { application/json: { schema: { $ref: '#/components/schemas/ErrorEnvelope' } } }
    NotFound:
      description: Not found
      content: { application/json: { schema: { $ref: '#/components/schemas/ErrorEnvelope' } } }
    ServerError:
      description: Internal server error
      content: { application/json: { schema: { $ref: '#/components/schemas/ErrorEnvelope' } } }
  schemas:
    SuccessEnvelope: { type: object, required: [success,timestamp,data,errors], properties: { success: {type: boolean, enum:[true]}, timestamp:{type:string,format:date-time}, message:{type:string}, data:{}, errors:{type:array,items:{},maxItems:0,default:[]} } }
    ErrorEnvelope:
      type: object
      required: [success, timestamp, message, data, errors]
      properties:
        success: { type: boolean, enum: [false] }
        timestamp: { type: string, format: date-time }
        message: { type: string }
        data: { type: object }
        errors:
          type: array
          items:
            type: object

    BaselineDetails: { type: object, properties: { description:{type:string}, metadata:{type:object, additionalProperties: true} } }
    BaselineSummary:
      type: object
      required: [baseline_id, details]
      properties:
        baseline_id: { type: string }
        details: { $ref: '#/components/schemas/BaselineDetails' }
        url_to_topo_csv: { type: string, format: uri }
        url_to_trainingdata_csv: { type: string, format: uri }
        url_to_config_csv: { type: string, format: uri }
        created_at: { type: string, format: date-time }
    BaselineCreateRealTopologyRequest:
      type: object
      required: [baseline_id, details, url_to_topo_csv]
      properties:
        baseline_id: { type: string }
        details: { $ref: '#/components/schemas/BaselineDetails' }
        url_to_topo_csv: { type: string, format: uri }
        url_to_trainingdata_csv: { type: string, format: uri }
        url_to_config_csv: { type: string, format: uri }
    UEDatasetSourceType: { type: string, enum: [real, utils_traffic_load, utils_mobility] }
    UEDataset:
      type: object
      required: [dataset_id, source_type, created_at]
      properties:
        dataset_id:
          type: string
          description: Identifier reused in the UE dataset S3 prefix.
        source_type: { $ref: '#/components/schemas/UEDatasetSourceType' }
        baseline_id: { type: string }
        url_to_trainingdata_csv:
          type: string
          format: uri
          deprecated: true
          description: Legacy field retained for backward compatibility.
        url_to_smo_ue_data_csv:
          type: string
          format: uri
          description: Canonical SMO UE dataset CSV URL (tenant UE prefix).
        created_at: { type: string, format: date-time }
        stats: { type: object, additionalProperties: true }

    BaselinesListResponse:
      allOf:
        - $ref: '#/components/schemas/SuccessEnvelope'
        - type: object
          properties:
            data:
              type: object
              required: [items,total]
              properties:
                items: { type: array, items: { $ref: '#/components/schemas/BaselineSummary' } }
                total: { type: integer, minimum: 0 }

    BaselineResponse:
      allOf:
        - $ref: '#/components/schemas/SuccessEnvelope'
        - type: object
          properties: { data: { $ref: '#/components/schemas/BaselineSummary' } }

    UEDatasetsListResponse:
      allOf:
        - $ref: '#/components/schemas/SuccessEnvelope'
        - type: object
          properties:
            data:
              type: object
              required: [items,total]
              properties:
                items: { type: array, items: { $ref: '#/components/schemas/UEDataset' } }
                total: { type: integer, minimum: 0 }

    UEDatasetUploadRequest:
      type: object
      required: [dataset_id, baseline_id]
      anyOf:
        - required: [url_to_smo_ue_data_csv]
        - required: [url_to_trainingdata_csv]
      properties:
        dataset_id:
          type: string
          description: Client-supplied identifier aligned with the S3 UE prefix.
        baseline_id: { type: string }
        url_to_smo_ue_data_csv:
          type: string
          format: uri
          description: S3 URL under `{prefix?}{tenant}/ue/{dataset_id}/...` (default: `s3://{bucket}/tenants/{tenant}/ue/{dataset_id}/...`).
        url_to_trainingdata_csv:
          type: string
          format: uri
          deprecated: true
          description: Legacy alias accepted for backward compatibility.

    UEDatasetResponse:
      allOf:
        - $ref: '#/components/schemas/SuccessEnvelope'
        - type: object
          properties: { data: { $ref: '#/components/schemas/UEDataset' } }
```

## Schema migrations (SMO Sim)

db/migrations/00_enums.sql

```sql
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'rapp_id') THEN
    CREATE TYPE rapp_id AS ENUM ('mro','cco','es','lb');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'train_status') THEN
    CREATE TYPE train_status AS ENUM ('queued','training','ready','failed');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'source_type') THEN
    CREATE TYPE source_type AS ENUM ('real','utils_traffic_load','utils_mobility');
  END IF;
END $$;
```

## Runtime dependencies

- S3 cleanup uses `boto3`; ensure the SMO Sim container installs dependencies via `requirements.txt` and that AWS/MinIO credentials are provided (for local dev, see `.env`). Without valid credentials, baseline/UE dataset deletion will return `500` because artifacts cannot be removed from object storage.

db/migrations/20_baselines.sql

```sql
CREATE TABLE IF NOT EXISTS baselines (
  id                         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id                  uuid NOT NULL,
  baseline_id                text NOT NULL,
  description                text,
  url_to_topo_csv            text,
  url_to_trainingdata_csv    text,
  created_by                 uuid,
  created_at                 timestamptz NOT NULL DEFAULT now(),
  updated_at                 timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, baseline_id)
);
CREATE INDEX IF NOT EXISTS idx_baselines_tenant ON baselines (tenant_id);
DROP TRIGGER IF EXISTS baselines_updated_at ON baselines;
CREATE TRIGGER baselines_updated_at BEFORE UPDATE ON baselines
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE baselines ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS baselines_rls ON baselines;
CREATE POLICY baselines_rls ON baselines
USING (tenant_id = current_setting('app.current_tenant')::uuid)
WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid);
```

db/migrations/21_ue_datasets.sql

```sql
CREATE TABLE IF NOT EXISTS ue_datasets (
  id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id                uuid NOT NULL,
  dataset_id               text NOT NULL,
  source_type              source_type NOT NULL,
  baseline_id              text,
  url_to_trainingdata_csv  text,
  url_to_smo_ue_data_csv   text,
  stats                    jsonb,
  created_by               uuid,
  created_at               timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, dataset_id)
);
CREATE INDEX IF NOT EXISTS idx_ue_tenant ON ue_datasets (tenant_id);
-- Backfill helper for legacy rolls where dataset_id was generated server-side
-- UPDATE ue_datasets SET dataset_id = COALESCE(dataset_id, gen_random_uuid()::text);
-- ALTER TABLE ue_datasets ALTER COLUMN dataset_id SET NOT NULL;

ALTER TABLE ue_datasets ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS ue_datasets_rls ON ue_datasets;
CREATE POLICY ue_datasets_rls ON ue_datasets
USING (tenant_id = current_setting('app.current_tenant')::uuid)
WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid);
```
---

## Observability & health

- Request/response logging middleware issues `X-Request-ID` on every response and enriches JSON logs with `tenant_id`/`request_id` via contextvars; when `MONGODB_URL` is set the same entries are persisted to `application_logs` with TTLs per level. HTTP/validation/unhandled errors are captured via `log_error_to_mongodb()` into `error_logs` with the request context.
- Error inspection endpoints (proxied through the gateway): `/v1/tenants/{tenant_id}/baselines/logs/errors|.../resolve|/logs/stats` return only SMO Sim entries (filter includes `service_name`); workers share the same sink.
- Health endpoint: `GET /health` returns the success envelope (`{success:true,data:{status,service}}`) for Docker/K8s probes.
- Quick check: `curl -I http://localhost:8000/health | grep X-Request-ID` (adjust port). Use the header value to correlate client requests with logs.
