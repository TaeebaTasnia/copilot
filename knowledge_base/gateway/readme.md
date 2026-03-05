# maveric_platform_gateway

## Project layout

```text
maveric_platform_smo_sim/
  design/openapi.yaml
  design/HLD.md
  design/LLD.md
  design/schemas.sql:
    db/migrations/
      00_enums.sql
      10_tenants.sql
      11_tenant_memberships.sql
  internal/lib/
    envelope/envelope.go
    tracing/tracing.go
    logging/logging.go
    redisidem/idem.go
    s3wrap/s3.go
    kafka/kafka.go            # lightweight; optional use
  internal/auth/jwt.go
  internal/cognito/client.go
  internal/middleware/middleware.go
  internal/proxy/proxy.go
  cmd/gateway/main.go
  Agent.md
```

## Multi-Tenancy APIs

This gateway implements a three-tier role-based multi-tenancy system:

- **Platform Admin** (`cloudly_admin`) - Manages organizations (stored in CloudlyIO org UUID: `00000000-0000-0000-3029-000000000000`)
- **Tenant Admin** (`tenant_admin`) - Manages users + resources within tenant
- **Tenant User** (`tenant_user`) - Accesses resources (read/write, run inference)

## Authentication (AWS Cognito)

Gateway expects a Cognito **ID token** with custom claims:

- `custom:tenant_id` (tenant UUID)
- `custom:role` (`cloudly_admin`, `tenant_admin`, `tenant_user`)

JWT verification uses Cognito JWKS (`COGNITO_JWKS_URL`) and validates `iss` + `aud` (app client ID).
Gateway enforces `token_use == "id"`; access tokens are rejected.
Admin/user provisioning uses Cognito Admin APIs (AWS SDK v2).

Required env (see `.env.example`):

- `COGNITO_REGION`, `COGNITO_USER_POOL_ID`, `COGNITO_APP_CLIENT_ID`
- `COGNITO_JWKS_URL`, `COGNITO_JWT_ISS`
- `AWS_REGION`, `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`
- `REQUIRE_ADMIN_MEMBERSHIP` (optional; default false)
- `COPILOT_BASE_URL` (gateway upstream for copilot backend, e.g. `http://copilot-backend:8000`)
- `COPILOT_BACKEND_API` (gateway->copilot shared API key header value; default `dev-secret-key-CHANGE-IN-PRODUCTION-use-openssl-rand-hex-32`)
- `CORS_ALLOW_ORIGINS` (optional CSV; default `http://localhost:3000` in dev)

### Tenant Lookup (public)

Used by frontend login flows to resolve a tenant before authentication:

`GET /tenants/lookup?tenant_name=Acme` (or `?slug=acme`).

Returns `tenant_id`, `tenant_name`, and `tenant_status`.

### Platform Admin Endpoints (`/v1/admin/**`)

Require: `cloudly_admin` role in CloudlyIO org.
If `REQUIRE_ADMIN_MEMBERSHIP=true`, the caller must also have a membership row in DB.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/admin/tenants` | List all tenants (paginated) |
| POST | `/admin/tenants` | Create tenant + first admin (returns temp_password; Cognito emails invite) |
| GET | `/admin/tenants/{tenant_id}` | Get tenant details + user_count |
| PATCH | `/admin/tenants/{tenant_id}` | Update tenant_name / tenant_status |
| DELETE | `/admin/tenants/{tenant_id}` | Delete tenant (cascade users + RLS revoke) |
| GET | `/admin/platform-admins` | List platform admins (paginated) |
| POST | `/admin/platform-admins` | Create platform admin (returns temp_password; Cognito emails invite) |
| DELETE | `/admin/platform-admins/{user_id}` | Delete platform admin |
| POST | `/admin/tenants/{tenant_id}/admins` | Create additional tenant admin (returns temp_password; Cognito emails invite) |

### Tenant User Management Endpoints (`/v1/tenants/{tenant_id}/users`)

Require: `tenant_admin` role in specified tenant.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/tenants/{tenant_id}/users` | List users in tenant (paginated, includes user_name) |
| POST | `/tenants/{tenant_id}/users` | Create user (returns temp_password + user_name; Cognito emails invite) |
| GET | `/tenants/{tenant_id}/users/{user_id}` | Get user details (includes user_name) |
| DELETE | `/tenants/{tenant_id}/users/{user_id}` | Delete user (returns 204 No Content) |

