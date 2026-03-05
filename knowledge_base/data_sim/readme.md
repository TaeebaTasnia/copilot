# maveric_platform_data_sim

## Project layout

```text
maveric_platform_data_sim/
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
    kafka.py
  app/main.py
  app/api/v1/routes.py
  app/workers/generate_worker.py
  Agent.md
```

## Database configuration

- The service reads `DATABASE_URL` from the environment. Values such as `postgres://user:pass@host/db` and `postgresql://user:pass@host/db` are both accepted.
- Credentials that contain reserved URL characters (for example `@`) do **not** need to be pre-encoded; the service normalises the URL and percent-encodes the credentials before instantiating SQLAlchemy.
- Blank or missing values leave SQL features disabled, matching existing behaviour for lightweight/local runs.
- Defaults in `.env` point at docker-compose service names (`mongo`, `redis`); override with `localhost` when running the app outside of containers (see `DEV.md` for one-liners).

## Object storage configuration

- Synthetic outputs are written to S3 using `S3_BUCKET` (legacy) or `S3_BUCKET_ARN`. Optional `S3_PREFIX` scopes all artifacts (baselines, UE datasets, generated profiles) beneath a tenant-controlled prefix.
- The CSV upload helpers honour `S3_ASSUME_ROLE_ARN`, `S3_ASSUME_ROLE_EXTERNAL_ID`, and `S3_ASSUME_ROLE_SESSION_NAME`, assuming the configured role before creating the boto3 client. Credentials are refreshed automatically if AWS returns `NoCredentialsError` during upload/download.
- `S3_REGION` still defaults to `us-east-1`. `S3_ENDPOINT_URL` is required only for MinIO/local runs; the helper will skip custom endpoints when an ARN is supplied.
- Callers may pass HTTPS URLs, `s3://` URIs, S3 ARNs, or bare object keys in API payloads. Bare keys are automatically prefixed with `S3_PREFIX` before being resolved against the effective bucket/access point.

## JSON payload conventions

- All POST endpoints accept strict JSON payloads. When supplying identifiers
  (for example `baseline_id`, `dataset_id`), wrap the values in double quotes so
  the request remains valid JSON. The service returns a 422 response with a
  helpful message if the body cannot be decoded.

## Observability

- Request logging middleware adds an `X-Request-ID` header to every response and streams request/response lifecycle events to STDOUT and MongoDB `application_logs` (TTL by severity: DEBUG 7d; INFO/WARN 30d; ERROR/CRITICAL 90d).
- Domain failures and HTTP/validation/unhandled errors use `log_error_to_mongodb()` to persist context-rich entries (tenant, baseline/dataset IDs, request_id, stack trace) into `error_logs` (90-day TTL) with indexes on `{tenant_id, service_name, created_at/resolved}` for fast per-tenant slicing. Query + resolve errors via `/v1/tenants/{tenant_id}/utils/logs/errors|.../resolve|/logs/stats`; `/v1/logs/health` reports Mongo index/TTL readiness.
- MongoDB is optional: if `MONGODB_URL` is unset or lacks a default database the service logs to STDOUT only and continues without failing startup. `testlogs.py` uses `MONGODB_URL` when set (defaults to `mongodb://localhost:27017/fastapi_db`).
- Redis connectivity is wired for future cache/rate-limit hooks and fails open when `REDIS_URL` is missing or the store is unavailable.
- Use the `X-Request-ID` value to correlate API responses with MongoDB log documents when debugging in production; `curl -I http://localhost:8003/v1/ping` should return the header.

## Health & monitoring

- `/health` returns the standard success envelope with `data: {status, service}` for liveness/readiness; the Dockerfile HEALTHCHECK hits this endpoint.
- `/v1/logs/health` returns MongoDB collection/index status for observability readiness checks.
- Docker Compose: `docker-compose up -d mongo redis app && docker-compose logs -f app` (override `MONGODB_URL` / `REDIS_URL` to `localhost` when running outside containers).

## Quick verification

1) Health: `curl -s http://localhost:8003/health`

2) Ping + request ID: `curl -I http://localhost:8003/v1/ping | grep X-Request-ID`

3) Generate dataset (example):

```bash
curl -X POST http://localhost:8003/v1/tenants/demo/utils/topology/generate \
  -H "Content-Type: application/json" \
  -d '{"baseline_id":"bl-123","details":{"description":"demo"},"topology_details":{"min_lat":37,"max_lat":38,"min_long":-122,"max_long":-121,"num_cell_sites":2,"cells_per_site":3,"azimuth_degree":120,"tower_height_min":20,"tower_height_max":50}}'
```

