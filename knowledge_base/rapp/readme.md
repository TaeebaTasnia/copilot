# maveric_platform_rapp

## Project layout

```text
maveric_platform_smo_sim/
  design/openapi.yaml
  design/HLD.md
  design/LLD.md
  design/schemas.sql:
    db/migrations/
      00_enums.sql
      00_shared_training_jobs.sql
      40_rapp_models.sql
      41_inference_runs.sql
  app/lib/
    envelope.py
    tracing.py
    logging.py
    s3wrap.py
    kafka.py
    idem.py
  app/main.py
  app/api/v1/routes.py
  app/workers/rapp_worker.py
  Agent.md
```

## Database configuration

- `DATABASE_URL` accepts both `postgres://` and `postgresql://` DSN formats.
- Passwords containing reserved characters (such as `@`) are safe to use; the service normalises the URL so SQLAlchemy receives a properly escaped DSN before opening the connection pool.
- Leaving `DATABASE_URL` unset disables Postgres-backed features for lightweight/local execution.

## Object storage configuration

- Configure S3 access via `S3_BUCKET` (legacy/static deployments) or `S3_BUCKET_ARN` when running on AWS managed buckets/access points. Optional `S3_PREFIX` scopes all artefacts under a tenant prefix.
- The worker and the synchronous data loaders honour `S3_ASSUME_ROLE_ARN`, `S3_ASSUME_ROLE_EXTERNAL_ID`, and `S3_ASSUME_ROLE_SESSION_NAME`, assuming the role before performing any object storage calls. When these values are omitted the runtime falls back to the container’s ambient credentials.
- `S3_REGION` continues to default to `us-east-1`. `S3_ENDPOINT_URL` is only required for MinIO/local development; the legacy `S3_ENDPOINT` override is still accepted for backwards compatibility.
- All S3 URLs accepted by the API may be HTTPS presigned URLs, `s3://` URIs, bare object keys, or full S3 ARNs. Relative keys are automatically prefixed with `S3_PREFIX` before being resolved against the effective bucket/access point. HTTP(S) URLs are treated as S3 only when they target the configured endpoint and expose the bucket segment; other hosts are rejected to avoid unsigned downloads.

## Training overrides

- ES/LB training continues to accept `train_days`, `total_timesteps`, and the existing RL overrides. CCO now reuses the same normaliser, so the worker rejects ambiguous DataFrame inputs and coerces hyper-parameters to their expected numeric types before calling `radplib.cco.train_cco`.
- New optional field: `params.learning_rate`. When supplied for a CCO training job it is validated (>0), passed through to the radplib manager, and persisted in both the returned metrics block and the model pickle metadata for audit/debugging. Other overrides (`num_epochs`, `lambda_`, `weak_coverage_threshold`, `over_coverage_threshold`, `epsilon`, `opt_delta`, `seed`) are normalised in the same pass, and `opt_delta` is sanitised to a tuple of integers.
- The worker mirrors the canonical RADP structure, copying the consolidated BDT pickle into `<base>/var/models/{tenant_id}/bdt/{bdt_id}.pickle` before training. The base directory honours `RAPP_WORKER_MODEL_BASE_DIR` so local/dev deployments can mount alternative volumes while retaining the same directory layout.

## CCO inference reuse

- Training artifacts now include an `input_signature` hash and the final tilt vector. When an inference request provides the same topology/UE/config snapshot, the worker returns the cached optimisation results immediately without re-running dGPCO.
- If the snapshot changes (e.g. fresh UE data), the worker applies the stored optimal tilts in a zero-epoch replay, avoiding a full optimisation cycle by default. Callers can opt back into a full search by enabling the `allow_reoptimization` flag.
- Topology/config frames are normalised before hitting the Bayesian digital twin so missing columns such as `cell_carrier_freq_mhz`, `hTx`, or `cell_az_deg` fall back to safe defaults instead of raising attribute errors.
- Real inference now routes through RadPLib (`infer_cco`); the loader filters UE data to the first available day and the requested tick, builds fresh plots from the BDT attachment output, returns the final CCO objective as the optimisation score, and surfaces the recommended tilt settings via `TextMetricsCCO`.