### Error Codes

| Code | Status | When |
|------|--------|------|
| USER_NOT_FOUND | 404 | User not found in tenant |
| TENANT_NOT_FOUND | 404 | Tenant not found |
| ADMIN_NOT_FOUND | 404 | Platform admin not found |
| TENANT_FORBIDDEN | 403 | Insufficient role for action (requires tenant_admin) |
| PLATFORM_ADMIN_REQUIRED | 403 | Not a platform admin (requires cloudly_admin) |
| PLATFORM_ADMIN_MEMBERSHIP_REQUIRED | 403 | Platform admin membership row missing (when enabled) |
| EMAIL_ALREADY_EXISTS | 409 | Email already exists in another tenant |
| CLOUDLYIO_ORG_PROTECTED | 409 | Cannot delete CloudlyIO org (resource constraint) |
| PROTECTED_ADMIN | 409 | Cannot delete primary admin (protected email) |
| COGNITO_ERROR | 502 | Cognito Admin API failure |

### Error Response Models

All error responses follow the structured envelope format with details:

**404 TENANT_NOT_FOUND**
```json
{
  "success": false,
  "timestamp": "2025-12-05T10:30:00Z",
  "message": "tenant not found",
  "data": {},
  "errors": [{
    "code": "TENANT_NOT_FOUND",
    "details": {
      "tenant_id": "00000000-0000-0000-0000-000000000000"
    }
  }]
}
```

**404 USER_NOT_FOUND**
```json
{
  "success": false,
  "timestamp": "2025-12-05T10:30:00Z",
  "message": "user not found",
  "data": {},
  "errors": [{
    "code": "USER_NOT_FOUND",
    "details": {
      "user_id": "12345678-0000-0000-0000-000000000000",
      "tenant_id": "87654321-0000-0000-0000-000000000000"
    }
  }]
}
```

**409 CLOUDLYIO_ORG_PROTECTED**
```json
{
  "success": false,
  "timestamp": "2025-12-05T10:30:00Z",
  "message": "cloudlyio org protected",
  "data": {},
  "errors": [{
    "code": "CLOUDLYIO_ORG_PROTECTED",
    "details": {}
  }]
}
```

**409 PROTECTED_ADMIN**
```json
{
  "success": false,
  "timestamp": "2025-12-05T10:30:00Z",
  "message": "protected admin cannot be deleted",
  "data": {},
  "errors": [{
    "code": "PROTECTED_ADMIN",
    "details": {
      "email": "ahnaftanjid@cloudly.io"
    }
  }]
}
```

**For complete testing guide:** See `/test/v1.5/README.md` in dev repo (Postman v1.5 collection with error scenario tests).

## Database configuration

- `POSTGRES_DSN` must be provided for admin migrations and tenant metadata queries.
- Only `postgres://` URI schemes are accepted. Passwords containing reserved characters (such as `@`) are normalised before migrations or pgx pool creation.
- GORM AutoMigrate is disabled. Apply the schema bundle in `design/schemas.sql` (or an equivalent migration pack) before starting the gateway so enums, triggers, indexes, and table definitions match downstream expectations. On boot the service only runs idempotent guard statements when the tables already exist (extensions, enum refresh, trigger/index re-registration, RLS policies).
- The schema bundle enforces global uniqueness on `tenant_memberships.email` and requires `user_name` on insert.

## JSON payload conventions

- When relaying requests through the gateway ensure client JSON bodies are valid
  (for example, wrap `tenant_id`, `baseline_id`, and other identifiers in double
  quotes). Downstream services respond with structured 422 errors if the payload
  cannot be decoded, and the gateway passes those responses through unchanged.

## Logging proxy (Data Sim, rApp, BDT, SMO Sim)