4) Inspect logs in Mongo:

```bash
python testlogs.py summary        # aggregate view
python testlogs.py recent 5       # last 5 request logs
python testlogs.py errors         # error_log samples
curl -s http://localhost:8003/v1/tenants/demo/utils/logs/errors | jq .
```

## OpenAPI (SMO Sim fragment):

> **Ownership**: `/tenants/{tenant_id}/utils/topology|traffic-load|mobility/generate` are served exclusively by `maveric_platform_data_sim`. Other services (for example SMO Sim) no longer expose duplicate handlers and instead rely on this API.

```yaml
openapi: 3.0.3
info: { title: Data Simulation API, version: 0.4.2 }
servers: [ { url: http://localhost:8003/v1 } ]
security: [{ jwt: [] }]
paths:
  /tenants/{tenant_id}/utils/topology/generate:
    parameters: [ { $ref: '#/components/parameters/tenant_id' } ]
    post:
      tags: [Utils, Baselines]
      summary: Generate baseline via synthetic topology generator
      requestBody: { content: { application/json: { schema: { $ref: '#/components/schemas/BaselineCreateUtilsTopologyRequest' }}}}
      responses:
        '201': { description: Created, content: { application/json: { schema: { $ref: '#/components/schemas/BaselineResponse' }}}}
      description: |
        Generates synthetic topology, config, and UE training data CSVs under
        `{prefix?}{tenant_id}/baselines/{baseline_id}/` (default: `s3://{bucket}/tenants/{tenant_id}/baselines/{baseline_id}/`) before recording the baseline row.
  /tenants/{tenant_id}/utils/traffic-load/generate:
    parameters: [ { $ref: '#/components/parameters/tenant_id' } ]
    post:
      tags: [Utils]
      summary: Generate a simulated UE dataset
      requestBody: { content: { application/json: { schema: { $ref: '#/components/schemas/TrafficLoadGenerateRequest' }}}}
      responses:
        '201': { description: Created (inline), content: { application/json: { schema: { $ref: '#/components/schemas/UEDatasetResponse' }}}}

  /tenants/{tenant_id}/utils/mobility/generate:
    parameters: [ { $ref: '#/components/parameters/tenant_id' } ]
    post:
      tags: [Utils]
      summary: Generate mobility data
      requestBody: { content: { application/json: { schema: { $ref: '#/components/schemas/MobilityModelParams' }}}}
      responses:
        '201': { description: Created (inline), content: { application/json: { schema: { $ref: '#/components/schemas/UEDatasetResponse' }}}}