## Comparison inference API

- `POST /v1/tenants/{tenant_id}/rapps/compare/infer` accepts a shared `{baseline_id, bdt_id, ue_dataset_id, tick}` context plus `{base,compare}_rapp_id`/`{base,compare}_rapp_model_id`. The service resolves the base model, optionally loads a compare model (unless `compare_rapp_model_id=BASELINE`), and when the compare artefact belongs to a different rApp ID it now maps that ID to the matching RadPLib harness (ES or LB today) before funnelling the output through the base rApp’s optimisation pipeline so cross-rApp artefacts can be benchmarked consistently. Unsupported overrides (CCO/MRO) generate HTTP 400.
- The response is synchronous (`200 OK`) and returns `ComparisonInferenceResult` containing paired plots, optimisation metrics, and text summaries for the base and compare models; when the compare payload uses the `BASELINE` sentinel the response marks `compare_rapp_metrics.mode` as `"baseline"` to flag the raw topology run.

## Day-scope evaluation (`/infer`)

- `POST /v1/tenants/{tenant_id}/rapps/{rapp_id}/models/{rapp_model_id}/infer` now supports two modes:
  - Tick mode: provide `tick` (legacy async flow, `202` on miss / `200` on cache hit).
  - Day mode: omit `tick`; evaluator runs ticks `0..23` for `day` (default `0`) and returns KPI payloads synchronously (`200`).
- Day mode computes pooled guardrails (`outage_rate`, `coverage_rate`, RSRP/SINR p5/p50/p95), per-tick objectives (`active_cells_ratio`, `energy_saving_ratio`, `estimated_kwh_saved`, `estimated_cost_saved_monthly`, `jains_fairness_index`, `max_ue_per_cell`, `p95_ue_per_cell`), and worst-tick stats.
- Large UE-level arrays are excluded by default and only returned when `include` contains `raw_ue_arrays`.
- Compatibility guard: request `baseline_id` must match both model baseline and dataset baseline.

## Day-scope comparison (`/compare/infer`)

- `POST /v1/tenants/{tenant_id}/rapps/compare/infer` supports day mode when `tick` is omitted.
- Day mode calls the same evaluator for both models and returns:
  - side-by-side day KPI summaries,
  - delta tables for guardrails/objectives,
  - pareto payload (`pareto_x`, `pareto_y`, `pareto_color` selectors).
- Baseline mismatch across model/dataset/request is rejected with explicit `400` details.
## Inference caching & deduplication

- The inference API now derives a deterministic UUIDv5 `run_id` from `(tenant_id, rapp_model_id, baseline_id, bdt_id, ue_dataset_id, tick)` so identical POSTs target the same logical execution. A secondary `db_key = sha256(run_id)` feeds the cache stores.
- Layered cache flow: Redis (L1, `REDIS_URL`) → MongoDB (L2, `MONGODB_URL`) → Postgres `inference_runs` (L3). Cache hits respond with `200 OK` and skip job submission; misses return `202 Accepted` and enqueue a single worker job. If a request arrives while a run is already `queued` or `running` the API simply echoes the existing run/status instead of spawning redundant work.
- The worker writes results to MongoDB first (durable) and then Redis (fast). Whenever Redis/Mongo fall behind, the API rewrites those layers from the canonical Postgres row before responding so all tiers converge.
- Configuration: `CACHE_ENABLED=true` by default. Set it to `false` to disable the cache entirely (useful for local runs without Redis/Mongo). Omit `REDIS_URL` and/or `MONGODB_URL` to auto-disable only that tier; the API now explicitly checks for `None` clients so PyMongo’s lack of truthiness support no longer surfaces a 500 when Mongo is absent. `redis==5.x` is part of `requirements.txt`, so remember to rebuild images when upgrading dependencies.
- Day evaluation cache is Redis-backed with a 7-day TTL and keyed by model hash + dataset hash + day + KPI params.
- Day summaries are persisted in Postgres `rapp_evaluation_results` for restart-safe retrieval.