- Data Sim: `/v1/tenants/{tenant_id}/utils/logs/errors|.../resolve|/logs/stats`
- SMO Sim: `/v1/tenants/{tenant_id}/baselines/logs/errors|.../resolve|/logs/stats`
- rApp: `/v1/tenants/{tenant_id}/rapps/logs/errors|.../resolve|/logs/stats`
- BDT: `/v1/tenants/{tenant_id}/bdt/logs/errors|.../resolve|/logs/stats`

All are proxied by the gateway to their respective services; workers log into the same backends and are retrievable via these endpoints.

## Copilot Gateway Routing (Production Target)

Copilot should be exposed through gateway so frontend traffic remains single-ingress:

- External route prefix: `/v1/tenants/{tenant_id}/copilot/**`
- Internal copilot backend prefix: `/api/v1/**`
- Implementation detail: gateway strips `/v1/tenants/{tenant_id}/copilot` and forwards the remaining suffix under `/api/v1` (for example `/copilot/health` -> `/api/v1/health`).
- Gateway also injects `X-API-Key: ${COPILOT_BACKEND_API}` on proxied copilot requests.
- Tenant path scoping remains a gateway concern in this phase; copilot backend does not expose tenant-prefixed routes directly.

Recommended proxy mappings:
- `GET /v1/tenants/{tenant_id}/copilot/health` -> `GET /api/v1/health`
- `GET /v1/tenants/{tenant_id}/copilot/agents` -> `GET /api/v1/agents`
- `POST/PATCH /v1/tenants/{tenant_id}/copilot/agents/query` -> `POST/PATCH /api/v1/agents/query`
- `POST/GET /v1/tenants/{tenant_id}/copilot/sessions` -> `POST/GET /api/v1/sessions`
- `GET/PATCH/DELETE /v1/tenants/{tenant_id}/copilot/sessions/{session_id}` -> `GET/PATCH/DELETE /api/v1/sessions/{session_id}`
- `GET /v1/tenants/{tenant_id}/copilot/sessions/{session_id}/messages` -> `GET /api/v1/sessions/{session_id}/messages`

Gateway should continue enforcing Cognito JWT + tenant role checks before proxying.
Design and rollout details: `design/copilot/plan.md` in the root repository.

## CORS Ownership

- Gateway is the single CORS owner for browser-facing traffic.
- Upstream CORS headers from proxied services are stripped before responding.
- For local/dev gateway CORS allow-list is controlled by `CORS_ALLOW_ORIGINS` (CSV).

## Local lib (snippets)
internal/lib/envelope/envelope.go
```bash
package envelope

import "time"

type Success struct {
  Success   bool        `json:"success"`
  Timestamp time.Time   `json:"timestamp"`
  Message   string      `json:"message,omitempty"`
  Data      interface{} `json:"data"`
  Errors    []any       `json:"errors"`
}

type Error struct {
  Success   bool        `json:"success"`
  Timestamp time.Time   `json:"timestamp"`
  Message   string      `json:"message"`
  Data      map[string]any `json:"data"`
  Errors    []struct {
    Code    string      `json:"code"`
    Details interface{} `json:"details,omitempty"`
  } `json:"errors"`
}

func Wrap(data interface{}, msg ...string) Success {
  m := ""
  if len(msg) > 0 { m = msg[0] }
  return Success{Success: true, Timestamp: time.Now().UTC(), Message: m, Data: data, Errors: []any{}}
}

```
internal/lib/redisidem/idem.go
```bash
package redisidem

import (
  "context"
  "crypto/sha256"
  "encoding/hex"
  "time"

  "github.com/redis/go-redis/v9"
)

type Store struct{ rdb *redis.Client }

func New(url string) (*Store, error) {
  opt, err := redis.ParseURL(url); if err != nil { return nil, err }
  return &Store{rdb: redis.NewClient(opt)}, nil
}

func hashKey(parts ...string) string {
  h := sha256.New()
  for _, p := range parts { h.Write([]byte(p)) }
  return hex.EncodeToString(h.Sum(nil))
}

// SetNX returns false if duplicate exists within ttl.
func (s *Store) SetNX(ctx context.Context, tenantID, route, idemKey string, ttl time.Duration) (bool, error) {
  k := "idem:" + tenantID + ":" + route + ":" + hashKey(idemKey)
  return s.rdb.SetNX(ctx, k, "1", ttl).Result()
}

```



