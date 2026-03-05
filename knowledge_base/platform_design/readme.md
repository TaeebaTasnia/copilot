# maveric_platform_dev

## Project Overview:

```text
maveric_platform_rapp/
  design/
    openapi.yaml
    HLD.md
    LLD.md
    schemas.sql:

  submodule/
    maveric_platform_data_sim
    maveric_platform_bdt_engine
    maveric_platform_smo_sim
    maveric_platform_rapp
    maveric_platform_gateway
    cloudlynet_ai_copilot

  test/
    postman

```
### OpenAPI (API Doc): design/openapi.yaml
### Schema: schemas.sql: design/schemas.sql (source of truth mirrored by gateway `db/migrations/schemas.sql`)
### Copilot design bundle: `design/copilot/*` (`copilot_openapi.yaml`, `copilot_schemas.sql`, HLD, LLD, `plan.md`)

---
## Dev Onboarding:
### Submodule:
- Initialize after clone: git submodule init
- Fetch contents: git submodule update --recursive
- One-shot init + update: git submodule update --init --recursive
- git submodule add:
```bash
git submodule add git@github.com:CloudlyIO/maveric_platform_data_sim.git submodule/maveric_platform_data_sim
git submodule add git@github.com:CloudlyIO/maveric_platform_bdt_engine.git submodule/maveric_platform_bdt_engine
git submodule add git@github.com:CloudlyIO/maveric_platform_smo_sim.git submodule/maveric_platform_smo_sim
git submodule add git@github.com:CloudlyIO/maveric_platform_rapp.git submodule/maveric_platform_rapp
git submodule add git@github.com:CloudlyIO/maveric_platform_gateway.git submodule/maveric_platform_gateway
```

### Tests - maveric_platform_tests
Update contract tests to hit each service's openapi.yaml and stitched gateway surface if needed.


### Notes on DB ownership & migrations

- Gateway now runs unified GORM auto-migrations at startup using `db/migrations/schemas.sql`, aligning with `design/schemas.sql`.
- Fresh installs only need `design/schemas.sql` or `design/db/init.sql`; migrations `001`-`005` and `dbmigration/cognito.sql` are already inlined for new setups (keep them for upgrades).
- `tenant_memberships` enforces one email per org (global unique on `email`) and requires `user_name` on insert.
- Tables by service of record (for app logic):
  - Gateway: `tenants`, `tenant_memberships`
  - SMO Sim: `baselines`, `ue_datasets` (`url_to_smo_ue_data_csv` is the canonical UE upload field; legacy `url_to_trainingdata_csv` remains accepted).
  - BDT Engine: `bdt_models`
  - rApp Engine: `rapp_models`, `inference_runs`
  - Shared job orchestration: `training_jobs`
- See `datamigration.md` for end-to-end developer workflow on generating Alembic revisions and letting the gateway orchestrate schema updates across environments.

### Utils traffic generator update

- Requests to `POST /v1/tenants/{tenant_id}/utils/traffic-load/generate` now accept `days`, `num_ues`, optional `spatial_params`/`time_params`, and load the referenced baseline topology from S3 before invoking the RADP spatial generator.
- The traffic-load endpoint always executes inline (no Kafka fallback) and returns the created dataset descriptor on success.
- Generated datasets are written to `s3://{tenant_id}/ue/{dataset_id}/synthetic_dataset.csv`; the service persists both the canonical `url_to_smo_ue_data_csv` and the legacy training alias for backwards compatibility.

## Local python setup (optional)
- Create venv: `python3 -m venv venv`
- Install deps: `pip install -r requirements.txt`
- Export env vars as needed per service (see submodule `.env` files for defaults).
- Run a service locally with `uvicorn app.main:app --reload --host 0.0.0.0 --port <port>`.

## Docker workflows
1. **Create the shared network (one-time, safe to rerun)**
   ```bash
   docker network create maveric
   ```

2. **Start infra (Postgres, Redis, Mongo, Kafka, MinIO, pgAdmin)**
   ```bash
   docker compose -f docker-compose.infra.yml up -d
   ```

3. **Start or rebuild all applications together**
   ```bash
   docker compose -f docker-compose.infra.yml -f docker-compose.apps.yml up -d --build
   ```

4. **Rebuild a single service without touching infra** (example: `bdt-worker`)
   ```bash
   docker compose -f docker-compose.infra.yml -f docker-compose.apps.yml up --no-deps --build bdt-worker
   ```

5. **Stop only the application layer**
   ```bash
   docker compose -f docker-compose.infra.yml -f docker-compose.apps.yml stop gateway bdt-engine bdt-worker rapp rapp-worker smo-sim data-sim
   ```

6. **Shut everything down (apps + infra)**
   ```bash
   docker compose -f docker-compose.infra.yml -f docker-compose.apps.yml down
   ```

7. **Check Postgres tables**
   ```bash
   docker exec -it postgres psql -U postgres -d maveric -c "\\dt"
   ```
