**Canonical source:** this file (Markdown). Confluence: [Org Chart API Tester — Skylab OAuth Setup Guide](https://confluence.workday.com/pages/viewpage.action?pageId=4521268620).

Configure OAuth for the **Org Chart API Tester** against Workday Skylab.

| Item | Value |
|------|-------|
| **Skylab URL** | https://org.skylab.inday.io/reports |
| **Tenant** | `performance` |
| **Token endpoint** | `https://org.skylab.inday.io/ccx/oauth2/performance/token` |
| **Org Chart API surface** | `/ccx/internalapi/orgchart/v1/performance` |

Skylab Live mode uses a **Bearer access token** only. The tester does not send username/password to Skylab — user identity is encoded in the OAuth access token.

---

## Path 1 — Generate credentials yourself (recommended)

### Step 1 — Register an API Client (one-time)

In the Skylab `performance` tenant (`org.skylab.inday.io`):

1. Open the task **Register API Client for Integrations** (`2997$5931`).
2. Create a client (e.g. **Org Chart API Tester**).
3. Enable the scope **Organizations and Roles** (required for `orgchart`).
4. The token user must have the domain **Reports: Navigate Organization**.
5. Save and record:
   - **Client ID**
   - **Client Secret** (shown only at creation — store securely)

### Step 2 — Generate a refresh token for your user

On the same API Client:

1. Open **Manage Refresh Tokens**.
2. Select the user (e.g. `wd-developer` or a superuser).
3. Click **Generate**.
4. Copy the **refresh token** (long string) and store it in a secure location (password manager, 1Password). **Do not commit it to git.**

If you change API Client scopes later, **regenerate** the refresh token. Existing refresh tokens do not pick up new scopes.

### Step 3 — Exchange refresh token → access token

In a terminal (replace values with your own; do not paste secrets into chat or Jira):

```bash
export OC_OAUTH_CLIENT_ID='your-client-id'
export OC_OAUTH_CLIENT_SECRET='your-client-secret'
export REFRESH_TOKEN='your-refresh-token'

curl -sS -X POST 'https://org.skylab.inday.io/ccx/oauth2/performance/token' \
  -u "${OC_OAUTH_CLIENT_ID}:${OC_OAUTH_CLIENT_SECRET}" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d "grant_type=refresh_token" \
  -d "refresh_token=${REFRESH_TOKEN}" | python3 -m json.tool
```

From the JSON response, copy the `access_token` value.

Access tokens expire (typically ~1 hour). When expired, run the `curl` command again or use **Get token** in the tester (see below).

### Step 4 — Connect in the Org Chart API Tester

1. Run `make start` and open http://127.0.0.1:8000
2. Set **Mode** to **Live**.
3. Set **Host** to `org.skylab.inday.io` and **Tenant** to `performance`.
4. In **Password**, paste either:
   - `Bearer <access_token>`, or
   - the raw JWT (`eyJ…`) — the tester adds the `Bearer` prefix automatically.
5. Click **Connect**.

The **Username** field is not used on Skylab — leave it empty.

### Step 5 — Use **Get token** in the tester (recommended)

The tester can exchange your refresh token without using `curl`:

1. Set **Mode** to **Live**, **Host** to `org.skylab.inday.io`, **Tenant** to `performance`.
2. Expand the **OAuth** panel (shown automatically for Skylab hosts).
3. Enter **Client ID**, **Client Secret**, and **Refresh Token**.
4. Click **Get token** (in the connection bar or OAuth panel).
5. The access token is placed in **Password**; client secret and refresh token fields are cleared from the form.
6. Click **Connect**.

Credentials are sent only to your local FastAPI backend for the token exchange. They are **not** written to disk or included in request history.

Full guide in the browser: http://127.0.0.1:8000/guide/skylab-oauth

---

## Path 2 — Request pre-provisioned credentials (ORG-21922)

If the ORG-21922 security review team already provisioned Skylab personas, request these values through a secure channel (Slack / 1Password — **not** Jira):

| Variable | Purpose |
|----------|---------|
| `OC_OAUTH_CLIENT_ID` | API Client ID |
| `OC_OAUTH_CLIENT_SECRET` | API Client secret |
| `OC_SKYLAB_TOKEN_A` | Refresh token for Persona A |
| `OC_SKYLAB_TOKEN_B` | Refresh token for Persona B (if applicable) |

Use **Get token** or the `curl` command in Path 1, Step 3, then connect as Persona A or B per the [Security Validation Plan](ORG-21922-security-validation-plan.md).

---

## Path 3 — Test without OAuth (SUV only)

For a quick API smoke test without OAuth setup, use a **SUV** (`*.workdaysuv.com`) in Live mode with normal **username + password**. The tester obtains an ID token automatically via `/ors/{tenant}/services/security/v1/authIdToken`.

SUV results are useful for setup rehearsal but are **not** official evidence for ORG-21922 Skylab sign-off.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| `invalid_client` on token exchange | Wrong Client ID or Client Secret | Verify credentials from Register API Client |
| `invalid_grant` | Refresh token invalid, revoked, or expired | Regenerate refresh token on the API Client |
| Connect OK but API **400** | Malformed navigable WID | Use a 32-character hex WID, not internal IDs like `2500$102` |
| Connect OK but API **401** / **403** | Token user lacks **Reports: Navigate Organization** or missing **Organizations and Roles** scope | Fix user security / API Client scopes; regenerate refresh token |
| Proxy **200** but **Upstream 401** | Access token expired | Click **Get token** again or re-run `curl` |
| Password shows `token:eyJ…` | Wrong prefix | Use `Bearer eyJ…` or raw JWT — not `token:` |

Always judge the **Upstream** status in the tester response, not the local proxy HTTP status.

---

## Security

- Never commit `.env`, client secrets, refresh tokens, or access tokens.
- Clear refresh token from the OAuth form after **Get token** (the UI clears secret fields automatically).
- Store evidence under `evidence/` with tokens redacted (see [SECURITY.md](../SECURITY.md)).

---

## Related documents

| Document | Use |
|----------|-----|
| [README.md](../README.md) | Quick start and architecture |
| [ORG-21922-security-validation-plan.md](ORG-21922-security-validation-plan.md) | Official Skylab security test execution |
| [SECURITY.md](../SECURITY.md) | Credential handling policy |