## OpenAPI (Gateway fragment) — openapi/openapi.yaml

**Note**: The official OpenAPI specification is maintained in `design/openapi.yaml` (dev repo). Below is a summary of multi-tenancy additions.

```yaml
openapi: 3.0.3
info:
  title: Maveric Gateway API
  version: 0.5.0
  description: Multi-tenant SaaS platform with three-tier RBAC (cloudly_admin, tenant_admin, tenant_user).
servers:
  - url: http://localhost:8080/v1
security: [{ jwt: [] }]
paths:
  /health:
    get:
      security: []
      tags: [Health]
      summary: Health check
      responses:
        '200':
          description: OK
          content:
            application/json:
              schema: { $ref: '#/components/schemas/SuccessEnvelope' }

  # Platform Admin & Tenant User Management endpoints documented above in "Multi-Tenancy APIs" section
  # /admin/tenants, /admin/platform-admins, /tenants/{tenant_id}/users, etc.

  /tenants:
    get:
      tags: [Tenants]
      summary: List tenants for current user (from JWT membership cache)
      responses:
        '200':
          description: Tenants
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/SuccessEnvelope'
                  - type: object
                    properties:
                      data: { $ref: '#/components/schemas/PaginatedTenants' }

  /tenants/{tenant_id}:
    parameters: [ { $ref: '#/components/parameters/tenant_id' } ]
    get:
      tags: [Tenants]
      summary: Get tenant details
      responses:
        '200':
          description: Tenant
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/SuccessEnvelope'
                  - type: object
                    properties:
                      data: { $ref: '#/components/schemas/Tenant' }    

    patch:
      tags: [Tenants]
      summary: Update tenant (tenant_admin or cloudly_admin)
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                name: { type: string }
                status: { type: string, enum: [active, suspended] }
      responses:
        '200':
          description: Updated
          content:
            application/json:
              schema: { $ref: '#/components/schemas/SuccessEnvelope' }

  /tenants/{tenant_id}/members:
    parameters: [ { $ref: '#/components/parameters/tenant_id' } ]
    get:
      tags: [Tenant Members]
      summary: List members
      responses:
        '200':
          description: Members
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/SuccessEnvelope'
                  - type: object
                    properties:
                      data: { $ref: '#/components/schemas/PaginatedTenantMembers' }
    post:
      tags: [Tenant Members]
      summary: Invite user by email
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [email, role]
              properties:
                email: { type: string, format: email }
                role: { type: string, enum: [tenant_admin, tenant_user] }
      responses:
        '201':
          description: Invitation
          content:
            application/json:
              schema:
                allOf:
                  - $ref: '#/components/schemas/SuccessEnvelope'
                  - type: object
                    properties:
                      data: { $ref: '#/components/schemas/TenantInvite' }

  /tenants/{tenant_id}/members/{user_id}:
    parameters:
      - $ref: '#/components/parameters/tenant_id'
      - name: user_id
        in: path
        required: true
        schema: { type: string, format: uuid }
    patch:
      tags: [Tenant Members]
      summary: Change role/status
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                role: { type: string, enum: [cloudly_admin, tenant_admin, tenant_user] }
                status: { type: string, enum: [active, suspended] }
      responses:
        '200': { description: Updated, content: { application/json: { schema: { $ref: '#/components/schemas/SuccessEnvelope' }}}}
    delete:
      tags: [Tenant Members]
      summary: Remove member
      responses:
        '204': { description: Removed }

components:
  securitySchemes:
    jwt: { type: http, scheme: bearer, bearerFormat: JWT }
  parameters:
    tenant_id: { name: tenant_id, in: path, required: true, schema: { type: string, format: uuid } }
  schemas:
    SuccessEnvelope:
      type: object
      required: [success, timestamp, data, errors]
      properties:
        success: { type: boolean, enum: [true] }
        timestamp: { type: string, format: date-time }
        message: { type: string }
        data: {}
        errors: { type: array, items: {}, maxItems: 0, default: [] }

    ErrorEnvelope:
      type: object
      required: [success, timestamp, message, data, errors]
      properties:
        success: { type: boolean, enum: [false] }
        timestamp: { type: string, format: date-time }
        message: { type: string }
        data: { type: object, additionalProperties: false, default: {} }
        errors:
          type: array
          items:
            type: object
            properties:
              code: { type: string }
              details: { type: object, additionalProperties: true }

    Tenant:
      type: object
      required: [tenant_id, name, status]
      properties:
        tenant_id: { type: string, format: uuid }
        name: { type: string }
        status: { type: string, enum: [active, suspended] }
        created_at: { type: string, format: date-time }

    TenantMember:
      type: object
      required: [user_id, email, user_name, role, status]
      properties:
        user_id: { type: string, format: uuid }
        email: { type: string, format: email }
        user_name: { type: string }
        role: { type: string, enum: [cloudly_admin, tenant_admin, tenant_user] }
        status: { type: string, enum: [active, suspended] }
        joined_at: { type: string, format: date-time }

    TenantInvite:
      type: object
      required: [invite_id, invite_url]
      properties:
        invite_id: { type: string, format: uuid }
        invite_url: { type: string, format: uri }

    PaginatedTenants:
      type: object
      required: [items, total]
      properties:
        items: { type: array, items: { $ref: '#/components/schemas/Tenant' } }
        total: { type: integer, minimum: 0 }

    PaginatedTenantMembers:
      type: object
      required: [items, total]
      properties:
        items: { type: array, items: { $ref: '#/components/schemas/TenantMember' } }
        total: { type: integer, minimum: 0 }
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

db/migrations/10_tenants.sql

```sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS tenants (
  tenant_id   uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name        text NOT NULL,
  status      text NOT NULL DEFAULT 'active',
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION set_updated_at() RETURNS TRIGGER AS $$
BEGIN NEW.updated_at = now(); RETURN NEW; END; $$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS tenants_updated_at ON tenants;
CREATE TRIGGER tenants_updated_at BEFORE UPDATE ON tenants
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE tenants ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenants_rls ON tenants;
CREATE POLICY tenants_rls ON tenants
USING (tenant_id = current_setting('app.current_tenant')::uuid)
WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid);

