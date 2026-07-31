# Org Chart API Tester

A local web application for exercising the **Workday Org Chart REST API** (`orgchart` v1) against SUVs, Skylab, or a built-in mock transport. Use it to explore endpoints interactively, validate connectivity and OAuth, and execute the manual security test plan.

> **Note:** This is a **Python** project. Use `make install` and `make start` (not npm). There is no Node.js build step.

## Features

- Browser UI for all six read-only Org Chart v1 endpoints
- **Mock mode** — offline responses with no network calls
- **Live mode** — real HTTP requests via a local FastAPI proxy
- SUV authentication (username + password → ID token)
- Skylab authentication (OAuth Bearer access token only)
- Connection diagnostics (OpenAPI catalog check, multi-surface probe)
- Request history with upstream vs proxy status distinction
- JSON Schema–validated environment and test-data configuration
- 147 automated unit/integration tests

## Quick start

**Requirements:** Python 3.11+ (tested on 3.14)

```bash
git clone https://github.com/rodrigosantanadapaz/orgchart-api-tester.git
cd orgchart-api-tester

make install    # creates .venv and installs dependencies
make start      # http://127.0.0.1:8000
```

Open the URL in your browser. The app starts in **Mock** mode — connect with any host/tenant/password to try requests without a real backend.

### Makefile targets

| Target    | Description                                      |
|-----------|--------------------------------------------------|
| `install` | Create virtualenv and install `requirements.txt` |
| `start`   | Run uvicorn with auto-reload on port 8000       |
| `test`    | Run the full pytest suite                        |
| `harness` | Validate `config/environment.json` + test data   |
| `clean`   | Remove `.venv`, caches, and `__pycache__` dirs   |

## Architecture

The codebase is split into frozen layers so endpoint knowledge and configuration stay separate from the web UI:

```
┌─────────────────────────────────────────────────────────────┐
│  webapp/          FastAPI + vanilla JS SPA                  │
│  ├── app.py       HTTP routes, error mapping                │
│  ├── service.py   Session, connect/disconnect, execute      │
│  ├── oauth_token  Skylab refresh-token exchange             │
│  ├── suv_id_token SUV username/password → ID token        │
│  └── static/      Browser UI (catalog, form, response)      │
├─────────────────────────────────────────────────────────────┤
│  engine/          Endpoint catalog + request builder        │
│  transport/       Read-only httpx transport + auth        │
├─────────────────────────────────────────────────────────────┤
│  harness/         JSON config loader + schema validation    │
│  config/          environment.json + test-data.*.json       │
└─────────────────────────────────────────────────────────────┘
```

**Request flow (Live mode):**

1. Browser sends `POST /api/execute` with endpoint id and parameters.
2. `ExecutionService` builds the URL and headers via `engine.request_builder`.
3. `transport.httpx_transport` issues a read-only GET to the Workday host.
4. Response is redacted (no `Authorization` / `Cookie` in output) and returned to the UI.