components:
  securitySchemes: { jwt: { type: http, scheme: bearer, bearerFormat: JWT } }
  parameters: { tenant_id: { name: tenant_id, in: path, required: true, schema: { type: string, format: uuid } } }
  schemas:
    SuccessEnvelope: { type: object, required: [success,timestamp,data,errors], properties: { success: {type: boolean, enum:[true]}, timestamp:{type:string,format:date-time}, message:{type:string}, data:{}, errors:{type:array,items:{},maxItems:0,default:[]} } }

    BaselineDetails:
      type: object
      properties:
        description: { type: string }
        metadata: { type: object, additionalProperties: true }

    TopologyDetails:
      type: object
      required: [min_lat, min_long, max_lat, max_long, num_cell_sites, cells_per_site, azimuth_degree, tower_height_min, tower_height_max]
      properties:
        min_lat: { type: number, format: float }
        min_long: { type: number, format: float }
        max_lat: { type: number, format: float }
        max_long: { type: number, format: float }
        num_cell_sites: { type: integer, minimum: 1 }
        cells_per_site: { type: integer, minimum: 1 }
        azimuth_degree: { type: integer, minimum: 0, maximum: 359 }
        tower_height_min: { type: number, format: float }
        tower_height_max: { type: number, format: float }

    BaselineCreateUtilsTopologyRequest:
      type: object
      required: [baseline_id, topology_details]
      properties:
        baseline_id: { type: string }
        details: { $ref: '#/components/schemas/BaselineDetails' }
        topology_details: { $ref: '#/components/schemas/TopologyDetails' }

    BaselineSummary:
      type: object
      required: [baseline_id, details]
      properties:
        baseline_id: { type: string }
        details: { $ref: '#/components/schemas/BaselineDetails' }
        url_to_topo_csv: { type: string, format: uri }
        url_to_trainingdata_csv: { type: string, format: uri }
        url_to_config_csv: { type: string, format: uri }

    BaselineResponse:
      allOf:
        - $ref: '#/components/schemas/SuccessEnvelope'
        - type: object
          properties: { data: { $ref: '#/components/schemas/BaselineSummary' } }

    TrafficLoadGenerateRequest:
      type: object
      required: [baseline_id]
      properties:
        baseline_id: { type: string }
        dataset_id:
          type: string
          description: Optional caller-supplied identifier; conflicts return 409, otherwise a UUID is generated.
        days: { type: integer, minimum: 1, default: 2 }
        num_ues: { type: integer, minimum: 1, default: 300 }
        spatial_params:
          type: object
          additionalProperties: true
          description: Optional overrides for the spatial layout generator; defaults ship with the service.
        time_params:
          type: object
          additionalProperties: true
          description: Optional overrides for per-tick weighting; defaults derive 24 ticks/day.
        random_seed:
          type: integer
          minimum: 0
          nullable: true
        notes: { type: string }

    # Extracted minimal MobilityModelParams for this service
    MobilityModelParams:
      type: object
      required: [ue_tracks_generation]
      properties:
        dataset_id:
          type: string
          description: Optional caller-supplied identifier; duplicate values return 409, otherwise a UUID is generated.
        ue_tracks_generation:
          type: object
          required: [params]
          properties:
            params:
              type: object
              required: [simulation_duration, simulation_time_interval_seconds, num_ticks, num_batches, ue_class_distribution, lat_lon_boundaries, gauss_markov_params]
              properties:
                simulation_duration: { type: integer }
                simulation_time_interval_seconds: { type: number, format: float }
                num_ticks: { type: integer }
                num_batches: { type: integer }
                ue_class_distribution:
                  type: object
                  required: [stationary, pedestrian, cyclist, car]
                  properties:
                    stationary: { $ref: '#/components/schemas/Distribution' }
                    pedestrian: { $ref: '#/components/schemas/Distribution' }
                    cyclist: { $ref: '#/components/schemas/Distribution' }
                    car: { $ref: '#/components/schemas/Distribution' }
                lat_lon_boundaries:
                  type: object
                  required: [min_lat, max_lat, min_lon, max_lon]
                  properties:
                    min_lat: { type: number, format: float }
                    max_lat: { type: number, format: float }
                    min_lon: { type: number, format: float }
                    max_lon: { type: number, format: float }
                gauss_markov_params:
                  type: object
                  required: [alpha, variance, rng_seed, lon_x_dims, lon_y_dims]
                  properties:
                    alpha: { type: number, format: float }
                    variance: { type: number, format: float }
                    rng_seed: { type: integer }
                    lon_x_dims: { type: integer }
                    lon_y_dims: { type: integer }

    Distribution:
      type: object
      required: [count, velocity, velocity_variance]
      properties:
        count: { type: integer, default: 10 }
        velocity: { type: integer, default: 5 }
        velocity_variance: { type: number, format: float, default: 1.0 }

    UEDataset:
      type: object
      required: [dataset_id, source_type, created_at]
      properties:
        dataset_id:
          type: string
          description: Identifier supplied by the caller or generated by the service.
        source_type: { type: string, enum: [real, utils_traffic_load, utils_mobility] }
        baseline_id: { type: string }
        url_to_trainingdata_csv: { type: string, format: uri }
        created_at: { type: string, format: date-time }
        stats: { type: object, additionalProperties: true }
      description: >
        `utils_mobility` is emitted by the mobility generator and is now consumed by SMO Sim responses.

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

## Runtime dependencies

- Synthetic topology generation uses `pandas` to assemble DataFrames and `boto3` to upload CSVs to S3/MinIO. Ensure these packages are installed via `requirements.txt` and storage credentials are configured (see `.env`).

### Utils traffic generator update

- Requests to `POST /v1/tenants/{tenant_id}/utils/traffic-load/generate` now accept `days`, `num_ues`, optional `spatial_params`/`time_params`, and load the referenced baseline topology from S3 before invoking the RADP spatial generator.
- The traffic-load and mobility endpoints both execute inline (no Kafka fallback) and return the created dataset descriptor on success.
- Callers may provide `dataset_id` for both utils endpoints; the service trims whitespace, rejects path separators, and responds with `409 Conflict` when a `(tenant_id, dataset_id)` pair already exists. Omitted identifiers default to UUIDs.
- Generated datasets are written beneath `{prefix?}{tenant_id}/ue/{dataset_id}/synthetic_dataset.csv` (default: `s3://{bucket}/tenants/{tenant_id}/ue/{dataset_id}/synthetic_dataset.csv`); the service persists both the canonical `url_to_smo_ue_data_csv` and the legacy training alias for backwards compatibility.

