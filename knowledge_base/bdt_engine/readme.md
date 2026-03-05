# maveric_platform_bdt_engine

## Project layout

```text
maveric_platform_bdt_engine/
  design/
    openapi.yaml
    HLD.md
    LLD.md
    schemas.sql
  app/
    main.py
    api/v1/routes.py
    core/config.py
    workers/bdt_worker.py
    utils/logger.py
  alembic/
    versions/
  tests/
  README.md
```

## Database configuration

- The service reads `DATABASE_URL` from the environment. Both `postgres://` and `postgresql://` schemes are accepted.
- Passwords may include reserved URL characters such as `@`; the connection string is normalised and credentials are percent-encoded automatically before SQLAlchemy initialises the engine.
- Leaving `DATABASE_URL` blank keeps SQL-backed features disabled for lightweight/local runs.

## Object storage configuration

- Use `S3_BUCKET` for legacy/static deployments or `S3_BUCKET_ARN` when running inside AWS with managed credentials or access points. Optional `S3_ASSUME_ROLE_ARN`, `S3_ASSUME_ROLE_EXTERNAL_ID`, and `S3_ASSUME_ROLE_SESSION_NAME` allow the worker to assume a dedicated access role before talking to S3. `S3_REGION` still defaults to `us-east-1`, while `S3_ENDPOINT_URL` is now only required for MinIO/local setups.
- On startup the worker prints the configured bucket, ARN, prefix, region, endpoint, and assume-role ARN in the format `** NAME ** value` to aid deployment debugging; the log appears only once per process and flags missing buckets.
- Training requests may supply HTTPS URLs, `s3://` URIs, full S3 ARNs, or bare object keys. The worker strips any leading bucket segment, then prepends `S3_PREFIX` when callers omit it before resolving the effective bucket/access point.
- HTTP(S) URLs are only treated as S3 when they target the configured S3/MinIO endpoint and include the bucket segment (for example `http://minio:9000/<bucket>/<key>`). Unrelated hosts fall back to direct HTTPS downloads and are rejected, preventing the worker from fetching arbitrary public content while restoring MinIO compatibility for clusters that expose the endpoint through an IP alias.
- Presigned URLs continue to work; if a query string contains AWS signature parameters the worker downloads the asset via HTTPS instead of the S3 API.

## JSON payload conventions

- Training and management endpoints expect valid JSON payloads. Wrap
  caller-supplied string identifiers (for example `bdt_id`, `baseline_id`) in
  double quotes. Requests with malformed JSON receive a 422 response so clients
  can correct the body quickly.

## Metrics

The service exposes Prometheus metrics at `/metrics`. Custom metrics include:

- `bdt_train_requests_total` (`Counter`): counts training requests. Labels: `tenant_id`, `status`.
- `bdt_train_request_duration_seconds` (`Histogram`): duration of training request handling. Labels: `tenant_id`, `status`.
- `bdt_worker_messages_total` (`Counter`): counts processed worker messages. Labels: `tenant_id`, `status`.
- `bdt_worker_process_duration_seconds` (`Histogram`): time to process a worker message. Labels: `tenant_id`, `status`.

## OpenAPI (SMO Sim fragment):

```yaml
openapi: 3.0.3
info: { title: BDT Engine API, version: 0.4.6 }
servers: [ { url: http://localhost:8001/v1 } ]
security: [{ jwt: [] }]
paths:
  /tenants/{tenant_id}/bdt:
    parameters: [ { $ref: '#/components/parameters/tenant_id' } ]
    get:
      tags: [BDT]
      summary: List BDT models
      responses:
        '200': { description: OK, content: { application/json: { schema: { $ref: '#/components/schemas/BDTModelsListResponse' }}}}
  /tenants/{tenant_id}/bdt/train:
    parameters: [ { $ref: '#/components/parameters/tenant_id' } ]
    post:
      tags: [BDT]
      summary: Start BDT training
      parameters: [ { name: Idempotency-Key, in: header, schema: { type: string } } ]
      requestBody: { content: { application/json: { schema: { $ref: '#/components/schemas/BDTTrainRequest' }}}}
      responses:
        '201': { description: Accepted, content: { application/json: { schema: { $ref: '#/components/schemas/BDTModelResponse' }}}}
  /tenants/{tenant_id}/bdt/models/{bdt_id}:
    parameters:
      - $ref: '#/components/parameters/tenant_id'
      - name: bdt_id
        in: path
        required: true
        schema: { type: string }
    get:
      tags: [BDT]
      summary: Get model
      responses:
        '200': { description: OK, content: { application/json: { schema: { $ref: '#/components/schemas/BDTModelResponse' }}}}

components:
  securitySchemes: { jwt: { type: http, scheme: bearer, bearerFormat: JWT } }
  parameters: { tenant_id: { name: tenant_id, in: path, required: true, schema: { type: string, format: uuid } } }
  schemas:
    SuccessEnvelope: { type: object, required: [success,timestamp,data,errors], properties: { success: {type: boolean, enum:[true]}, timestamp:{type:string,format:date-time}, message:{type:string}, data:{}, errors:{type:array,items:{},maxItems:0,default:[]} } }
    TrainStatus: { type: string, enum: [queued, training, ready, failed] }
    BaselineDetails: { type: object, properties: { description:{type:string}, metadata:{type:object, additionalProperties:true} } }

    BDTModelSummary:
      type: object
      required: [bdt_id, baseline_id, status]
      properties:
        bdt_id: { type: string }
        baseline_id: { type: string }
        details: { $ref: '#/components/schemas/BaselineDetails' }
        status: { $ref: '#/components/schemas/TrainStatus' }
        metrics: { type: object, additionalProperties: true }
        created_at: { type: string, format: date-time }
        updated_at: { type: string, format: date-time }

    PaginatedBDTModels:
      type: object
      required: [items, total]
      properties:
        items: { type: array, items: { $ref: '#/components/schemas/BDTModelSummary' } }
        total: { type: integer, minimum: 0 }

    BDTModelsListResponse:
      allOf:
        - $ref: '#/components/schemas/SuccessEnvelope'
        - type: object
          properties: { data: { $ref: '#/components/schemas/PaginatedBDTModels' } }

    BDTModelResponse:
      allOf:
        - $ref: '#/components/schemas/SuccessEnvelope'
        - type: object
          properties: { data: { $ref: '#/components/schemas/BDTModelSummary' } }

    BDTTrainRequest:
      type: object
      required: [bdt_id, baseline_id]
      properties:
        bdt_id: { type: string, minLength: 1 }
        baseline_id: { type: string }
        details: { $ref: '#/components/schemas/BaselineDetails' }
        url_to_topo_csv:
          type: string
          description: Absolute HTTPS/S3 URL or object key relative to the configured S3 prefix.
        url_to_trainingdata_csv:
          type: string
          description: Absolute HTTPS/S3 URL or object key relative to the configured S3 prefix.
        url_to_config_csv:
          type: string
          description: Absolute HTTPS/S3 URL or object key relative to the configured S3 prefix.
        hyperparams:
          type: object
          properties:
            train_test_split: { type: number, minimum: 0, maximum: 0.9, default: 0.2 }
            random_seed: { type: integer, minimum: 0 }
          additionalProperties: true
```

