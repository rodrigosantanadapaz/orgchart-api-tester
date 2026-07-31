# ORG-21922 — Org Chart REST API: Implementation Security Review

**Role:** Principal Software Security Architect (design review)
**Jira:** [ORG-21922](https://jira2.workday.com/browse/ORG-21922) — *Org Chart REST API — security checklist (domains, threat model)*
**Epic:** [ORG-21726](https://jira2.workday.com/browse/ORG-21726) · **FDSPA:** [ORG-21974](https://jira2.workday.com/browse/ORG-21974) · **Follow-ups:** [ORG-22071](https://jira2.workday.com/browse/ORG-22071) · **Perf (out of scope):** [ORG-21938](https://jira2.workday.com/browse/ORG-21938)
**Toggle:** `INTERNAL: ORG-21934 — Org Chart REST API Toggle` (Internal – ON), WID `3558acd28f1410000dccc156a0e30000`
**Service:** `orgchart` v1, service WID `3558acd28f1410000e04914050bc0000`; SCR `orgchart/navigables` WID `3558acd28f1410000e3a06e7a6b50000`
**Reviewed:** the **remote Workday Org Chart REST API** (XO metadata service). *Not* the local `orgchart-api-tester` FastAPI app.
**Date:** 2026-07-30

> **Nature of the implementation.** This API is an **XO (metadata-driven) service** — there is no hand-written controller/Java. Behavior is defined by XO metadata: Service → Service Container → Version → **SCR** (Secured Class Resource) → **Service Operation** → **RSMB** (Return Set Method Binding) / **RAMB** (Return Attribute Method Binding) / **BA** (Build Attribute) → **CRF** (Class Report Field) → **Domain**. "Code references" below are metadata objects (with WIDs) captured from the merged code-review patch and the audited design docs.

---

## 0. Evidence base & source priority

| Priority | Source | What it gave us |
|---|---|---|
| 1. Implementation | `xo-code-reviews/ORG/<hash>/raw_changes.json` + `full_commit_history.md` (merged patch, PR #161 area); hashes `a0af8706…`, `039617…`, `6fff64…` | Actual merged metadata: RSMB bindings, domains, CRF domain reverts, `getInstancesFromResourceClass` flip |
| 1. Implementation | `robert-evers/ORG-22063` → `tasks/ORG-21726/plans/04-target-service-current-state.md`, `05-poc-reference.md`, `13-security-audit.md`, `06-gap-analysis.md`, `15-deferred-items.md`, `memory/decisions.md`, `memory/status.md` | SCR settings, per-field CRF/domain map, ESS smoke-test matrix, prompt-security resolution, filter behavior (audited vs live SUV) |
| 2. Existing tests | `15-deferred-items.md §1`, `14-followup-system-test-story.md`, `memory/decisions.md` (WATS) | UTG `Org Chart REST API Method Bindings` (`22041$60986`), 5 WATS REST cases, ~30 manual smoke tests |
| 3. Docs / TDD | **Confluence TDD `4327427328` v16** + **Implementation State `4451444155` v7** + **Smoke Test Results `4451737446` v7** — *retrieved & reviewed directly 2026-07-30* (see `ORG-21922-tdd-reconciliation.md`); plus `02-tdd-summary.md` | Design intent, HTTP/error contract, verified security layers, doc conflicts |
| 4. Jira / team | ORG-21922, ORG-21974, ORG-22071, ORG-21934 | Domain decision, "private/Agents-only", assets, open questions |
| 5. Miro | `miro.com/app/board/uXjVH2me7OQ=` | **Contents not accessible** — see `ORG-21922-miro-review.md` |
| 6. Assumptions | — | Marked **TO CONFIRM** throughout |

---

## 1. Implementation map (in-scope endpoints)

All 6 in-scope endpoints resolve from **one collection SCR** (`orgchart/navigables`) plus two sub-collection SCRs (`parent`, `children`) and a prompt group (`orgChartPrompts`). Per Workday REST convention, **one "view" service operation generates both the collection GET and the singular `/{ID}` GET** (source: `03-api-surface.md`).

### 1.1 `GET /navigables/{ID}` (the "self" endpoint) + `GET /navigables`
```
Endpoint:            GET /navigables/{ID}  and  GET /navigables
Route/SCR:           orgchart/navigables  (WID 3558acd28f1410000e3a06e7a6b50000)
Service operation:   view (GET)  (WID 3558acd28f1410000e4db8f3d4b50000)
Resource class:      Navigable (abstract) — WID cd0ca626446c11de98360015c5e6daf6, IID 1$715
                     subtypes: Worker (1$261), Organization (1$223), Position Restrictions (1$4872)
Singular binding:    getInstancesFromRSMB = Instance@get This Instance(GSS)(public)[rsmb]
                     WID d3ff1b9e446c11de98360015c5e6daf6   <-- resolves ANY Navigable by WID
Collection dump:     getInstancesFromResourceClass = false  (merged patch flips Old "Y" -> "")  => no bulk dump
Security methods:    (a) operation domain = Reports: Navigate Organization (75c4f96faa4a4f60809202a621864b45)
                     (b) SCR flags secureResultsUsingDomain / instanceBasedSecurityCompatibility  <-- SEE CONFLICT §3.3
                     (c) CRF field-level domains (Layer 4)
CRFs (envelope):     Navigable Type (RAMB *NT), Has Parent (RAMB), Has Children (RAMB), Detail (discriminator)
                     -> all reverted to domain "Public Reporting Items" (40bae4886d324a53b410cddbc997584f)
RAMBs/BAs:           navigableType RAMB (86$979781) dispatches via BA "get Navigable Type Name for Org Chart REST API"
                     implemented per-subtype for Employee(+1)/Organization/Position Restrictions;
                     hasParent RAMB (86$979782); hasChildren RAMB (86$979780)
Representations:     orgchartNavigableView (WID 3558acd28f1410000e4413343f960000) -> embeds navigableDetail
                     -> {workerNodeDetails | organizationNodeDetails | unfilledPositionDetails}
Returned types:      Worker | Organization | Unfilled Position (polymorphic `detail`)
Pagination:          paginated=true (limit default 20/max 100, offset); serverSidePaginationCacheEnabled=true
Filters:             navigableFilter (array, form/explode) advertised on collection
Existing tests:      3 RSMB unit tests (UTG 22041$60986); WATS REST GET cases; manual smoke (worker/org/position)
Open questions:      (1) secureResultsUsingDomain true vs false (doc conflict). (2) Does a valid-but-not-
                     caller-visible WID return 200+data, 404, or 403? (3) Are envelope/Public-Reporting-Items
                     fields returned for any WID regardless of navigational reachability?
```

### 1.2 `GET /navigables/{ID}/children`
```
SCR:                 orgchart/navigables/children (sub-collection)
Operation:           children/view (GET)  (WID bf01e161430310001550ab932daa0000 on POC lineage)
RSMB:                Navigable@get Children or Peers for Org Chart API(GSS)*P[rsmb]  (95ef6a23335e10000fb9e27e66360000)
                     -- API-EXCLUSIVE rewrite of the UI method "Children and Peers(SS)*P" (19$38426);
                        carries a "+???" metadata-review marker (06-gap-analysis) -> TO CONFIRM it is resolved
defaultSortRAMB:     Navigable@get Navigable Node Order(GRA)*P*S[ramb]  (e7478b17cb551000c069951e34fa0000)
Filters:             navigableFilter FQP (additive — see §4.2 / §Special-Filter)
Security:            endpoint domain (Reports: Navigate Organization) + traversal method visibility
                     (org-level filtering observed live: tkerr sees a restricted child org, lmcneil does not)
Existing tests:      WATS REST children case; manual smoke (CEO 142 children)
Open questions:      Are ALL children independently visibility-checked (orgs vs workers vs positions)?
                     Do total/hasChildren counts include hidden children?
```

### 1.3 `GET /navigables/{ID}/parent`
```
SCR:                 orgchart/navigables/parent (sub-collection)
Operation:           parent/view (GET)  (bf01e16143031000159bec2782330000 on POC lineage)
RSMB:                Navigable@get Parents(SSC)*P[rsmb]  (d40bbe76446c11de98360015c5e6daf6)
                     suppressParentSecurityEvaluation = false  (parent security IS evaluated) [04-target §2]
Filters:             navigableFilter advertised by Swagger; POC had NO navigableFilter on parent (gap) -> TO CONFIRM on target
Existing tests:      WATS REST parent case; smoke (CEO has no parent -> empty array)
```

### 1.4 `GET /values/orgChartPrompts/workers?search=…`
```
Prompt group:        orgChartPrompts (a86cc88e1fc61000280e95adde470000) — secured by Reports: Navigate Organization
Worker prompt set:   Worker Secured [Singular] (15$466135)
                     secureByDomains = ["Worker Data: Public Worker Reports" (2229$797),
                                        "Self-Service: Current Staffing Information" (2229$845)]  => DOMAIN-FILTERED
Returns:             MULTIPLE_INSTANCE_MODEL_REFERENCE { total, data:[{id, descriptor}] }  (no detail fields)
Params:              search (case-insensitive prefix), limit (default/max 1000), offset
Existing tests:      smoke A-series prompt cases
Note:                Custom unsecured work set "Workers for Org Chart REST prompt" (15$502454) was DELETED (INIU)
```

### 1.5 `GET /values/orgChartPrompts/organizations?search=…`
```
Prompt set:          default Organization ISD (built-in security)  [13-security-audit Risk 2]
Live check:          organizations?search=Product -> 19 orgs (status.md)
Returns:             { total, data:[{id, descriptor}] }
```

### 1.6 `GET /navigables/{ID}/children?navigableFilter=…`
```
FQP:                 navigableFilter on children SCR (POC WID 90c12bcee97b10000ae113b1ce2c0000)
navigableFilters prompt: uses "Navigable [Singular]" (15$338505) — NO security possible
                     (Navigable class not contextually secured); justified via exception #9/#10 [15-deferred §5]
Observed behavior:   ADDITIVE — org 6620 Product Management returns 9 children by default, 10 with
                     navigableFilter=Open Positions (6ea473c87495100024a9b7cd96820030); extra node is
                     P-00085 (Unfilled), type=POSITION  (status.md)
```

> **Route-name mapping note.** The tester/README refer to the 6 in-scope routes with names that match the XO metadata 1:1 (`/navigables/{ID}`, `/children`, `/parent`, `/values/orgChartPrompts/{workers,organizations,navigableFilters}`). The **`positions` prompt was removed** in v1 (returns 404) — do **not** assume it exists (source: `15-deferred-items.md §2`, `status.md`).

---

## 2. Architecture & data flow

```
Agent / integration (private API; "Only Agents will use this API" — ORG-21974)
  → [Trust boundary A] Gateway Internal (routing 9eeedb8269fc1000432c7b2aef5e003b), protectedUsageEnabled=true
  → Authentication (OAuth 2.0 Bearer; tenant-scoped)                    [platform-trusted]
  → [Trust boundary B] Feature toggle ORG-21934 gate (metadata invisible when OFF)
  → REST endpoint / Service Operation "view|parent/view|children/view"
  → [Trust boundary C] Operation security domain: Reports: Navigate Organization   → 403 if absent
  → SCR instance resolution
        • singular: Instance@get This Instance(GSS)(public)  → resolves the requested WID
        • children/parent: RSMB traversal methods            → return related set
        • secureResultsUsingDomain / instanceBasedSecurityCompatibility  ← governs object-level filtering (CONFLICT §3.3)
  → [Trust boundary D] CRF field-level domains (Layer 4)  → strips fields per caller's domains
  → Representation construction (orgchartNavigableView → polymorphic detail)
  → Response (JSON; fields silently omitted when a domain is lacking)
```

**Where secured objects enter:** the caller-supplied **WID** (`ID`/`subresourceID`) and **navigableFilter** WIDs enter at the SCR boundary; the resolved `Navigable` (and its embedded Worker/Org/Position + Location/JobProfile/Manager) enter at instance resolution and representation construction.

**"Security by upstream assumption" (key architectural risk):** Field construction (Layer 4) **assumes that instance resolution already removed objects the caller may not see**. If the singular binding (`This Instance(GSS)(public)`) does **not** perform object-level visibility (see §3.3), then Layer 4 only strips *restricted fields* — it does **not** hide the *existence* of the node or its **Public Reporting Items** fields. This is the crux of the "self" endpoint concern.

---

## 3. Security model (Phase 3)

The team's stated model = "general API security uses **Reports: Navigate Organization**". Validated below. The implementation uses a **four-layer** model (source: `13-security-audit.md`, `16-cliona-demo-summary.md`).

| # | Layer | Mechanism | Effect |
|---|---|---|---|
| 1 | Feature toggle | ORG-21934 | Whole service invisible when OFF |
| 2 | Operation domain | Reports: Navigate Organization | 403 if caller lacks the domain (endpoint-level gate) |
| 3 | SCR instance resolution | `secureResultsUsingDomain`, `instanceBasedSecurityCompatibility`, RSMB bindings | *Supposed* object-level filtering — **contested, see §3.3** |
| 4 | CRF field-level | Per-field security domains | Restricted fields silently omitted per user |

### 3.1 Point-by-point answers

| Question | Finding | Evidence | Confidence | Risk |
|---|---|---|---|---|
| Is *Reports: Navigate Organization* explicitly enforced? | Yes, on all 3 operations + prompt group | merged patch (`75c4f96f…` on service version + `orgChartPrompts`); `13-security-audit §Layer 2` | **High** | — |
| Where enforced? | Service-operation level (endpoint gate) | `13-security-audit §Layer 2` | **High** | Gate ≠ object visibility |
| Route / service / method / object / representation level? | **Operation (endpoint)** level; **not** at object/class level | ditto | **High** | See BOLA |
| Required for every endpoint? | Yes (view, parent/view, children/view; prompts inherit) | `13-security-audit` | **High** | — |
| Is object-level visibility evaluated *after* domain access? | **Not on the "self" endpoint** (structurally cannot be, see §3.3); **children** appears to filter orgs | decisions.md (class not contextually secured); CONTEXT.md (children org filter) | **Medium** | **High** |
| Orgs / Workers / Positions evaluated independently? | Field-level: yes (per-CRF domains). Object-level: **inconsistent** across endpoints | `13-security-audit §Layer 4`; §3.3 | **Medium** | Medium |
| Parent access ⇒ children access? | No implicit grant; children filtered by traversal method | CONTEXT.md | **Low/TO CONFIRM** | Medium |
| Child access ⇒ parent access? | `suppressParentSecurityEvaluation=false` ⇒ parent security evaluated | `04-target §2` | **Medium** | Medium |
| Does a valid WID allow direct retrieval? | **Yes** — `This Instance(GSS)(public)` resolves any WID | merged patch; `04`/`05` | **High** | **High** |
| Security before or after data retrieval? | Domain gate before; field security during representation; **object visibility ambiguous** | §2, §3.3 | **Medium** | High |
| Hidden records filtered or rejected? | Fields: silently omitted. Objects: **TO CONFIRM** (200+data vs 404 vs 403) | `13-security-audit`; no test | **TO CONFIRM** | **High** |
| Prompts governed by same model? | **No — divergent.** workers=domain-filtered; orgs=ISD-secured; navigableFilters=unsecured; positions=removed | `15-deferred §5`; `status.md` | **High** | Medium |
| Pagination counts based on secured results? | **TO CONFIRM** — `total` / hidden-node counting not tested | — | **TO CONFIRM** | Medium |
| Metadata fields security-sensitive? | `hasParent`/`hasChildren`/`type`/`descriptor` are **Public Reporting Items** (all users) | merged patch (`Has Parent` → Public Reporting Items) | **High** | Medium |
| `hasParent`/`hasChildren` from full or caller-visible hierarchy? | Computed via full-traversal GSS per node; **whether counts respect visibility = TO CONFIRM** | `15-deferred §11`; decisions.md | **TO CONFIRM** | Medium |
| Does `navigableFilter` affect authorization? | Designed as selection-only; observed **additive**; navigableFilters prompt unsecured | `status.md`; `15-deferred §5` | **Medium** | Medium |
| Different behavior per navigable type? | Yes — POSITION has no `hasParent`/`hasChildren` and no parent path; detail strips to `{}` for restricted users | decisions.md; `status.md` | **High** | Low |
| Lacking-domain vs lacking-object-visibility distinguishable? | Lacking domain → 403. Lacking object visibility → **TO CONFIRM** (likely 200 with public data) | `13-security-audit`; §3.3 | **TO CONFIRM** | **High** |

### 3.2 CRF field-level map (Layer 4) — verified by ESS smoke tests

`13-security-audit.md` documents the per-field domain map; `memory/decisions.md` records live verification with personas **smorgan/oreynolds** (privileged) vs **tkerr** (ESS).

- **Public Reporting Items (all users with the endpoint domain):** worker `fullName, jobTitle, workerType, location, photo, orgMembership, email`; org `name, organizationType, location, code, subtype, manager` (identity); envelope `type, hasParent, hasChildren, detail`.
- **Self + managers/admins:** `businessTitle, primaryPosition, fte, phoneNumbers`.
- **Managers/admins only:** `positionsForWorker, active, timeType, orgsManaged`, position `positionID` (Worker Data: Current Staffing Information).
- **Verified:** cross-worker restricted fields are silently stripped (no null/placeholder). **Field-level security works.** (Evidence: `13-security-audit` ESS matrix; `decisions.md` B4/B5.)

### 3.3 The `secureResultsUsingDomain` conflict + the "not contextually secured" fact (CRITICAL)

> **Updated 2026-07-30 after retrieving the original Confluence TDD + Implementation State.** Full reconciliation in `ORG-21922-tdd-reconciliation.md`.

**Conflict — now re-weighted (still TO CONFIRM #1 for the exact value):**
- **`true` (3 sources, incl. the authoritative latest):** `04-target-service-current-state.md`; `16-cliona-demo-summary.md`; **Confluence Implementation State `4451444155` v7 §3** — "Layer 3 — `secureResultsUsingDomain` filters *which* navigables a caller can resolve."
- **`false` (1 outlier):** `13-security-audit.md` (2026-06-05) — likely written mid-build or conflated with the POC (POC is `false` per `05-poc-reference.md`).
- **`instanceBasedSecurityCompatibility`:** still unresolved — `04`=`false` vs `13`=`true`; **Confluence is silent** → metadata-only TO CONFIRM.

**Structural fact that dominates the conflict (now confirmed by Confluence, not just the eng docs):** Implementation State **§4.2** states verbatim: *"The Navigable class is **not contextually secured**… `Public Reporting Items` is the only viable domain for these container CRFs. **Real security is provided by … the operation domain, SCR instance filtering, and leaf-CRF field stripping — not by the discriminator CRFs.**"* Securing the discriminators by domain threw Critical exception `21430$174` and was reverted (`memory/decisions.md`). So **object-level domain securing on the base Navigable (Worker/Organization) is not achievable regardless of the `secureResultsUsingDomain` value** — the flag can, at most, enforce the *operation domain*, not per-instance visibility, on a non-contextually-secured class.

**Refined, evidence-backed conclusion:**

> **On `GET /navigables/{ID}`, object-level visibility is NOT enforced for Worker/Organization.** A caller with *Reports: Navigate Organization* can retrieve *any* valid Navigable WID and receive its existence, `type`, `descriptor`/`name`, `hasParent`/`hasChildren`, manager identity, and all **Public Reporting Items** fields; only *restricted* fields (Layer 4) are stripped. The smoke tests corroborate the mechanism: restricted personas (`smorgan`/`tkerr`) are **never denied a node** — they receive the **same node** with sensitive fields silently omitted (Smoke H2–H6, "Security differential"). For **Position** navigables, `detail` strips to `{}` for an unauthorised persona **but the POSITION node + descriptor are still returned** (Smoke D1-sec/H6) — so existence is disclosed for all three subtypes.

**Confidence:** **Medium-High → High** that no object-level *access* gate exists on `/self` for Worker/Org (structural fact now confirmed in Confluence + corroborating smoke behavior). **The single residual RUNTIME question** is whether a *genuinely hidden/out-of-hierarchy* Worker/Org behaves any differently via `/self` — **untested**, because every smoke node was visible to all personas. → **Prove with T-01/T-02/T-06/T-18.**

**HTTP contract actually implemented (from Smoke Test Results `4451737446`):** no-domain → **403** (I3); invalid/malformed WID → **404**, no stack leak (I1/I2); visible valid WID → **200** (B/C/D). **Inaccessible-but-valid WID → undefined/untested** (no smoke case; TDD Security = TBD) — likely 200 + public data. Defining this contract is a prerequisite (see §6, and `ORG-21922-tdd-reconciliation.md` §D-Q4).

---

## 4. Endpoint-by-endpoint review (Phase 4)

### 4.1 `GET /navigables/{ID}` — SELF (special attention)

```
Purpose:              Retrieve a single Navigable (Worker | Organization | Unfilled Position) by WID.
Returned data:        envelope {type, descriptor, id, hasParent, hasChildren, detail{...}}
Object types:         Worker, Organization, Unfilled Position
Authentication:       OAuth Bearer, tenant-scoped (platform).
Domain authorization: Reports: Navigate Organization at operation level -> 403 if absent. [High]
Object visibility:    NOT PROVEN / likely NOT ENFORCED. Navigable not contextually secured;
                      binding = This Instance(GSS)(public); Layer 4 strips fields, not existence. [Medium, High risk]
Security deps:        Relies on Layer 4 field stripping for data protection; NO object-level gate.
CRFs/RAMBs:           navigableType RAMB (*NT) + per-subtype BA; Has Parent / Has Children RAMBs;
                      Detail discriminator CRF — all "Public Reporting Items".
Existing coverage:    Functional smoke (worker/org/position render). NO hidden-object / inaccessible-WID test.
Threats:              BOLA, WID enumeration, information disclosure (existence + name + manager identity),
                      relationship inference (hasParent/hasChildren), PII (public fields).
Manual validation:    T-01 (hidden org via self as restricted user), T-06 (invalid vs inaccessible WID).
Open questions:       secureResultsUsingDomain (§3.3); expected HTTP for inaccessible valid WID (TO CONFIRM).
Confidence:           Medium (object visibility likely not enforced).
```

**Special-review verdict (self):** **Object-level visibility is NOT proven; evidence indicates it is not enforced and is delegated to nothing (field-level only).** The endpoint (a) resolves the WID before any object-visibility evaluation, (b) uses a generic public instance lookup, (c) trusts the supplied WID, (d) returns Public-Reporting-Items fields identically for all three subtypes, (e) can disclose object existence and relationship flags, and (f) **has no existing test for a valid-but-inaccessible WID.** → **Prove on live SUV before approval.**

### 4.2 `GET /navigables/{ID}/children`

```
Purpose:              List children (mixed Workers / Orgs / Unfilled Positions), paginated.
Object visibility:    Traversal method appears to apply org-level visibility (tkerr vs lmcneil, CONTEXT.md). [Medium]
Security deps:        RSMB "Children or Peers for Org Chart API(GSS)*P" — carries unresolved "+???" review marker. [TO CONFIRM]
Filters:              navigableFilter — ADDITIVE (9->10 with Open Positions). [status.md]
Threats:              Hierarchy enumeration, pagination leakage, count leakage, filter-driven disclosure,
                      per-child inconsistent authz (are workers/positions checked as strictly as orgs?).
Manual validation:    T-04 (mixed visible/hidden children), T-10 (pagination), T-11 (counts), T-13/T-14 (filter).
Confidence:           Medium.
```
**Children special-review:** Determine whether hidden children are **removed** (expected) vs **counted-but-omitted** vs **disclosed via metadata**. `+???` marker on the children RSMB must be confirmed resolved. Verify children of **all three types** are independently visibility-checked (the design docs prove org filtering; worker/position filtering on children is **TO CONFIRM** and is called out as a known concern in CONTEXT.md: "workers/positions were observed to be less filtered than orgs").

### 4.3 `GET /navigables/{ID}/parent`

```
Purpose:              Return parent node(s) (manager / parent org).
Object visibility:    suppressParentSecurityEvaluation=false -> parent security evaluated. [Medium]
Risk:                 A visible child revealing a hidden parent's existence/identity; parent-crossing a boundary.
Filters:              navigableFilter advertised by Swagger but absent on POC parent SCR -> TO CONFIRM on target.
Manual validation:    T-05 (visible child, hidden parent).
Confidence:           Medium.
```

### 4.4 `GET /values/orgChartPrompts/workers?search=…`

```
Returns:              {id, descriptor} only (no detail).
Object visibility:    Worker Secured [Singular] -> secureByDomains [Public Worker Reports, Current Staffing Info]. [High]
Enumeration:          Prefix search on descriptor; limit up to 1000. Domain-filtered set reduces (not eliminates)
                      enumeration surface. Terminated/inactive worker inclusion = TO CONFIRM.
Threats:              Worker enumeration, PII (names) — mitigated by domain-scoped set; consistency with /self = TO CONFIRM.
Manual validation:    T-07 (exact/partial name), T-09 (broad search returns only visible), T-16 (consistency).
Confidence:           Medium-High (set is secured; runtime scope TO CONFIRM).
```

### 4.5 `GET /values/orgChartPrompts/organizations?search=…`

```
Returns:              {id, descriptor} only.
Object visibility:    Default Organization ISD (built-in security). [Medium]
Consistency risk:     Org prompt may EXPOSE or BLOCK differently than /self direct lookup — if /self does not
                      enforce object visibility (§3.3) but the org prompt DOES, that is an inconsistency in
                      the OTHER direction (prompt hides an org that /self will still return). [High-value test]
Manual validation:    T-08, T-16.
Confidence:           Medium.
```

### 4.6 `GET /navigables/{ID}/children?navigableFilter=…`

```
Behavior:             ADDITIVE selection (adds Open Positions node). [status.md]
navigableFilters set: Navigable [Singular] — UNSECURED (no contextual security on Navigable). [15-deferred §5]
Risks:                (a) invalid/malformed filter falling back to unrestricted results;
                      (b) filter causing hidden objects to appear;
                      (c) the unsecured navigableFilters prompt leaking valid filter WIDs.
Requirement:          Filter MUST change selection, not authorization.
Manual validation:    T-13 (filtered vs unfiltered same security boundary), T-14 (invalid filter no fallback).
Confidence:           Medium.
```

---

## 5. Threat analysis (Phase 5 — STRIDE, emphasis Info-Disclosure & EoP)

| Threat ID | Threat | STRIDE | Endpoint | Asset | Attack scenario | Precondition | Implementation evidence | Impact | Existing control | Control conf. | Recommended validation | Severity | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| T-D01 | **Direct-WID object disclosure (BOLA) on self** | Info Disclosure / EoP | `/navigables/{ID}` | Org/Worker/Position existence + public fields + manager identity | Agent with domain fetches a WID it can't reach by navigation | Has *Reports: Navigate Organization*; knows/guesses a WID | Navigable not contextually secured (decisions.md); `This Instance(GSS)(public)`; discriminator CRFs = Public Reporting Items | Confidentiality: leaks org structure, names, manager identity | Layer 4 (fields only), toggle, domain gate | Medium | T-01, T-06 | **High** | **Potential (TO CONFIRM)** |
| T-D02 | **Inaccessible vs invalid WID distinguishable** | Info Disclosure | `/navigables/{ID}` | Object existence | Compare 404 (invalid) vs 200/other (valid-but-hidden) | domain | invalid→404 (smoke); hidden→? | Existence oracle → enumeration aid | none specific | TO CONFIRM | T-06 | Medium | **TO CONFIRM** |
| T-D03 | **WID enumeration via prompts** | Info Disclosure | workers/orgs prompts | Names/WIDs | Broad/1-char search to harvest {id,descriptor} | domain | workers=domain-filtered; orgs=ISD; limit 1000 | Bulk identity harvest within visible scope | domain-scoped sets | Medium | T-07,T-08,T-09 | Medium | **Mitigated (partial)** |
| T-D04 | **Hierarchy enumeration via recursive traversal** | Info Disclosure | children/parent | Org graph | Recurse children/parent to reconstruct chart | domain | children filters orgs; worker/position filtering TO CONFIRM | Rebuild (possibly hidden) hierarchy | traversal method visibility | Medium | T-15 | Medium | **Potential** |
| T-D05 | **Relationship inference via `hasParent`/`hasChildren`** | Info Disclosure | all navigable | Existence of hidden relations | Read boolean flags computed over full hierarchy | domain | flags = Public Reporting Items; computed via full traversal (15-deferred §11) | Infer hidden parent/children exist | none if counts ignore visibility | TO CONFIRM | T-12 | Medium | **TO CONFIRM** |
| T-D06 | **Manager-identity disclosure via org node** | Info Disclosure | `/navigables/{orgID}` | Manager PII (name) | Fetch any org WID → read `manager` embed identity | domain | manager identity = Public Reporting Items | Leak "who manages org X" for any org | Layer 4 strips manager's *restricted* fields only | Medium | T-01/T-17 | Medium | **Potential** |
| T-D07 | **Excessive data / PII exposure in fields** | Info Disclosure | self/children | Worker PII (email, phone, photo) | Read node detail | domain (+ self/mgr for restricted) | ESS stripping verified | email/photo/orgMembership are Public | public-in-orgchart rationale | Medium | T-17 | Low-Med | **Mitigated** |
| T-E01 | **Filter bypass / fallback to unrestricted** | EoP | children?navigableFilter | Extra nodes | Send invalid/unauthorized filter → hope for unfiltered set | domain | filter additive; navigableFilters unsecured | Reveal nodes beyond intended selection | validation on filter values | TO CONFIRM | T-14 | Medium | **TO CONFIRM** |
| T-E02 | **Pagination leakage of hidden nodes** | Info Disclosure | collections | Hidden nodes / counts | Page deep; compare `total` vs returned | domain | not tested | Count/late-page leak of hidden items | server-side cache pagination | TO CONFIRM | T-10,T-11 | Medium | **TO CONFIRM** |
| T-E03 | **Inconsistent authorization across endpoints** | EoP / Info Disclosure | self vs children vs prompt | Same object | Object hidden via one path, visible via another | domain | children filters; self likely not; prompts vary | Bypass one gate via another endpoint | none unifying | Medium | T-16 | **High** | **Potential** |
| T-S01 | **Spoofing / auth** | Spoofing | all | tokens | — | — | OAuth+tenant (platform) | — | platform auth | High | — | Low | **Mitigated** |
| T-T01 | **Tampering / write** | Tampering | all | data | — | — | GET-only, read-only | — | no write ops | High | — | N/A | **Not Applicable** |
| T-DoS1 | **`hasParent`/`hasChildren` traversal amplification** | DoS (security-adjacent) | children (large N) | availability | Request large org → N extra traversals | domain | 15-deferred §11 (CEO 151 children) | Latency/cost; can mask enforcement under load | none yet | Medium | (ORG-21938 perf; note security-relevance) | Low-Med | **Potential** |
| T-B01 | **Trust-boundary violation (Layer-4-only reliance)** | EoP | self | all | Downstream field-stripping assumed to cover object visibility | — | §2 upstream assumption | Object exposure when instance layer doesn't filter | — | Medium | T-01 | **High** | **Potential** |

> No item is marked **Confirmed** — every disclosure/EoP finding depends on runtime behavior that a live SUV test must reproduce. They are **Potential/TO CONFIRM** per the execution rules.

---

## 6. Open questions (implementation)

1. **[TO CONFIRM #1 — top priority]** Actual merged value of `secureResultsUsingDomain` (docs lean **`true`**, one outlier `false`) / `instanceBasedSecurityCompatibility` (`04`=false vs `13`=true; Confluence silent) on `orgchart/navigables` (§3.3). Pull from live SUV metadata. **Note:** even if `true`, it is structurally **moot for Worker/Org object visibility** (class not contextually secured) — so the deeper question is Q2 below.
2. **[TO CONFIRM]** Does `GET /navigables/{hiddenWID}` for a restricted user return **200 + public data**, **404**, or **403**? (Defines T-D01/T-D02 severity and the API's expected error contract.)
3. **[TO CONFIRM]** Are **worker** and **unfilled-position** children independently visibility-checked in `/children`, or only orgs? (CONTEXT.md flags workers/positions "less filtered".)
4. **[TO CONFIRM]** Do `hasParent`/`hasChildren` and collection `total` reflect the **caller-visible** hierarchy or the **full** hierarchy?
5. **[TO CONFIRM]** Is the children RSMB `+???` metadata-review marker resolved? What does "or **Peers**" include (could peers be returned)?
6. **[TO CONFIRM]** Does `parent` have `navigableFilter` on the target (POC gap)? Does an **invalid** `navigableFilter` fall back to unrestricted results?
7. **[Decision]** Production domain: keep `Reports: Navigate Organization` or switch to `View: People-View Org Chart` (blocked all access on SUV — policy config). Owner: Cliona (ORG-22071 / ORG-21938).
8. **[Decision]** Is the unsecured `navigableFilters` prompt (Navigable [Singular]) acceptable, or must filter values be constrained?

---

## 7. Appendix — key WIDs

| Object | WID / IID |
|---|---|
| Service `orgchart` | `3558acd28f1410000e04914050bc0000` (IID 6118$8175) |
| SCR `orgchart/navigables` | `3558acd28f1410000e3a06e7a6b50000` |
| Operation `view (GET)` | `3558acd28f1410000e4db8f3d4b50000` |
| Singular RSMB `This Instance(GSS)(public)` | `d3ff1b9e446c11de98360015c5e6daf6` |
| Children RSMB (API) | `95ef6a23335e10000fb9e27e66360000` |
| Parent RSMB (SSC) | `d40bbe76446c11de98360015c5e6daf6` |
| Domain `Reports: Navigate Organization` | `75c4f96faa4a4f60809202a621864b45` |
| Domain `Public Reporting Items` | `40bae4886d324a53b410cddbc997584f` |
| Toggle ORG-21934 | `3558acd28f1410000dccc156a0e30000` |
| Navigable class | `cd0ca626446c11de98360015c5e6daf6` (IID 1$715) |
| Worker prompt set `Worker Secured [Singular]` | `15$466135` |
| navigableFilters set `Navigable [Singular]` | `15$338505` |
| UTG (unit tests) | `22041$60986` |

*Every non-obvious claim above cites its source doc/patch. Items without runtime proof are marked TO CONFIRM.*