## OpenAPI (rApp fragment):

```yaml
openapi: 3.0.3
info: { title: rApp Engine API, version: 0.4.8 }
servers: [ { url: http://localhost:8004/v1 } ]
security: [{ jwt: [] }]
paths:
  /tenants/{tenant_id}/rapps:
    parameters: [ { $ref: '#/components/parameters/tenant_id' } ]
    get:
      tags: [rApps/Registry]
      summary: List available rApps
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/SuccessEnvelope'
                  - type: object
                    properties:
                      data:
                        type: array
                        items: { $ref: '#/components/schemas/RApp' }

  /tenants/{tenant_id}/rapps/{rapp_id}/train:
    parameters: [ { $ref: '#/components/parameters/tenant_id' }, { $ref: '#/components/parameters/rapp_id' } ]
    post:
      tags: [rApps/Training]
      summary: Train a model for the selected rApp
      requestBody: { content: { application/json: { schema: { $ref: '#/components/schemas/RAppTrainRequest' }}}}
      responses:
        '202':
          description: Accepted
          content: { application/json: { schema:
            allOf: [ { $ref: '#/components/schemas/SuccessEnvelope' },
                     { type: object, properties: { data: { $ref: '#/components/schemas/RAppTrainingAccepted' }}} ] } }

  /tenants/{tenant_id}/rapps/{rapp_id}/models:
    parameters: [ { $ref: '#/components/parameters/tenant_id' }, { $ref: '#/components/parameters/rapp_id' } ]
    get:
      tags: [rApps/Trained Models]
      summary: List models
      responses:
        '200': { description: OK, content: { application/json: { schema:
          allOf: [ { $ref: '#/components/schemas/SuccessEnvelope' },
                   { type: object, properties: { data: { $ref: '#/components/schemas/PaginatedRAppModels' }}} ] } } }

  /tenants/{tenant_id}/rapps/{rapp_id}/models/{rapp_model_id}:
    parameters:
      - $ref: '#/components/parameters/tenant_id'
      - $ref: '#/components/parameters/rapp_id'
      - $ref: '#/components/parameters/rapp_model_id'
    get:
      tags: [rApps/Trained Models]
      summary: Get model details
      responses:
        '200': { description: OK, content: { application/json: { schema:
          allOf: [ { $ref: '#/components/schemas/SuccessEnvelope' },
                   { type: object, properties: { data: { $ref: '#/components/schemas/RAppModelSummary' }}} ] } } }
    delete:
      tags: [rApps/Trained Models]
      summary: Delete model
      responses: { '204': { description: Deleted } }

  /tenants/{tenant_id}/rapps/{rapp_id}/models/{rapp_model_id}/infer:
    parameters:
      - $ref: '#/components/parameters/tenant_id'
      - $ref: '#/components/parameters/rapp_id'
      - $ref: '#/components/parameters/rapp_model_id'
    post:
      tags: [rApps/Inference]
      summary: Start inference (async)
      requestBody:
        description: Provide baseline, BDT, dataset and tick context for the inference job (deterministic `run_id` derived from the tuple)
        content:
          application/json:
            schema: { $ref: '#/components/schemas/InferenceRequest' }
      responses:
        '200':
          description: Cache hit; inference payload returned immediately
          headers:
            Location:
              description: URL to `/infer/{run_id}`
              schema: { type: string }
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/SuccessEnvelope'
                  - type: object
                    properties:
                      data: { $ref: '#/components/schemas/InferenceResponse' }
        '202':
          description: Accepted; poll the Location header for completion
          headers:
            Location:
              description: URL to `/infer/{run_id}`
              schema: { type: string }
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/SuccessEnvelope'
                  - type: object
                    properties:
                      data: { $ref: '#/components/schemas/InferenceResponse' }

  /tenants/{tenant_id}/rapps/{rapp_id}/models/{rapp_model_id}/infer/{run_id}:
    parameters:
      - $ref: '#/components/parameters/tenant_id'
      - $ref: '#/components/parameters/rapp_id'
      - $ref: '#/components/parameters/rapp_model_id'
      - $ref: '#/components/parameters/run_id'
    get:
      tags: [rApps/Inference]
      summary: Get inference status
      responses:
        '200': { description: OK, content: { application/json: { schema:
          allOf: [ { $ref: '#/components/schemas/SuccessEnvelope' },
                   { type: object, properties: { data: { $ref: '#/components/schemas/InferenceResponse' }}} ] } } }

  /tenants/{tenant_id}/rapps/compare/infer:
    parameters: [ { $ref: '#/components/parameters/tenant_id' } ]
    post:
      tags: [rApps/Inference]
      summary: Compare two rApp models (sync)
      description: |
        Evaluate the base and compare models using the optimisation pipeline defined by ``base_rapp_id`` with a shared `{baseline_id, bdt_id, ue_dataset_id, tick}` context. When ``compare_rapp_id`` differs from the base the handler resolves the override RadPLib identifier, invokes the matching inference harness (ES/LB supported today), and feeds the output through the base optimisation pipeline; unsupported overrides (CCO/MRO) fail with HTTP 400. Set ``compare_rapp_model_id`` to ``BASELINE`` (and keep ``compare_rapp_id`` aligned with ``base_rapp_id``) to benchmark the raw topology configuration.
      requestBody:
        content:
          application/json:
            schema: { $ref: '#/components/schemas/CompareInferenceRequest' }
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/SuccessEnvelope'
                  - type: object
                    properties:
                      data: { $ref: '#/components/schemas/ComparisonInferenceResult' }

components:
  securitySchemes: { jwt: { type: http, scheme: bearer, bearerFormat: JWT } }
  parameters:
    tenant_id: { name: tenant_id, in: path, required: true, schema: { type: string, format: uuid } }
    rapp_id: { name: rapp_id, in: path, required: true, schema: { type: string, enum: [mro, cco, es, lb] } }
    rapp_model_id: { name: rapp_model_id, in: path, required: true, schema: { type: string } }
    run_id: { name: run_id, in: path, required: true, schema: { type: string, format: uuid } }

  schemas:
    SuccessEnvelope: { type: object, required: [success,timestamp,data,errors], properties: { success: {type: boolean, enum:[true]}, timestamp:{type:string,format:date-time}, message:{type:string}, data:{}, errors:{type:array,items:{},maxItems:0,default:[]} } }
    TrainStatus: { type: string, enum: [queued, training, ready, failed] }
    InferenceStatus: { type: string, enum: [queued, running, completed, failed] }
    CompareInferenceRequest:
      type: object
      required: [base_rapp_id, base_rapp_model_id, compare_rapp_id, compare_rapp_model_id, baseline_id, bdt_id, ue_dataset_id, tick]
      properties:
        base_rapp_id: { type: string, enum: [mro, cco, es, lb], description: "Optimisation pipeline to execute; drives the response format." }
        base_rapp_model_id: { type: string }
        compare_rapp_id: { type: string, enum: [mro, cco, es, lb], description: "Optional rApp namespace for the compare model artefact; may differ from base_rapp_id. Cross-rApp comparisons are currently supported for ES and LB only." }
        compare_rapp_model_id: { type: string, description: "Identifier of the compare model or the literal BASELINE to evaluate the raw topology configuration." }
        baseline_id: { type: string }
        bdt_id: { type: string }
        ue_dataset_id: { type: string }
        tick: { type: integer, minimum: 0, maximum: 23 }
    ComparisonInferenceResult:
      type: object
      required: [base_rapp_plot, base_rapp_optimization_metric, base_rapp_text, compare_rapp_plot, compare_rapp_optimization_metric, compare_rapp_text]
      properties:
        base_rapp_plot: { $ref: '#/components/schemas/PlotData' }
        base_rapp_metrics: { type: object, additionalProperties: true }
        base_rapp_optimization_metric: { type: integer }
        base_rapp_text:
          oneOf:
            - { $ref: '#/components/schemas/TextMetricsMRO' }
            - { $ref: '#/components/schemas/TextMetricsCCO' }
            - { $ref: '#/components/schemas/TextMetricsES' }
            - { $ref: '#/components/schemas/TextMetricsLB' }
        compare_rapp_plot: { $ref: '#/components/schemas/PlotData' }
        compare_rapp_metrics: { type: object, additionalProperties: true, description: "Includes mode=\"baseline\" when the comparison targets the raw topology rather than a trained model." }
        compare_rapp_optimization_metric: { type: integer }
        compare_rapp_text:
          oneOf:
            - { $ref: '#/components/schemas/TextMetricsMRO' }
            - { $ref: '#/components/schemas/TextMetricsCCO' }
            - { $ref: '#/components/schemas/TextMetricsES' }
            - { $ref: '#/components/schemas/TextMetricsLB' }

    RApp: { type: object, required: [rapp_id, name], properties: { rapp_id: { type: string, enum: [mro, cco, es, lb] }, name: { type: string }, description: { type: string } } }

    RAppTrainRequest:
      type: object
      required: [rapp_model_id, bdt_id, baseline_id, dataset_id, params]
      properties:
        rapp_model_id: { type: string }
        bdt_id: { type: string }
        baseline_id: { type: string }
        dataset_id: { type: string }
        params: { type: object, additionalProperties: true }

    RAppTrainingAccepted:
      type: object
      required: [rapp_model_id, status, created_at]
      properties:
        rapp_model_id: { type: string }
        status: { $ref: '#/components/schemas/TrainStatus' }
        created_at: { type: string, format: date-time }
        bdt_id: { type: string }
        dataset_id: { type: string }

    RAppModelSummary:
      type: object
      required: [rapp_model_id, rapp_id, baseline_id, status, created_at]
      properties:
        rapp_model_id: { type: string }
        rapp_id: { type: string, enum: [mro, cco, es, lb] }
        baseline_id: { type: string }
        bdt_id: { type: string }
        dataset_id: { type: string }
        status: { $ref: '#/components/schemas/TrainStatus' }
        metrics: { type: object, additionalProperties: true }
        artifacts_uri: { type: array, items: { type: string } }
        created_at: { type: string, format: date-time }
        updated_at: { type: string, format: date-time }

    PaginatedRAppModels:
      type: object
      required: [items, total]
      properties:
        items: { type: array, items: { $ref: '#/components/schemas/RAppModelSummary' } }
        total: { type: integer, minimum: 0 }

    PlotPoint: { type: object, required: [x, y], properties: { x: {type:number}, y: {type:number} } }
    PlotGroup: { type: object, required: [title, data], properties: { title:{type:string}, data:{ type: array, items: { $ref: '#/components/schemas/PlotPoint' }}} }
    PlotData: { type: object, required: [groups], properties: { groups: { type: array, items: { $ref: '#/components/schemas/PlotGroup' } } } }

    TextMetricsMRO: { type: object, required:[hyst,ttt], properties: { hyst:{type:number}, ttt:{type:number} } }
    CellElConfig: { type: object, required:[cell_id, el_degree], properties: { cell_id:{type:string}, el_degree:{type:number} } }
    CellElOnOffConfig: { type: object, required:[cell_id, el_degree, on_off], properties: { cell_id:{type:string}, el_degree:{type:number}, on_off:{type:boolean} } }
    TextMetricsCCO: { type: object, required:[items], properties: { items: { type: array, items: { $ref: '#/components/schemas/CellElConfig' } } } }
    TextMetricsLB:  { type: object, required:[tick, items], properties: { tick:{type:string}, items:{ type: array, items: { $ref: '#/components/schemas/CellElConfig' } } } }
    TextMetricsES:  { type: object, required:[tick, items], properties: { tick:{type:string}, items:{ type: array, items: { $ref: '#/components/schemas/CellElOnOffConfig' } } } }

    InferenceRequest:
      type: object
      required: [baseline_id, bdt_id, ue_dataset_id, tick]
      properties:
        baseline_id: { type: string }
        bdt_id: { type: string }
        ue_dataset_id: { type: string }
        tick: { type: integer, minimum: 0, maximum: 23 }

    InferenceResult:
      type: object
      required: [plot, optimization_metric, text]
      properties:
        plot: { $ref: '#/components/schemas/PlotData' }
        metrics: { type: object, additionalProperties: true }
        optimization_metric: { type: integer }
        text:
          oneOf:
            - $ref: '#/components/schemas/TextMetricsMRO'
            - $ref: '#/components/schemas/TextMetricsCCO'
            - $ref: '#/components/schemas/TextMetricsES'
            - $ref: '#/components/schemas/TextMetricsLB'

    InferenceResponse:
      type: object
      required: [run_id, rapp_model_id, rapp_id, status, created_at]
      properties:
        run_id: { type: string, format: uuid }
        rapp_model_id: { type: string }
        rapp_id: { type: string, enum: [mro, cco, es, lb] }
        baseline_id: { type: string, nullable: true }
        bdt_id: { type: string, nullable: true }
        status: { $ref: '#/components/schemas/InferenceStatus' }
        ue_dataset_id: { type: string, nullable: true }
        tick: { type: integer, nullable: true, minimum: 0, maximum: 23 }
        result: { $ref: '#/components/schemas/InferenceResult', nullable: true }
        error: { type: string, nullable: true }
        created_at: { type: string, format: date-time }
        updated_at: { type: string, format: date-time, nullable: true }


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


db/migrations/40_rapp_models.sql

```sql
CREATE TABLE IF NOT EXISTS rapp_models (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id      uuid NOT NULL,
  rapp_model_id  text NOT NULL,
  rapp_id        rapp_id NOT NULL,
  baseline_id    text NOT NULL,
  status         train_status NOT NULL,
  config         jsonb,
  metrics        jsonb,
  artifacts_uri  text[],
  created_by     uuid,
  created_at     timestamptz NOT NULL DEFAULT now(),
  updated_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (tenant_id, rapp_model_id)
);
CREATE INDEX IF NOT EXISTS idx_rapp_tenant_status ON rapp_models (tenant_id, rapp_id, status);

