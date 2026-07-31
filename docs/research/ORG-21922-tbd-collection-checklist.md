# ORG-21922 — TBD Collection Checklist

Purpose: everything you must confirm to turn the validated-but-not-runtime-ready
configuration into an executable one. Nothing here changes the schemas or loader.

Legend for **Required for**: `SUV`, `SkyLab`, or `Both`.
Golden rule for safe verification: **never paste a secret into a file or chat.**
Secrets/tokens/identities are provided only as environment variables that the
`env:` references resolve at runtime. **Do not discover expected WIDs by
enumerating the API under test** — that would contaminate the evidence; obtain
them from a separate trusted channel (Workday UI / `xo-suv-prod` / metadata).

---

## A. `environment.json` values (non-secret)

| # | Value | Populates (exact field) | Where it is used | Expected format | Required for | How to verify safely |
|---|-------|-------------------------|------------------|-----------------|--------------|----------------------|
| A1 | SUV host | `environments.suv.host` | `restBaseTemplate` + `tokenUrlTemplate` `{host}` substitution | Bare hostname, no scheme/port/path (e.g. `i-0abc123.workdaysuv.com`) | SUV | From `x2-mcp` `get_suv`/`list_active_suvs`, or the tester's `.env` `SUV_DOMAIN_SUFFIX`. Non-secret. |
| A2 | SkyLab host | `environments.skylab.host` | Same as above | Bare hostname (e.g. `<tenant>.skylab.workday.com`) | SkyLab | Confirm with whoever owns the SkyLab tenant; do not guess. Non-secret. |
| A3 | Auth model | `defaults.auth.model` (or per-env `environments.<env>.auth.model`) | Selects token-acquisition flow (gates `auth.actingAs.*`) | Enum: `oauth2_refresh_token_per_user` \| `oauth2_client_credentials_acting_as` | Both (may differ per env) | Determined by how each env authenticates. SUV tester today logs in per user → likely per-user. SkyLab is **TBD until confirmed**. |
| A4 | Acting-as mechanism | `environments.<env>.auth.actingAs.mechanism` (+ `headerName`, `valueRef`) | Only when model = `oauth2_client_credentials_acting_as`; how the client impersonates a persona | `mechanism`: short string; `headerName`: HTTP header; `valueRef`: `env:`/`secret:` ref | Only the env that uses client-credentials | Confirm from the auth integration docs/owner. `valueRef` stays reference-only. |
| A5 | Toggle name | `defaults.toggle.name` (or per-env) | Pre-flight assertion that the feature toggle gating the API is in the expected state | Toggle identifier string (do **not** assume `ORG-21934`) | Both | From implementation evidence: merged XO metadata / PR / design plan. |
| A6 | Toggle expected state | `defaults.toggle.expectedState` (or per-env) | Same pre-flight | Enum: `on` \| `off` (`tbd` blocks execution) | Both | Same source as A5. |
| A7 (confirm) | Tenant | `defaults.tenant` / `environments.<env>.tenant` | `{tenant}` substitution | String (currently `super`) | Both | Confirm per env; already defaulted, verify it is correct. Non-secret. |
| A8 (confirm) | REST base path | `defaults.restBaseTemplate` / per-env override | Full endpoint URL construction | Template string with `{host}`/`{tenant}` | Both | Confirm SUV uses `/ccx/internalapi/...` and SkyLab uses `/ccx/api/...`. Non-secret. |

---

## B. Secret / reference **values** (env vars only — never persisted)

These references already exist in the config/test-data; you only need to make the
**values** available as environment variables in the runner's shell/secret store.

| # | Env var(s) | Referenced by | Meaning | Required for | How to verify safely |
|---|-----------|---------------|---------|--------------|----------------------|
| B1 | `OC_OAUTH_CLIENT_ID`, `OC_OAUTH_CLIENT_SECRET` | `defaults.auth.clientIdRef` / `clientSecretRef` | OAuth client credentials | Both (whichever env performs OAuth) | Export in shell only; confirm resolution with the loader's ref check (reports name, never value). |
| B2 | `OC_SUV_USER_A..D` | `test-data.suv.json` `personas.<role>.identityRef` | Persona identities on the SUV | SUV (subset allowed) | Export as env vars; identity mapping stays out of files. |
| B3 | `OC_SUV_TOKEN_A..D` | `test-data.suv.json` `personas.<role>.credentialRef` | Per-persona credential (refresh token or equivalent) | SUV | Reference-only; never written to config/evidence. |
| B4 | `OC_SKYLAB_USER_A..D` | `test-data.skylab.json` `personas.<role>.identityRef` | Persona identities on SkyLab | SkyLab (all four required) | Export as env vars. |
| B5 | `OC_SKYLAB_TOKEN_A..D` | `test-data.skylab.json` `personas.<role>.credentialRef` | Per-persona credential | SkyLab | Reference-only. |

Persona role meanings to map when choosing identities: `A`=full-access,
`B`=restricted-hierarchy, `C`=no-`Reports: Navigate Organization`-domain,
`D`=segmented-visibility.

---

## C. Test-data WIDs (`test-data.<env>.json` → `wids.<LABEL>`)

Format for every WID: **32-char lowercase hex** (e.g. `3aa5...e1`) or `TBD`.
Required for **Both** environments (values differ per env). Verify each via a
trusted channel (Workday UI / `xo-suv-prod`), **not** the API under test.

| Label | Field | What to collect |
|-------|-------|-----------------|
| `ORG_VIS` | `wids.ORG_VIS` | An Organization WID that persona A/B **can** see. |
| `ORG_HID` | `wids.ORG_HID` | An Organization WID that a restricted persona (B) **must not** see. |
| `WKR_VIS` | `wids.WKR_VIS` | A Worker WID visible to the persona under test. |
| `WKR_HID` | `wids.WKR_HID` | A Worker WID that must be hidden from the restricted persona. |
| `POS_VIS` | `wids.POS_VIS` | An Unfilled Position WID visible to the persona. |
| `POS_HID` | `wids.POS_HID` | An Unfilled Position WID that must be hidden. |
| `CHILD_HP` | `wids.CHILD_HP` | A navigable with `hasChildren = true` (for the children endpoint). |
| `PARENT_MIX` | `wids.PARENT_MIX` | A navigable whose parent chain mixes visible/hidden ancestors. |
| `ORG_BIG` | `wids.ORG_BIG` | A large organization (many children) for pagination tests. |
| `WID_GHOST` | `wids.WID_GHOST` | A syntactically valid WID that does **not** exist (non-existence test). |
| `WID_BAD` | `wids.WID_BAD` | Already set to all-zeros (syntactically-valid-but-invalid). No action. |

---

## D. Filters (`test-data.<env>.json` → `filters.<LABEL>`)

Required for **Both**. Format: non-empty string (opaque `navigableFilter` value) or `TBD`.

| Label | Field | What to collect |
|-------|-------|-----------------|
| `FLT_OK` | `filters.FLT_OK` | A valid `navigableFilter` value expected to return results. |
| `FLT_BAD` | `filters.FLT_BAD` | A malformed/invalid `navigableFilter` value to exercise error handling. |

---

## E. Readiness check

After collecting the above, run (no requests are sent):

```
./.venv/bin/python -m harness config/environment.json
```

- Fill `environment.json` fields A1–A6 (and confirm A7–A8).
- Populate the `wids`/`filters` your first test cases need (Section C/D).
- Export the Section B env vars in the runner shell.
- The command prints remaining TBDs; execution stays **blocked** until the values
  a given test needs are non-TBD and all referenced env vars resolve.