```


db/migrations/11_tenant_memberships.sql (Multi-Tenancy Implementation)

```sql
CREATE TABLE IF NOT EXISTS tenant_memberships (
  tenant_id   uuid NOT NULL REFERENCES tenants(tenant_id) ON DELETE CASCADE,
  user_id     uuid NOT NULL,
  email       text NOT NULL,
  user_name   text NOT NULL DEFAULT '',
  -- Roles: cloudly_admin (platform), tenant_admin (org), tenant_user (regular)
  role        text NOT NULL CHECK (role IN ('cloudly_admin', 'tenant_admin', 'tenant_user')),
  status      text NOT NULL DEFAULT 'active',
  created_at  timestamptz NOT NULL DEFAULT now(),
  updated_at  timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (tenant_id, user_id),
  UNIQUE (tenant_id, email)
);

DROP TRIGGER IF EXISTS tenant_memberships_updated_at ON tenant_memberships;
CREATE TRIGGER tenant_memberships_updated_at BEFORE UPDATE ON tenant_memberships
FOR EACH ROW EXECUTE FUNCTION set_updated_at();

ALTER TABLE tenant_memberships ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS tenant_memberships_rls ON tenant_memberships;
CREATE POLICY tenant_memberships_rls ON tenant_memberships
USING (tenant_id = current_setting('app.current_tenant')::uuid)
WITH CHECK (tenant_id = current_setting('app.current_tenant')::uuid);
```

**Migration Notes**: Dev repo migrations 001-005 provide:
- 001: Multi-tenancy schema foundation (email, auth_provider columns, role constraint)
- 002: Role migration (owner/admin → tenant_admin, viewer → tenant_user)
- 003: CloudlyIO org bootstrap (special platform admin org UUID: 00000000-0000-0000-3029-000000000000)
- 004: Email uniqueness constraint (1:1 email:org mapping for MVP safety)
- 005: user_name column with email prefix backfill

**Note:** These schemas are from legacy migrations. For multi-tenancy schema changes (migrations 001-005), see `/migrations/` in dev repo. These include email uniqueness, role migration, CloudlyIO org bootstrap, and user_name column with email prefix backfill.