DROP TRIGGER IF EXISTS rapp_models_updated_at ON rapp_models;
CREATE TRIGGER rapp_models_updated_at BEFORE UPDATE ON rapp_models
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE rapp_models ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS rapp_models_rls ON rapp_models;
CREATE POLICY rapp_models_rls ON rapp_models
USING (tenant_id = current_setting('app.current_tenant')::uuid)
WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid);
```

db/migrations/41_inference_runs.sql
```sql
CREATE TABLE IF NOT EXISTS inference_runs (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  tenant_id     uuid NOT NULL,
  rapp_id       rapp_id NOT NULL,
  rapp_model_id text NOT NULL,
  baseline_id   text,
  request       jsonb,
  ue_dataset_id text,
  tick          text,
  result        jsonb,
  result_uri    text[],
  status        text NOT NULL DEFAULT 'queued',
  error         text,
  created_by    uuid,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_infer_tenant ON inference_runs (tenant_id, created_at DESC);

ALTER TABLE inference_runs ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS inference_runs_rls ON inference_runs;
CREATE POLICY inference_runs_rls ON inference_runs
USING (tenant_id = current_setting('app.current_tenant')::uuid)
WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid);

```

## Implementation Notes

- Legacy Bayesian Digital Twin pickle files created when the package lived under
  the `app.radp.*` namespace remain compatible. The worker remaps those module
  paths to the current `radplib.dependencies.radp.*` tree while loading.
- The vendored library exposes the canonical ``radplib`` namespace as well as a
  shim for ``radp`` so legacy RADP components continue to import without code
  changes.
- Request handlers call ``set_current_tenant`` before executing SQL so Postgres
  RLS always scopes data to the authenticated tenant.
- Trained rApp artifacts are persisted to `/app/var/models/{tenant_id}/rapps/{rapp_id}/{rapp_model_id}.zip`
  and mirrored to `s3://{bucket}/{prefix?}{tenant_id}/models/rapps/{rapp_id}/{rapp_model_id}.zip` (default prefix: `tenants/`)
  regardless of whether the worker is running in S3 or local/EFS mode. Both locations are recorded in
  `rapp_models.artifacts_uri` (local path first, remote URIs afterwards) so inference pods can rehydrate
  missing ZIPs by resolving the stored references (or deriving the canonical key) before invoking RadP.
  The worker automatically derives the effective bucket from `S3_BUCKET_ARN` when present and refreshes
  the boto3 client if AWS reports `NoCredentialsError` mid-upload. HTTP(S) URLs must point at the configured
  MinIO/S3 endpoint and include the bucket segment; the worker strips duplicated bucket prefixes and rejects
  unrelated hosts. BDT pickles follow the same pattern: if the shared cache is empty the worker downloads the
  pickle from the recorded URI into `/app/var/models/{tenant_id}/bdt/{bdt_id}.pickle` and normalises filenames
  to the canonical `*.pickle` suffix.