**Important:** `POST /api/execute` returns HTTP **200** when the local proxy succeeds. The authoritative API result is **`upstreamStatus`** in the response body — always check that field (and the UI's "Upstream" badge) for 4xx/5xx from Workday.

## Mock vs Live mode

| | Mock | Live |
|---|------|------|
| Network | None | Real HTTP to configured host |
| Credentials | Ignored (any values accepted) | Required |
| Use case | UI development, catalog exploration | SUV / Skylab validation |
| Toggle | Mode dropdown before Connect | Mode dropdown before Connect |

Switch mode **before** connecting. If you reload the page while connected, the UI restores the session from the server; use **Disconnect** before changing mode to avoid a 409 conflict.

## Authentication

### Skylab (`org.skylab.inday.io`)

Skylab Live mode is **Bearer-token only**. The username field is disabled — identity is encoded in the OAuth access token.

1. Set mode to **Live**.
2. Enter host (`org.skylab.inday.io`) and tenant (e.g. `performance`).
3. Expand **OAuth** and fill Client ID, Client Secret, and Refresh Token.
4. Click **Get token** — the access token is placed in the Password field.
5. Click **Connect**.

You can also paste `Bearer eyJ…` or a raw JWT directly into Password.

### SUV (Workday development instance)

1. Set mode to **Live**.
2. Enter SUV hostname, tenant, username, and password.
3. Click **Connect** — the tester exchanges credentials for an ID token via `/ors/{tenant}/services/security/v1/authIdToken`.

SUVs use the **internal API** surface: `/ccx/internalapi/orgchart/v1/{tenant}`.

### Mock

Any host, tenant, and password work. No authentication is performed.

## Environment configuration

Runtime defaults live in [`config/environment.json`](config/environment.json). The harness loader validates this file against JSON Schema:

```bash
make harness
# or: .venv/bin/python -m harness config/environment.json
```

Key settings per environment (`suv`, `skylab`):

| Setting | Purpose |
|---------|---------|
| `restBaseTemplate` | Base URL pattern (`{host}`, `{tenant}` placeholders) |
| `auth` | OAuth token URL template and supported models |
| `testDataRef` | Personas and WID placeholders for security tests |
| `evidence` | Where to store manual test artifacts (gitignored) |

**Skylab and SUV** both use `internalapi` (not the public `/ccx/api/...` surface, which returns 400 on Skylab).

Optional overrides via `.env` (copy from [`.env.example`](.env.example)):

| Variable | Description |
|----------|-------------|
| `OC_EXECUTION_MODE` | Default mode: `mock` or `live` |
| `OC_PROBE_NAVIGABLE_WID` | WID for connection probe diagnostics |
| `OC_ACCESS_TOKEN` | Bearer token for `scripts/skylab_openapi_check.py` |

Persona credentials for the security harness use `env:OC_*` references in test-data files — set them in your environment or secret store, never in git.

## Running locally (detailed)

```bash
# 1. Clone and install
make install

# 2. (Optional) copy and edit local overrides
cp .env.example .env

# 3. Start the server
make start

# 4. Run tests (separate terminal)
make test
```

Alternative without Make:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn webapp.app:app --reload --port 8000
python -m pytest
```

### Skylab OpenAPI check (CLI)

```bash
export OC_ACCESS_TOKEN='eyJ...'   # or Bearer eyJ...
python scripts/skylab_openapi_check.py --host org.skylab.inday.io --tenant performance
```

## Security test plans

Manual security testing is documented in [`docs/security-test-plan.md`](docs/security-test-plan.md) (cases T-01 through T-18). There is **no automated runner** for these cases — execute them through the UI:

1. Connect in **Live** mode with the appropriate persona (User A–D).
2. Select the endpoint and parameters from the catalog.
3. Execute and record **upstream status**, response body, and `wd-stat-request-id`.
4. Store evidence under `evidence/` (gitignored); redact tokens per the plan.

Background research and implementation notes from ORG-21922 are in [`docs/research/`](docs/research/).

See also [`SECURITY.md`](SECURITY.md) for credential handling and responsible disclosure.

## Project layout

```
orgchart-api-tester/
├── config/              Environment + test-data JSON (schema-validated)
├── docs/                Security test plan + research artifacts
├── engine/              Frozen endpoint catalog and request builder
├── harness/             Config loader CLI and JSON schemas
├── scripts/             Optional CLI utilities
├── tests/               Pytest suite
├── transport/           HTTP transport and auth providers
├── webapp/              FastAPI app and static SPA
├── Makefile
├── requirements.txt
├── LICENSE              MIT
└── SECURITY.md
```

## Current limitations

- **Read-only API only** — all v1 endpoints are GET; no write operations.
- **Manual security tests** — the test plan is not automated; evidence collection is manual.
- **TBD placeholders** — `config/environment.json` and test-data files contain `TBD` values for hosts, toggles, and WIDs until you configure them for your environment.
- **Skylab public surface** — `/ccx/api/orgchart/...` returns 400; use `internalapi` (already configured).
- **No npm frontend** — the UI is vanilla JS served as static files; no bundler or `package.json`.
- **Session in memory** — credentials are held server-side for the active session only; restarting the server disconnects.
- **Single user** — no multi-tenant or concurrent-session isolation in the local app.

## License

[MIT](LICENSE)
