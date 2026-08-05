# ORG-21922 — Org Chart REST API: Security Validation Plan

**Jira:** ORG-21922 · **Epic:** ORG-21726 · **Toggle:** ORG-21934  
**API:** `orgchart` v1  
**Official execution environment:** **Skylab** — `org.skylab.inday.io` / tenant `performance`  
**Surface:** `/ccx/internalapi/orgchart/v1/{tenant}`  
**Version:** 4.1 · **Date:** 2026-08-04  
**Status:** `READY FOR SKYLAB EXECUTION`  
**Canonical source:** this file (Markdown). Confluence page must match.

> **SUV (optional):** Rehearse org setup and OAuth on a SUV before Skylab. SUV results are **not** official evidence and **not** used for sign-off.

**Companion (design review):** `docs/research/ORG-21922-implementation-security-review.md`

**Status legend:** `NOT RUN` · `PASS` · `FAIL` · `BLOCKED` · `NEEDS INVESTIGATION`

---

## Table of contents

1. [Purpose and scope](#1-purpose-and-scope)  
2. [Security model](#2-security-model)  
3. [Knowledge layers](#3-knowledge-layers)  
4. [API endpoints in scope](#4-api-endpoints-in-scope)  
5. [Personas](#5-personas)  
6. [Test data (Organization Visibility)](#6-test-data-organization-visibility)  
7. [Skylab preconditions](#7-skylab-preconditions)  
8. [Evidence requirements](#8-evidence-requirements)  
9. [Execution strategy](#9-execution-strategy)  
10. [Endpoint specifications and test cases](#10-endpoint-specifications-and-test-cases)  
11. [Cross-endpoint consistency tests](#11-cross-endpoint-consistency-tests)  
12. [Execution summary](#12-execution-summary)  
13. [HTTP contract record](#13-http-contract-record)  
14. [Sign-off gates](#14-sign-off-gates)  
15. [Defect handling](#15-defect-handling)  
16. [References](#16-references)  
17. [Appendix — superseded v1 cases](#17-appendix--superseded-v1-cases)

---

## 1. Purpose and scope

### 1.1 Purpose

Execute the **complete security validation** of the Org Chart REST API (`orgchart` v1) in **Skylab**, validating:

- **Organization Visibility** enforcement (`Everyone` vs `Role Assignees`) across all supported endpoints  
- **Object-level authorization** — direct WID access, parent/children traversal, cross-endpoint consistency  
- **Non-disclosure** of hidden organizations, workers, relationships, counts, and excessive PII  
- **Prompt and filter** behaviour without authorization bypass  

### 1.2 In scope — six API surfaces

| # | Endpoint |
|---|----------|
| 1 | `GET /navigables/{ID}` *(security-review name: **self**)* |
| 2 | `GET /navigables/{ID}/children` |
| 3 | `GET /navigables/{ID}/parent` |
| 4 | `GET /values/orgChartPrompts/workers` |
| 5 | `GET /values/orgChartPrompts/organizations` |
| 6 | `GET /navigables/{ID}/children?navigableFilter=…` |

Supporting prompt for filter WIDs: `GET /values/orgChartPrompts/navigableFilters/` (setup only, not a seventh validation surface).

### 1.3 Out of scope

- Local Org Chart API Tester application security  
- Preview and Production environments  
- Cross-tenant isolation (platform responsibility)  
- Write operations (API is read-only)  
- `positions` prompt (removed in v1 — expect 404)  
- Performance/load ([ORG-21938](https://jira2.workday.com/browse/ORG-21938)) except where pagination affects security enforcement  
- Domain-gate variation (`Reports: Navigate Organization`) — held constant on Skylab via All Users  

---

## 2. Security model

### 2.1 Layered controls

| Layer | Control | Role in this plan |
|-------|---------|-------------------|
| L0 | Toggle ORG-21934 | Must be ON |
| L1 | **API entry gate** — `Reports: Navigate Organization` | Held **constant** via Skylab **All Users** SG; not varied during validation |
| L2 | **Organization Visibility** — `Everyone` / `Role Assignees` | **Primary authorization model under validation** |
| L3 | Traversal / SCR instance resolution | Validated on `/children` and `/parent`; singular binding on self |
| L4 | CRF field-level domains | Validated for excess PII on authorized responses |
| Prompts | Workers, organizations, navigableFilters | Validated per §10.4–10.6 |

### 2.2 Organization Visibility matrix

For **every endpoint**, tests cover:

| Organization Visibility | Authorized Persona | Unauthorized Persona | Expected visibility |
|---------------------------|-------------------|----------------------|---------------------|
| **Everyone** | P-A and P-B | — | Both personas receive equivalent results |
| **Role Assignees** | Role assignee (P-A or P-B per org) | Non-assignee | Assignee receives intended payload; Unauthorized Persona must not receive assignee-equivalent payload |

### 2.3 “Self” alias

There is **no** separate `GET /self` route. **Self** = `GET /navigables/{ID}` (direct navigable WID lookup). This endpoint carries the highest BOLA risk and is validated first within each persona pass.

---

## 3. Knowledge layers

### 3.1 Implementation context (design review reference)

Reference: `docs/research/ORG-21922-implementation-security-review.md` (conclusions unchanged).

| Topic | Design-review finding | Validation focus |
|-------|----------------------|------------------|
| Navigable class | Not contextually secured; discriminator CRFs use *Public Reporting Items* | Organization Visibility must enforce on self |
| Singular RSMB | Resolves any Navigable WID (`This Instance(GSS)(public)`) | Unauthorized Persona denied on Role Assignees WIDs |
| `/children` | Traversal-method org visibility applied | Hidden children absent from `data[]` and `total` |
| `/parent` | Parent security evaluated (`suppressParentSecurityEvaluation = false`) | Hidden parents absent for Unauthorized Persona |
| Invalid WID | Returns **404** (smoke-confirmed on Skylab) | Baseline for negative tests |
| `navigableFilter` | Additive selection; navigableFilters prompt unsecured | Filter must not bypass Organization Visibility |

### 3.2 Validation criteria

| Scenario | Pass condition |
|----------|----------------|
| Org **Everyone** | P-A and P-B receive equivalent visibility on all endpoints |
| Org **Role Assignees**, Authorized Persona | HTTP 200 with intended payload |
| Org **Role Assignees**, Unauthorized Persona | No assignee-equivalent payload; record HTTP status in §13 |
| Hidden org/worker (Role Assignees, not assigned) | Absent from prompts, children, parent; denied on self |
| Cross-endpoint | Same WID: identical visibility verdict on self, children, parent, prompts |
| `navigableFilter` | Changes selection only; never bypasses Organization Visibility |
| Pagination `total` | Reflects caller-visible set only |
| `hasParent` / `hasChildren` | Reflect caller-visible relations only |

### 3.3 Validation coverage map

| ID | Validates | Test IDs |
|----|-----------|----------|
| V-01 | All Users SG grants API access on Skylab | OC-NAV-001 |
| V-02 | Role Assignees enforced on self | OC-NAV-004 |
| V-03 | Role Assignees enforced on children traversal | OC-CHILD-004, OC-CHILD-006 |
| V-04 | Role Assignees enforced on parent traversal | OC-PARENT-002 |
| V-05 | Prompts respect Organization Visibility | OC-ORG-003, OC-WRK-003 |
| V-06 | Filter does not bypass Organization Visibility | OC-FLT-003, OC-FLT-004 |
| V-07 | Inaccessible WID indistinguishable from nonexistent WID | OC-NAV-009 |
| V-08 | Metadata flags do not leak hidden relationships | OC-NAV-010 |

---

## 4. API endpoints in scope

| Endpoint | Tester ID | Primary risks |
|----------|-----------|---------------|
| `GET /navigables/{ID}` | `get_navigable` | BOLA, existence oracle, relationship metadata, PII |
| `GET /navigables/{ID}/children` | `get_children` | Enumeration, mixed visibility, pagination, counts |
| `GET /navigables/{ID}/parent` | `get_parent` | Hidden parent disclosure, upward traversal |
| `GET /values/orgChartPrompts/workers` | `prompt_workers` | Worker enumeration, PII in descriptors |
| `GET /values/orgChartPrompts/organizations` | `prompt_organizations` | Org enumeration, consistency vs self |
| `GET /navigables/{ID}/children?navigableFilter=` | `get_children` + filter | Filter bypass, invalid filter fallback |

---

## 5. Personas

### 5.1 Why two personas

Official Skylab validation uses **exactly two personas** (P-A and P-B):

- **`Reports: Navigate Organization`** is the API entry gate. Both personas belong to **All Users**, which grants this domain on Skylab. The entry gate is **not** varied during validation.
- **Organization Visibility** is the primary authorization model under validation. Tests require an **Authorized Persona** (role assignee) and an **Unauthorized Persona** (non-assignee) for each Role Assignees org.
- **Everyone** orgs require both personas to receive equivalent results, confirming no persona-specific drift.
- Additional personas from earlier drafts (domain-denied users, multi-group matrices) are **not** part of the official Skylab validation strategy.

### 5.2 Persona definitions

| Persona | Symbol | Skylab account | Security groups | Role in tests |
|---------|--------|----------------|-----------------|---------------|
| **Persona A** | `P-A` | *(fill on Skylab)* | All Users; role assignee on P-A Role Assignees orgs | **Authorized Persona** on `ORG-RA-A`, `ORG-PRA`, `ORG-CRA`; baseline for Everyone |
| **Persona B** | `P-B` | *(fill on Skylab)* | All Users; not assignee on P-A Role Assignees orgs | **Unauthorized Persona** on P-A Role Assignees orgs; **Authorized Persona** on `ORG-RA-B` |

**OAuth:** separate refresh token per persona. **Disconnect** the tester between persona switches.

---

## 6. Test data (Organization Visibility)

### 6.1 Organization objects

| Organization | Symbol | Organization Visibility | Role Assignee | Parent | Children / subordinates | Purpose | Visible to P-A | Visible to P-B |
|--------------|--------|-------------------------|---------------|--------|-------------------------|---------|----------------|----------------|
| OC-SEC Everyone Root | `ORG-EV` | Everyone | — | — | optional workers | Baseline Everyone | Yes | Yes |
| OC-SEC RA Worker A | `ORG-RA-A` | Role Assignees | P-A | — | — | Direct Role Assignees self test | Yes | No |
| OC-SEC RA Worker B | `ORG-RA-B` | Role Assignees | P-B | — | — | Mirror Role Assignees test | No | Yes |
| OC-SEC RA None | `ORG-RA-0` | Role Assignees | *(none)* | — | — | No assignees edge case | No | No |
| OC-SEC Parent RA | `ORG-PRA` | Role Assignees | P-A | — | `ORG-CRA`, `ORG-CEV` | Hierarchy parent | Yes | No |
| OC-SEC Child RA | `ORG-CRA` | Role Assignees | P-A | `ORG-PRA` | — | Role Assignees child under Role Assignees parent | Yes | No |
| OC-SEC Child Everyone | `ORG-CEV` | Everyone | — | `ORG-PRA` | — | Everyone child under Role Assignees parent | Yes | Validate OC-CHILD-007/008 |
| OC-SEC Mixed Parent | `ORG-MIX` | Everyone | — | — | visible + Role Assignees children | Mixed children | Yes | Partial (visible subset only) |
| OC-SEC Large Parent | `ORG-BIG` | Everyone | — | — | 100+ children, some Role Assignees | Pagination security | Yes | Partial (visible subset only) |

### 6.2 Worker and position objects

| Object | Symbol | Under org | Organization Visibility context | Purpose | Visible to P-A | Visible to P-B |
|--------|--------|-----------|-----------------------------------|---------|----------------|----------------|
| Worker in Everyone org | `WKR-EV` | `ORG-EV` | Everyone parent | Worker self / children | Yes | Yes |
| Worker in Role Assignees org | `WKR-RA` | `ORG-RA-A` | Role Assignees parent | Hidden worker BOLA | Yes | No |
| Unfilled position visible | `POS-VIS` | `ORG-EV` | Everyone | Position subtype | Yes | Yes |
| Unfilled position hidden | `POS-HID` | `ORG-RA-A` | Role Assignees | Position BOLA | Yes | No |

### 6.3 Prompt and filter data

| Symbol | Source | Purpose |
|--------|--------|---------|
| `FLT-OK` | `navigableFilters` prompt (e.g. Open Positions) | Valid `navigableFilter` WID |
| `FLT-BAD` | Bogus / unauthorized WID | Invalid filter fallback test |
| `SEARCH-MIX` | Known string matching visible + hidden names | Enumeration boundary test |
| `WID-BAD` | Malformed ID | Negative test |
| `WID-GHOST` | Valid-format nonexistent 32-hex WID | Existence-oracle baseline |

### 6.4 WID worksheet (fill on Skylab)

| Symbol | WID | Recorded by | Date |
|--------|-----|-------------|------|
| `ORG-EV` | | | |
| `ORG-RA-A` | | | |
| `ORG-RA-B` | | | |
| `ORG-RA-0` | | | |
| `ORG-PRA` | | | |
| `ORG-CRA` | | | |
| `ORG-CEV` | | | |
| `ORG-MIX` | | | |
| `ORG-BIG` | | | |
| `WKR-EV` | | | |
| `WKR-RA` | | | |
| `POS-VIS` | | | |
| `POS-HID` | | | |
| `FLT-OK` | | | |
| `FLT-BAD` | | | |

---

## 7. Skylab preconditions

| # | Item |
|---|------|
| 1 | Toggle ORG-21934 ON |
| 2 | Host `org.skylab.inday.io`, tenant `performance`, **internalapi** surface |
| 3 | §6 hierarchy created and WIDs recorded in §6.4 |
| 4 | OAuth tokens for P-A and P-B |
| 5 | Org Chart API Tester — Live mode |
| 6 | Evidence folder: `evidence/org-21922/{Test-ID}/` |

```bash
make start   # http://127.0.0.1:8000
```

Judge **Upstream (Skylab)** HTTP status — not proxy HTTP 200 on `POST /api/execute`.

---

## 8. Evidence requirements

Per test, capture:

- [ ] Skylab environment (`org.skylab.inday.io` / `performance`)  
- [ ] Date and time (UTC)  
- [ ] Persona (P-A / P-B) and Skylab account name  
- [ ] Organization Visibility configuration screenshot  
- [ ] Tested WID(s)  
- [ ] HTTP status (**upstream**)  
- [ ] Full response body (JSON)  
- [ ] `wd-stat-request-id`  
- [ ] Screenshot of tester UI  
- [ ] Trace link (if available)  
- [ ] Secrets redacted (no tokens/passwords)  

---

## 9. Execution strategy

Execute tests in the following order. Complete each phase before moving to the next. Record results in the execution tables (§10–§11) and HTTP observations in §13.

| Phase | Action | Test IDs |
|-------|--------|----------|
| 1 | **Validate Everyone visibility** — confirm P-A and P-B receive equivalent results on Everyone orgs | OC-NAV-001/002, OC-CHILD-001/002, OC-WRK-001/002, OC-ORG-001/002 |
| 2 | **Validate Role Assignees — Authorized Persona** — confirm assignee receives intended payloads | OC-NAV-003/005, OC-CHILD-003/005/007, OC-PARENT-001/003, OC-WRK-004, OC-ORG-004 |
| 3 | **Validate Role Assignees — Unauthorized Persona** — confirm non-assignee is denied or receives empty/filtered results | OC-NAV-004/006/009–012, OC-CHILD-004/006/008/009, OC-PARENT-002/004/005, OC-WRK-003/005/006, OC-ORG-003/005/006 |
| 4 | **Validate direct object access** — complete remaining self (`/navigables/{ID}`) cases | OC-NAV-007/008/010/013 |
| 5 | **Validate children traversal** — mixed visibility, pagination, worker children | OC-CHILD-010/011/012 |
| 6 | **Validate parent traversal** — upward disclosure | *(covered in phases 2–3; confirm OC-PARENT complete)* |
| 7 | **Validate prompts** — workers and organizations enumeration | *(covered in phases 1–3; confirm OC-WRK and OC-ORG complete)* |
| 8 | **Validate navigableFilter** — filter boundary, bypass, invalid filter | OC-FLT-001–006 |
| 9 | **Cross-endpoint consistency** — same WID, same verdict across endpoints | OC-X-001–004 |
| 10 | **Record HTTP contract observations** — document denial status codes and body shapes | §13 |

**P0 gate:** Phases 2–3 must include OC-NAV-004, OC-CHILD-004, OC-PARENT-002, OC-ORG-003, OC-WRK-003, OC-FLT-004, and OC-X-001 before sign-off.

---

## 10. Endpoint specifications and test cases

Each endpoint section follows the same layout: Security Objective → Risks → Preconditions → Required Test Data → Personas → Test Steps → Expected Behaviour → Expected HTTP Behaviour → Expected Payload Behaviour → Execution Table → Pass Criteria → Fail Criteria.

---

### 10.1 `GET /navigables/{ID}` (self)

#### Security Objective

Validate Organization Visibility and object-level authorization on direct navigable WID access.

#### Risks

- BOLA — direct access to hidden org/worker/position WIDs (T-D01)  
- Existence oracle — response differs for inaccessible vs nonexistent WID (T-D02)  
- Relationship metadata leak via `hasParent` / `hasChildren` (T-D05)  
- Manager PII exposure (T-D06)  
- Field over-exposure beyond Layer-4 stripping (T-D07)  

#### Preconditions

- Target WID recorded in §6.4  
- Persona OAuth token valid; correct persona connected in tester  
- Toggle ORG-21934 ON  

#### Required Test Data

`ORG-EV`, `ORG-RA-A`, `ORG-RA-B`, `ORG-RA-0`, `WKR-RA`, `WKR-EV`, `POS-HID`, `WID-GHOST`

#### Personas

| Case type | Persona |
|-----------|---------|
| Everyone orgs | P-A and P-B (equivalent results) |
| Role Assignees — Authorized Persona | P-A on `ORG-RA-A`; P-B on `ORG-RA-B` |
| Role Assignees — Unauthorized Persona | P-B on `ORG-RA-A`; P-A on `ORG-RA-B` |

#### Test Steps

1. Connect tester as target persona.  
2. Select `get_navigable`.  
3. Set `ID` to tested WID from §6.4.  
4. Send request; record **upstream** HTTP status, body, and `wd-stat-request-id`.  
5. For OC-NAV-009, repeat with `WID-GHOST` and compare responses.  

#### Expected Behaviour

- **Everyone:** both personas receive full org/worker detail.  
- **Role Assignees — Authorized Persona:** full detail for assigned org/worker.  
- **Role Assignees — Unauthorized Persona:** denied or empty; no assignee-equivalent descriptor, manager, or hierarchy flags.  
- **Existence oracle (OC-NAV-009):** inaccessible Role Assignees WID response matches nonexistent WID response.  

#### Expected HTTP Behaviour

- Malformed / nonexistent WID → **404**  
- Role Assignees org, Unauthorized Persona → record observed status in §13  
- Everyone org, both personas → **200**  

#### Expected Payload Behaviour

- **Authorized:** full `detail` per navigable subtype  
- **Unauthorized:** no `descriptor`, `name`, `manager`, or hierarchy flags that reveal the protected object  
- **Layer-4 (OC-NAV-013):** restricted fields stripped on worker responses  

#### Execution Table — OC-NAV

| Test ID | Endpoint | Visibility | Organization WID | Parent WID | Child WID | Expected Result | Actual Result | HTTP Status | Request ID | Tested WID | Persona | Evidence | Pass/Fail | Notes |
|---------|----------|------------|------------------|------------|-----------|-----------------|---------------|-------------|------------|------------|---------|----------|-----------|-------|
| OC-NAV-001 | `GET /navigables/{ID}` | Everyone (`ORG-EV`) | | — | — | 200; `type=ORGANIZATION`; descriptor matches | | | | | P-A | | | P0 |
| OC-NAV-002 | `GET /navigables/{ID}` | Everyone (`ORG-EV`) | | — | — | Same payload as OC-NAV-001 | | | | | P-B | | | P0 |
| OC-NAV-003 | `GET /navigables/{ID}` | Role Assignees (`ORG-RA-A`) | | — | — | 200; full org detail | | | | | P-A | | | P0 · Authorized Persona |
| OC-NAV-004 | `GET /navigables/{ID}` | Role Assignees (`ORG-RA-A`) | | — | — | Denied; no descriptor/manager/hasChildren leak | | | | | P-B | | | **P0** · Unauthorized Persona · V-02 |
| OC-NAV-005 | `GET /navigables/{ID}` | Role Assignees (`ORG-RA-B`) | | — | — | 200; full org detail | | | | | P-B | | | P0 · Authorized Persona |
| OC-NAV-006 | `GET /navigables/{ID}` | Role Assignees (`ORG-RA-B`) | | — | — | Denied | | | | | P-A | | | P0 · Unauthorized Persona |
| OC-NAV-007 | `GET /navigables/{ID}` | Role Assignees (`ORG-RA-0`) | | — | — | Denied | | | | | P-A | | | P1 |
| OC-NAV-008 | `GET /navigables/{ID}` | Role Assignees (`ORG-RA-0`) | | — | — | Denied | | | | | P-B | | | P1 |
| OC-NAV-009 | `GET /navigables/{ID}` | Role Assignees (`ORG-RA-A`) | | — | — | Response matches `WID-GHOST` (no existence oracle) | | | | | P-B | | | P0 · V-07 |
| OC-NAV-010 | `GET /navigables/{ID}` | Role Assignees (`ORG-RA-A`) | | — | — | `hasParent`/`hasChildren` do not reveal hidden relations | | | | | P-B | | | P1 · V-08 |
| OC-NAV-011 | `GET /navigables/{ID}` | Worker (`WKR-RA`) | | — | — | Denied; no worker identity leak | | | | | P-B | | | P0 |
| OC-NAV-012 | `GET /navigables/{ID}` | Position (`POS-HID`) | | — | — | Denied or empty; no position detail disclosed | | | | | P-B | | | P0 |
| OC-NAV-013 | `GET /navigables/{ID}` | Everyone worker (`WKR-EV`) | | — | — | 200; restricted fields stripped per Layer-4 | | | | | P-B | | | P2 |

#### Pass Criteria

- Authorized Persona receives intended payload on assigned Role Assignees and Everyone objects.  
- Unauthorized Persona receives no assignee-equivalent payload.  
- OC-NAV-009: inaccessible and nonexistent WID responses are indistinguishable.  

#### Fail Criteria

- Unauthorized Persona receives `descriptor`, `name`, `manager`, or hierarchy flags for a protected object.  
- Existence oracle: different HTTP status or body shape for inaccessible vs `WID-GHOST`.  

---

### 10.2 `GET /navigables/{ID}/children`

#### Security Objective

Validate downward traversal enforces Organization Visibility on child navigables.

#### Risks

- Hidden child enumeration in `data[]` (T-D04)  
- Mixed visibility parent returns protected children (T-04)  
- Pagination exposes hidden nodes or unstable offsets (T-E02)  
- `total` count reveals hidden children (T-E02)  
- Worker/position children not filtered by Organization Visibility  

#### Preconditions

- Parent WID recorded in §6.4 with configured subordinates  
- Persona OAuth token valid  

#### Required Test Data

`ORG-EV`, `ORG-PRA`, `ORG-CRA`, `ORG-CEV`, `ORG-MIX`, `ORG-BIG`, `ORG-EV` (worker children)

#### Personas

| Case type | Persona |
|-----------|---------|
| Everyone parent | P-A and P-B |
| Role Assignees parent — Authorized Persona | P-A on `ORG-PRA` |
| Role Assignees parent — Unauthorized Persona | P-B on `ORG-PRA` |
| Mixed / pagination | P-B (Unauthorized Persona on subset) |

#### Test Steps

1. Connect as target persona.  
2. Select `get_children`; set `ID` to parent WID.  
3. Send request; record `data[].id`, `total`, and upstream HTTP status.  
4. For pagination (OC-CHILD-010), iterate `offset`/`limit` across all pages.  
5. Compare results between P-A and P-B on Everyone parents.  

#### Expected Behaviour

- Only caller-visible children appear in `data[]`.  
- `total` equals the count of visible children for the calling persona.  
- Role Assignees children absent for Unauthorized Persona even when parent is Everyone (`ORG-CEV` under `ORG-PRA`).  

#### Expected HTTP Behaviour

- Authorized traversal → **200** with filtered set  
- Unauthorized Persona on Role Assignees parent → record observed status in §13  

#### Expected Payload Behaviour

- `data[]` contains only navigables visible to the calling persona  
- No hidden WIDs on any pagination page  
- `total` does not include hidden children  

#### Execution Table — OC-CHILD

| Test ID | Endpoint | Visibility | Organization WID | Parent WID | Child WID | Expected Result | Actual Result | HTTP Status | Request ID | Tested WID | Persona | Evidence | Pass/Fail | Notes |
|---------|----------|------------|------------------|------------|-----------|-----------------|---------------|-------------|------------|------------|---------|----------|-----------|-------|
| OC-CHILD-001 | `/children` | Parent Everyone (`ORG-EV`) | — | | — | 200; children returned | | | | | P-A | | | P0 |
| OC-CHILD-002 | `/children` | Parent Everyone (`ORG-EV`) | — | | — | Same set as OC-CHILD-001 | | | | | P-B | | | P0 |
| OC-CHILD-003 | `/children` | Parent Role Assignees (`ORG-PRA`) | — | | — | 200; includes `ORG-CRA`, `ORG-CEV` | | | | | P-A | | | P0 · Authorized Persona |
| OC-CHILD-004 | `/children` | Parent Role Assignees (`ORG-PRA`) | — | | — | Denied or empty; no children leak | | | | | P-B | | | **P0** · Unauthorized Persona · V-03 |
| OC-CHILD-005 | `/children` | Child Role Assignees in list | — | `ORG-PRA` | `ORG-CRA` | `ORG-CRA` in `data[]` | | | | | P-A | | | P0 |
| OC-CHILD-006 | `/children` | Child Role Assignees in list | — | `ORG-PRA` | `ORG-CRA` | `ORG-CRA` absent from `data[]` | | | | | P-B | | | P0 |
| OC-CHILD-007 | `/children` | Child Everyone in list | — | `ORG-PRA` | `ORG-CEV` | `ORG-CEV` in `data[]` | | | | | P-A | | | P1 |
| OC-CHILD-008 | `/children` | Child Everyone in list | — | `ORG-PRA` | `ORG-CEV` | Document observed visibility for P-B | | | | | P-B | | | P1 |
| OC-CHILD-009 | `/children` | Mixed (`ORG-MIX`) | — | | — | Hidden children absent; `total` = visible count only | | | | | P-B | | | P0 |
| OC-CHILD-010 | `/children` | Pagination (`ORG-BIG`) | — | | — | No hidden nodes on any page; stable offsets | | | | | P-B | | | P1 |
| OC-CHILD-011 | `/children` | Count metadata (`ORG-MIX`) | — | | — | `total` equals visible children count for P-B | | | | | P-B | | | P1 |
| OC-CHILD-012 | `/children` | Worker children | — | `ORG-EV` | `WKR-*` | Worker children match Organization Visibility rules | | | | | P-B | | | P1 |

#### Pass Criteria

- `data[]` and `total` reflect only caller-visible children.  
- Unauthorized Persona does not receive Role Assignees child WIDs.  

#### Fail Criteria

- Hidden child WID appears in `data[]` or `total` exceeds visible count.  

---

### 10.3 `GET /navigables/{ID}/parent`

#### Security Objective

Validate upward traversal enforces Organization Visibility on parent navigables.

#### Risks

- Hidden parent disclosure in `data[]` (T-D04)  
- Relationship inference from partial parent metadata  

#### Preconditions

- Child WID with known parent chain recorded in §6.4  
- Persona OAuth token valid  

#### Required Test Data

`ORG-CEV`, `ORG-CRA`, `ORG-PRA`, `CHILD-HP` (hidden-parent scenario)

#### Personas

| Case type | Persona |
|-----------|---------|
| Role Assignees parent — Authorized Persona | P-A |
| Role Assignees parent — Unauthorized Persona | P-B |

#### Test Steps

1. Connect as target persona.  
2. Select `get_parent`; set `ID` to child WID.  
3. Send request; check whether parent WID (`ORG-PRA`) appears in `data[]`.  
4. Record upstream HTTP status and body.  

#### Expected Behaviour

- Authorized Persona sees Role Assignees parent in `data[]`.  
- Unauthorized Persona does not receive parent descriptor or WID for Role Assignees parent.  

#### Expected HTTP Behaviour

- Authorized traversal → **200** with parent in `data[]`  
- Unauthorized Persona → record observed status in §13  

#### Expected Payload Behaviour

- No Role Assignees parent `id` or `descriptor` for Unauthorized Persona  
- Hidden parent (`CHILD-HP`) not disclosed  

#### Execution Table — OC-PARENT

| Test ID | Endpoint | Visibility | Organization WID | Parent WID | Child WID | Expected Result | Actual Result | HTTP Status | Request ID | Tested WID | Persona | Evidence | Pass/Fail | Notes |
|---------|----------|------------|------------------|------------|-----------|-----------------|---------------|-------------|------------|------------|---------|----------|-----------|-------|
| OC-PARENT-001 | `/parent` | Parent Role Assignees | — | `ORG-PRA` | `ORG-CEV` | `ORG-PRA` in `data[]` | | | | | P-A | | | P0 · Authorized Persona |
| OC-PARENT-002 | `/parent` | Parent Role Assignees | — | `ORG-PRA` | `ORG-CEV` | Parent absent or denied | | | | | P-B | | | **P0** · Unauthorized Persona · V-04 |
| OC-PARENT-003 | `/parent` | Parent Role Assignees | — | `ORG-PRA` | `ORG-CRA` | `ORG-PRA` in `data[]` | | | | | P-A | | | P1 |
| OC-PARENT-004 | `/parent` | Parent Role Assignees | — | `ORG-PRA` | `ORG-CRA` | Parent absent or denied | | | | | P-B | | | P1 |
| OC-PARENT-005 | `/parent` | Hidden parent | — | hidden | `CHILD-HP` | Hidden parent not disclosed | | | | | P-B | | | P1 |

#### Pass Criteria

- Unauthorized Persona does not receive Role Assignees parent in `data[]`.  

#### Fail Criteria

- Parent WID or descriptor leaked to Unauthorized Persona.  

---

### 10.4 `GET /values/orgChartPrompts/workers`

#### Security Objective

Validate the workers prompt does not enumerate workers outside the caller's Organization Visibility scope.

#### Risks

- Worker enumeration via search (T-D03)  
- PII in descriptors  
- Inconsistency with navigable self visibility  

#### Preconditions

- `WKR-RA` (hidden to P-B) and `WKR-EV` recorded in §6.4  
- Persona OAuth token valid  

#### Required Test Data

`WKR-EV`, `WKR-RA`, `SEARCH-MIX`

#### Personas

| Case type | Persona |
|-----------|---------|
| Everyone worker | P-A and P-B |
| Role Assignees worker — Unauthorized Persona | P-B on `WKR-RA` |
| Role Assignees worker — Authorized Persona | P-A on `WKR-RA` |

#### Test Steps

1. Connect as target persona.  
2. Select `prompt_workers`.  
3. Set `search` to exact name, partial name, or `SEARCH-MIX` as specified per test.  
4. Send request; inspect `data[]` for `WKR-RA` and `WKR-EV`.  
5. For OC-WRK-005, set `limit=1000` and scan full result set.  

#### Expected Behaviour

- `WKR-EV` findable by both personas.  
- `WKR-RA` present for P-A; **absent** for P-B across all search strategies.  

#### Expected HTTP Behaviour

- **200** for all prompt requests  

#### Expected Payload Behaviour

- Results contain `{id, descriptor}` only  
- No hidden worker entries for Unauthorized Persona  
- No excess PII beyond descriptor  

#### Execution Table — OC-WRK

| Test ID | Endpoint | Visibility | Organization WID | Parent WID | Child WID | Expected Result | Actual Result | HTTP Status | Request ID | Tested WID | Persona | Evidence | Pass/Fail | Notes |
|---------|----------|------------|------------------|------------|-----------|-----------------|---------------|-------------|------------|------------|---------|----------|-----------|-------|
| OC-WRK-001 | `prompt_workers` | Everyone worker | — | — | — | 200; `WKR-EV` findable by name | | | | | P-A | | | P1 |
| OC-WRK-002 | `prompt_workers` | Everyone worker | — | — | — | Same as OC-WRK-001 | | | | | P-B | | | P1 |
| OC-WRK-003 | `prompt_workers` | Role Assignees worker (`WKR-RA`) | — | — | — | `WKR-RA` absent from results | | | | | P-B | | | **P0** · Unauthorized Persona · V-05 |
| OC-WRK-004 | `prompt_workers` | Role Assignees worker | — | — | — | `WKR-RA` present | | | | | P-A | | | P1 · Authorized Persona |
| OC-WRK-005 | `prompt_workers` | Broad search | — | — | — | No hidden workers in `limit=1000` harvest | | | | | P-B | | | P2 |
| OC-WRK-006 | `prompt_workers` | 1-char search | — | — | — | Results scoped; no excess PII | | | | | P-B | | | P2 |

#### Pass Criteria

- `WKR-RA` absent from all P-B prompt results.  

#### Fail Criteria

- Hidden worker `{id, descriptor}` returned to Unauthorized Persona.  

---

### 10.5 `GET /values/orgChartPrompts/organizations`

#### Security Objective

Validate the organizations prompt enforces Organization Visibility consistently with navigable self access.

#### Risks

- Organization enumeration via search (T-D03)  
- Inconsistency — org in prompt but denied on self (T-E03)  

#### Preconditions

- `ORG-RA-A` hidden to P-B; `ORG-EV` visible to both personas  
- Persona OAuth token valid  

#### Required Test Data

`ORG-EV`, `ORG-RA-A`, `SEARCH-MIX`

#### Personas

| Case type | Persona |
|-----------|---------|
| Everyone org | P-A and P-B |
| Role Assignees org — Unauthorized Persona | P-B on `ORG-RA-A` |
| Role Assignees org — Authorized Persona | P-A on `ORG-RA-A` |

#### Test Steps

1. Connect as target persona.  
2. Select `prompt_organizations`.  
3. Search exact name, partial prefix, or `SEARCH-MIX` as specified.  
4. Inspect `data[]` for `ORG-RA-A` and `ORG-EV`.  

#### Expected Behaviour

- `ORG-EV` findable by both personas.  
- `ORG-RA-A` present for P-A; **absent** for P-B.  
- Prompt visibility matches self endpoint verdict (OC-X-001).  

#### Expected HTTP Behaviour

- **200** for all prompt requests  

#### Expected Payload Behaviour

- Only organizations visible to the calling persona appear in results  
- No prefix leak of hidden org names  

#### Execution Table — OC-ORG

| Test ID | Endpoint | Visibility | Organization WID | Parent WID | Child WID | Expected Result | Actual Result | HTTP Status | Request ID | Tested WID | Persona | Evidence | Pass/Fail | Notes |
|---------|----------|------------|------------------|------------|-----------|-----------------|---------------|-------------|------------|------------|---------|----------|-----------|-------|
| OC-ORG-001 | `prompt_organizations` | Everyone (`ORG-EV`) | `ORG-EV` | — | — | 200; org findable | | | | | P-A | | | P1 |
| OC-ORG-002 | `prompt_organizations` | Everyone (`ORG-EV`) | `ORG-EV` | — | — | Same as OC-ORG-001 | | | | | P-B | | | P1 |
| OC-ORG-003 | `prompt_organizations` | Role Assignees (`ORG-RA-A`) | `ORG-RA-A` | — | — | `ORG-RA-A` absent from results | | | | | P-B | | | **P0** · Unauthorized Persona · V-05 |
| OC-ORG-004 | `prompt_organizations` | Role Assignees (`ORG-RA-A`) | `ORG-RA-A` | — | — | Org present | | | | | P-A | | | P1 · Authorized Persona |
| OC-ORG-005 | `prompt_organizations` | Broad `SEARCH-MIX` | — | — | — | No Role Assignees orgs in harvest | | | | | P-B | | | P2 |
| OC-ORG-006 | `prompt_organizations` | Partial name | `ORG-RA-A` | — | — | No prefix leak of hidden org | | | | | P-B | | | P1 |

#### Pass Criteria

- `ORG-RA-A` absent from all P-B prompt results.  
- Prompt and self visibility consistent for the same WID.  

#### Fail Criteria

- Hidden org appears in prompt for Unauthorized Persona.  
- Org findable in prompt but full detail returned on self for Unauthorized Persona.  

---

### 10.6 `GET /navigables/{ID}/children?navigableFilter=…`

#### Security Objective

Validate `navigableFilter` changes child selection only and does not bypass Organization Visibility.

#### Risks

- Filter bypass — hidden nodes exposed after filter (T-E01)  
- Invalid filter returns unfiltered superset (T-E14)  
- Additive filter nodes not subject to Organization Visibility  

#### Preconditions

- `FLT-OK` WID recorded from `navigableFilters` prompt (OC-FLT-006)  
- Parent `ORG-MIX` or `ORG-PRA` recorded in §6.4  
- Persona OAuth token valid  

#### Required Test Data

`ORG-MIX`, `ORG-PRA`, `FLT-OK`, `FLT-BAD`

#### Personas

| Case type | Persona |
|-----------|---------|
| Filter boundary | P-A and P-B on `ORG-MIX` |
| Role Assignees bypass attempt | P-B on `ORG-PRA` |
| Invalid filter | P-B on `ORG-MIX` |

#### Test Steps

1. Connect as target persona.  
2. Select `get_children`; set `ID` to parent WID.  
3. Add `navigableFilter` parameter (`FLT-OK` or `FLT-BAD`).  
4. Send request; compare filtered `data[]` against unfiltered results for same persona.  
5. For OC-FLT-006, call `navigableFilters` prompt and record `FLT-OK` WID.  

#### Expected Behaviour

- Filtered results are a subset of (or equal to) the unfiltered visible set for the calling persona.  
- Filter does not expose Role Assignees children to Unauthorized Persona.  
- Invalid filter (`FLT-BAD`) returns error or empty — never an unfiltered superset.  

#### Expected HTTP Behaviour

- Valid filter → **200**  
- Invalid filter → record observed status in §13 (expect 400 or secured empty)  

#### Expected Payload Behaviour

- No visibility bypass via filter parameter  
- Additive nodes (e.g. Open Positions) subject to same Organization Visibility  

#### Execution Table — OC-FLT

| Test ID | Endpoint | Visibility | Organization WID | Parent WID | Child WID | Expected Result | Actual Result | HTTP Status | Request ID | Tested WID | Persona | Evidence | Pass/Fail | Notes |
|---------|----------|------------|------------------|------------|-----------|-----------------|---------------|-------------|------------|------------|---------|----------|-----------|-------|
| OC-FLT-001 | `/children?navigableFilter` | Parent `ORG-MIX` | — | `ORG-MIX` | — | 200; filtered ⊆ unfiltered visible | | | | | P-A | | | P1 |
| OC-FLT-002 | `/children?navigableFilter` | Parent `ORG-MIX` | — | `ORG-MIX` | — | No hidden nodes exposed by filter | | | | | P-B | | | P1 |
| OC-FLT-003 | `/children?navigableFilter=FLT-OK` | Parent Role Assignees | — | `ORG-PRA` | — | No Role Assignees children for Unauthorized Persona | | | | | P-B | | | **P0** · V-06 |
| OC-FLT-004 | `/children?navigableFilter=FLT-BAD` | Parent `ORG-MIX` | — | `ORG-MIX` | — | Error or empty — never unfiltered superset | | | | | P-B | | | **P0** |
| OC-FLT-005 | `/children?navigableFilter` | Additive check | — | `ORG-MIX` | — | Additive nodes visible only if authorized | | | | | P-A | | | P1 |
| OC-FLT-006 | `navigableFilters` prompt | Setup | — | — | — | Record `FLT-OK` WID | | | | | P-A | | | P2 · setup |

#### Pass Criteria

- Filtered `data[]` ⊆ unfiltered visible set for the calling persona.  
- Invalid filter does not return superset of unfiltered results.  

#### Fail Criteria

- Hidden navigable appears in filtered results for Unauthorized Persona.  
- `FLT-BAD` returns full unfiltered child list.  

---

## 11. Cross-endpoint consistency tests

Execute after all endpoint tables in §10 are complete.

| Test ID | Endpoints | Objective | Expected Result | Actual Result | HTTP Status | Request ID | Tested WID | Persona | Evidence | Pass/Fail | Notes |
|---------|-----------|-----------|-----------------|---------------|-------------|------------|------------|---------|----------|-----------|-------|
| OC-X-001 | self + children + parent + org prompt | `ORG-RA-A` visibility identical on all paths | Same deny/allow verdict across endpoints | | | | | P-B | | | **P0** |
| OC-X-002 | prompt_workers → self | WID from prompt → same visibility on self | Consistent verdict | | | | | P-B | | | P1 |
| OC-X-003 | children recurse + parent | Cannot reconstruct hidden subtree | No hidden graph recoverable | | | | | P-B | | | P1 |
| OC-X-004 | self (`ORG-CEV`) vs parent (`ORG-PRA`) | Everyone child does not expose Role Assignees parent | Parent hidden for Unauthorized Persona | | | | | P-B | | | P1 |

---

## 12. Execution summary (Skylab — official)

| Endpoint | Everyone | Role Assignees — Authorized Persona | Role Assignees — Unauthorized Persona | Overall Status |
|----------|----------|--------------------------------------|---------------------------------------|----------------|
| `GET /navigables/{ID}` | OC-NAV-001, 002 | OC-NAV-003, 005, 007–013 | OC-NAV-004, 006, 009–012 | NOT RUN |
| `GET /navigables/{ID}/children` | OC-CHILD-001, 002 | OC-CHILD-003, 005, 007, 010–012 | OC-CHILD-004, 006, 008, 009 | NOT RUN |
| `GET /navigables/{ID}/parent` | — | OC-PARENT-001, 003 | OC-PARENT-002, 004, 005 | NOT RUN |
| `GET /values/orgChartPrompts/workers` | OC-WRK-001, 002 | OC-WRK-004 | OC-WRK-003, 005, 006 | NOT RUN |
| `GET /values/orgChartPrompts/organizations` | OC-ORG-001, 002 | OC-ORG-004 | OC-ORG-003, 005, 006 | NOT RUN |
| `GET /children?navigableFilter` | OC-FLT-001, 005 | OC-FLT-001 | OC-FLT-002–004 | NOT RUN |
| Cross-endpoint | — | OC-X-001–004 | OC-X-001–004 | NOT RUN |

**Overall Skylab validation:** `NOT RUN`  
**P0 executed:** — / 7  
**P0 pass rate:** —  
**Executor:** — · **Completion date:** —  
**Open defects:** —

### P0 mandatory cases

OC-NAV-004 · OC-CHILD-004 · OC-PARENT-002 · OC-ORG-003 · OC-WRK-003 · OC-FLT-004 · OC-X-001

---

## 13. HTTP contract record

Record observed HTTP status and body shape during Skylab execution. This section is the single place for status codes that cannot be predetermined.

| Scenario | Test ID | Observed HTTP | Body shape | Recorded by | Date |
|----------|---------|---------------|------------|-------------|------|
| Role Assignees org, Unauthorized Persona, self | OC-NAV-004 | | | | |
| Role Assignees org, Unauthorized Persona, children | OC-CHILD-004 | | | | |
| Role Assignees parent, Unauthorized Persona, parent | OC-PARENT-002 | | | | |
| Inaccessible vs nonexistent WID | OC-NAV-009 | | | | |
| Invalid navigableFilter | OC-FLT-004 | | | | |

---

## 14. Sign-off gates (Skylab only)

| Gate | Criteria |
|------|----------|
| Setup | §6.4 WID worksheet complete; §5.2 Skylab accounts recorded |
| P0 | All 7 mandatory P0 cases executed with evidence |
| Security | No FAIL on Unauthorized Persona Role Assignees disclosure |
| Consistency | OC-X-001 PASS |
| Contract | §13 complete for all denial scenarios |
| Evidence | §8 checklist per test |

**Approver:** — · **Date:** —

---

## 15. Defect handling

Any FAIL that discloses hidden objects, relationships, counts, or PII → **Security bug** on Epic ORG-21726, linked to ORG-21922. Attach redacted Skylab evidence. Block GA until all P0 cases pass or are explicitly accepted by the security advocate.

---

## 16. References

| Document | Use |
|----------|-----|
| `docs/research/ORG-21922-implementation-security-review.md` | Layer model, threats T-D01–T-E03 |
| `docs/research/ORG-21922-tdd-reconciliation.md` | TDD vs implementation |
| `docs/research/ORG-21922-architect-summary.md` | Architect guidance |
| `docs/research/ORG-21922-security-test-plan.md` | Historical v1 (T-01–T-18) |
| Org Chart API Tester | `README.md` |

---

## 17. Appendix — superseded v1 cases

Historical mapping from v1 (`docs/research/ORG-21922-security-test-plan.md`) to v4.1:

| v1 | v4.1 equivalent |
|----|-----------------|
| T-01 hidden org self | OC-NAV-004 |
| T-02 hidden worker/position | OC-NAV-011, OC-NAV-012 |
| T-03 domain gate (no domain) | Out of scope — All Users on Skylab |
| T-04 mixed children | OC-CHILD-009 |
| T-05 hidden parent | OC-PARENT-005 |
| T-06 existence oracle | OC-NAV-009 |
| T-07 workers prompt | OC-WRK-003 |
| T-08 orgs prompt | OC-ORG-003 |
| T-09 broad harvest | OC-WRK-005, OC-ORG-005 |
| T-10 pagination | OC-CHILD-010 |
| T-11 counts | OC-CHILD-011 |
| T-12 hasParent/hasChildren | OC-NAV-010 |
| T-13 filter boundary | OC-FLT-001, OC-FLT-002 |
| T-14 invalid filter | OC-FLT-004 |
| T-15 recursion | OC-X-003 |
| T-16 consistency | OC-X-001 |
| T-17 PII fields | OC-NAV-013 |
| T-18 domain≠object | OC-NAV-004 (Organization Visibility model) |