- `RAPP_WORKER_LOCAL_DATASET_ROOT` overrides the directory used to hydrate
  synthetic CSV fixtures. The legacy `RAPP_WORKER_LOCAL_DATA_ROOT` is now
  interpreted as the model cache root (still honoured for backwards
  compatibility when it does not point inside `/var/models`).
- UE datasets consumed during inference are automatically filtered to the first
  available `day`, and legacy exports missing `loc_x`/`loc_y`/`mock_ue_id`
  columns are backfilled from `lon`/`lat`/`ue_id` to keep plot generation
  working without re-running data simulations. Attachment results expose both
  `cell_id` and `serving_cell_id`, so the response payload includes per-cell UE
  scatter plots while coverage scoring retains the canonical identifier. The ES
  optimisation metric reuses the training reward calculation
  (`_calculate_reward`) and the LB metric mirrors `CCO_RL_Env._calculate_reward`,
  both running the attached RF dataframe through `CcoEngine` for coverage plus
  their respective load/energy terms.

## JSON payload conventions

- All API requests expect strict JSON. Wrap string identifiers—such as
  `baseline_id`, `bdt_id`, `ue_dataset_id`, and `rapp_model_id`—in double
  quotes. Omitting the quotes produces a 422 error with a message pointing to
  the offending field.