> Idempotency note: the API scopes the `Idempotency-Key` header to the caller-provided `bdt_id`. Replaying the same key + `bdt_id` returns the original queued model, while reusing the key with a different `bdt_id` is treated as a fresh submission.

> Event note: the emitted `maveric.bdt.train.v1` payload exposes `job_id` as the caller-supplied `bdt_id` for human-friendly tracking, while `training_job_id` continues to reference the persisted `training_jobs.id`. Both identifiers plus the baseline-derived CSV URLs are carried in the message.

> Worker note: the consumer now loads the baseline row referenced by `baseline_id` to resolve the canonical topology/training/config CSV locations when overrides are not provided on the event. Missing required artifacts fail the job early with detailed logging. Incoming URLs may be absolute or relative; when callers submit bare keys the worker prepends `S3_PREFIX`, uses the configured `S3_BUCKET`, strips any duplicated bucket segment from HTTP URLs, and prints the resolved bucket/region/endpoint at startup for quick diagnostics. After training, the worker writes the serialized model map both to S3 (`s3://{bucket}/{prefix?}{tenant}/bdt/{bdt_id}/{bdt_id}.pickle`) and to `/app/var/models/{tenant_id}/bdt/{bdt_id}.pickle` inside the container for local debugging and reuse.

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

db/migrations/00_shared_training_jobs.sql (verbatim across BDT, rApp, DataSim)

```sql
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'train_status') THEN
    CREATE TYPE train_status AS ENUM ('queued','training','ready','failed');
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS training_jobs (
  id               uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id        uuid NOT NULL,
  kind             text NOT NULL CHECK (kind IN ('bdt','rapp','utils')),
  model_ref        uuid,
  status           train_status NOT NULL,
  idempotency_key  text,
  error            text,
  worker           text,
  logs_uri         text,
  created_by       uuid,
  started_at       timestamptz,
  finished_at      timestamptz,
  UNIQUE (tenant_id, idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_jobs_tenant_status ON training_jobs (tenant_id, status, started_at);

ALTER TABLE training_jobs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS training_jobs_rls ON training_jobs;
CREATE POLICY training_jobs_rls ON training_jobs
USING (tenant_id = current_setting('app.current_tenant')::uuid)
WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid);
```


db/migrations/30_bdt_models.sql
```sql
CREATE TABLE IF NOT EXISTS bdt_models (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id      uuid NOT NULL,
  bdt_id         text NOT NULL,
  baseline_id    text NOT NULL,
  status         train_status NOT NULL,
  details        jsonb,
  hyperparams    jsonb,
  metrics        jsonb,
  artifacts_uri  text[],
  created_by     uuid,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, bdt_id)
);
CREATE INDEX IF NOT EXISTS idx_bdt_tenant_status ON bdt_models (tenant_id, status);

DROP TRIGGER IF EXISTS bdt_models_updated_at ON bdt_models;
CREATE TRIGGER bdt_models_updated_at BEFORE UPDATE ON bdt_models
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE bdt_models ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS bdt_models_rls ON bdt_models;
CREATE POLICY bdt_models_rls ON bdt_models
USING (tenant_id = current_setting('app.current_tenant')::uuid)
WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid);

```

## Observability & health

- Request/response logging middleware issues `X-Request-ID` on every response, enriches logs with `tenant_id`/`request_id` via contextvars, and emits JSON logs to STDOUT + MongoDB `application_logs` (TTL per level) when `MONGODB_URL` is configured (`service_name` scoped). HTTP/validation/unhandled failures are captured via `log_error_to_mongodb()` into `error_logs`.
- Error inspection endpoints (proxied through the gateway): `/v1/tenants/{tenant_id}/bdt/logs/errors|.../resolve|/logs/stats` return only this service’s entries (`service_name` filter). Worker logs land in the same collection under the engine’s `APP_NAME`.
- Health endpoint: `GET /health` returns the success envelope (`{success:true,data:{status,service}}`) for Docker/K8s probes; `/metrics` exposes Prometheus output.
- Quick check: `curl -I http://localhost:8001/health | grep X-Request-ID` (port may vary). Use the header value to correlate client requests with logs.