- Example inference request:

```bash
curl -X POST \
  "$BASE_URL/tenants/$TENANT_ID/rapps/es/models/$MODEL_ID/infer" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "baseline_id": "baseline-es",
        "bdt_id": "BDT-01",
        "ue_dataset_id": "dataset-es",
        "tick": 12
      }'
```

## Observability & health

- Request/response logging middleware issues `X-Request-ID` on every response and enriches JSON logs with `tenant_id`/`request_id` via contextvars; use the header value to correlate client calls with container logs. When `MONGODB_URL` is set the service also persists to `application_logs` (`service_name` scoped with TTL per level), and HTTP/validation/unhandled errors are stored via `log_error_to_mongodb()` in `error_logs`.
- Error inspection endpoints (proxied through the gateway): `/v1/tenants/{tenant_id}/rapps/logs/errors|.../resolve|/logs/stats` return only rApp Engine entries (filter includes `service_name`); worker logs land in the same collections.
- Health endpoint: `GET /health` returns the success envelope (`{success:true,data:{status,service}}`) for Docker/K8s probes.
- Quick checks:
  - `curl -I http://localhost:8002/health | grep X-Request-ID` (adjust port)
  - `curl -s http://localhost:8002/v1/tenants/$TENANT_ID/rapps | jq '.request_id'` to confirm request IDs flow through envelopes.
