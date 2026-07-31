# ORG-21922 — TDD / Implementation-State Reconciliation

**Purpose:** Reconcile the **original Confluence documentation** (TDD + Implementation State + Smoke Test Results) against the **merged XO metadata patch** and the engineering docs (`04-target-service-current-state.md`, `13-security-audit.md`, `memory/decisions.md`) and the **existing test evidence**. No live SUV was contacted; nothing posted to Jira.

**Original sources reviewed (this pass):**
- **TDD** — Confluence [`Org Chart REST API TDD`](https://confluence.workday.com/display/OC/Org+Chart+REST+API+TDD), page `4327427328`, v16 (2026-06-10, Robert Evers).
- **Implementation State** — Confluence `Org Chart REST API (v1) — Implementation State & Design Decisions`, page `4451444155`, v7 (2026-06-12, Robert Evers).
- **Smoke Test Results** — Confluence page `4451737446`, v7 (2026-06-12); run 2026-06-10 on SUV `i-073aded5e67683e74`, **25 PASS / 0 FAIL**.

---

## A. Reconciliation table

| Topic | Original design intention | Actual merged implementation | Evidence |
|---|---|---|---|
| **1. `secureResultsUsingDomain` (base `navigables` SCR)** | **Never specified in the TDD** (Security card = "Existing Domains: TBD / Proposed Domains: TBD"). Implementation State §3 *claims* Layer 3 = "`secureResultsUsingDomain` filters *which* navigables a caller can resolve." | **Conflicting across engineering docs.** Weight of evidence = **`true`**: `04-target-service-current-state.md` (target SCR `true`), Implementation State §3 & §4.3, `16-cliona-demo-summary.md`. **Outlier = `false`**: `13-security-audit.md`. **However**, on the base Navigable class the flag is largely **moot** (class not contextually secured — see topic 4). | TDD Security card (all TBD); Impl State §3, §4.3; `04-target §2` vs `13-security-audit §Layer 3`; `05-poc-reference` (POC=`false`, "target has it on") |
| **2. `instanceBasedSecurityCompatibility`** | Not mentioned in TDD or Implementation State. | **Conflicting, unresolved by original docs.** `04-target` = **`false`** (target "stricter"); `13-security-audit` = **`true`**. Confluence is silent → cannot break the tie from documentation. **Remains a metadata-only TO CONFIRM.** | `04-target §6`; `13-security-audit §Layer 3` (no Confluence statement) |
| **3. WID resolution binding (self)** | TDD: Base Service = **"Standard Navigable Lookup"** (no visibility qualifier). | **Confirmed:** `getInstancesFromRSMB = Instance@get This Instance(GSS)(public)` (`d3ff1b9e446c11de98360015c5e6daf6`) — a **public "resolve any instance by WID"** binding. | TDD Business-Logic card; merged patch (`raw_changes` × 3 hashes); `04-target §2`; `05-poc-reference §2` |
| **4. Object-level visibility for `/navigables/{ID}` (self)** | **Not required by the TDD** (Security = TBD). Implementation State §3 claims SCR instance filtering secures "which navigables a caller can resolve" — but §4.2 **undercuts this** for the base class. | **Structurally NOT enforced for Worker/Organization.** The **Navigable class is not contextually secured**; securing discriminator CRFs by domain threw Critical exception `21430$174` and was **reverted to Public Reporting Items**; "real security … not by the discriminator CRFs." Only **Positions Unfilled** achieves object-level securing — and even then the **node's existence + descriptor are still returned**, only `detail` strips to `{}`. | Impl State §4.2, §4.3; `memory/decisions.md` (revert); Smoke **D1-sec / H6** (POSITION detail→`{}`, node still returned) |
| **5. Scope of `Reports: Navigate Organization`** | TDD does not state it (domains TBD). | **Operation-level (endpoint) domain only.** Absent → **403**. It does **not** secure fields (those carry their own CRF domains: Public Reporting Items + restricted domains) and does **not** by itself secure the returned Worker/Org **instance**. | Impl State §3 (Layer 2), §4 (field security is separate leaf-CRF); merged patch (`75c4f96f…` on operations + prompt group); Smoke **I3** (403) |
| **6a. HTTP — visible valid WID** | TDD: returns the Self node. | **200 + envelope + detail** (fields per caller domains). | Smoke **B1–B5, C1, D1** |
| **6b. HTTP — inaccessible valid WID** | **Undefined** anywhere (TDD Test Strategy lists only "valid/invalid parms"; no 403/404 contract for hidden objects). | **UNKNOWN / UNTESTED.** No smoke case exercises a node the persona cannot see; field-stripping tests all use *visible* nodes. Structural inference: likely **200 + public fields** (Worker/Org) or **200 + `detail:{}`** (Position). | TDD Test Strategy card (silent); Smoke has **no** hidden-object case; §4 inference |
| **6c. HTTP — invalid WID** | TDD implies negative testing. | **404 "not found"** (all-zeros and malformed; no stack leak). | Smoke **I1, I2** |
| **6d. HTTP — user without domain** | Not specified in TDD. | **403** (no-proxy/system context, before any data). | Smoke **I3**; Impl State §3 (Layer 2 "verified") |
| **(supporting) Discriminator CRF domain** | TDD: new CRFs use **Public Reporting Items**. | **Public Reporting Items** on `Detail`/`~Worker~`/`Organization` (revert); `Positions Unfilled` domain-secured via work set. | TDD Reporting/Security cards; Impl State §4.2–§4.3; patch |
| **(supporting) Prompt security** | TDD silent on prompt security. | **Divergent:** workers = `Worker Secured [Singular]` (domain-filtered, search required >500); orgs = ISD; **navigableFilters = unsecured** (exception-justified); positions **removed (404)**. | Impl State §4.4, §4.5, §5; `15-deferred §5`; Smoke **A2** (no-search→total 0), **A1/A4** |
| **(supporting) `navigableFilter` semantics** | TDD: filters "prune the tree / isolate object types". | **Additive**, not restrictive (org 6620: 9→10 with Open Positions). Original docs flag this as a **contract mismatch to confirm**. | Impl State §4.5, §2.3; Smoke **G2, D2**; Impl State Open-Questions |
| **(supporting) Field-level (Layer 4) stripping** | TDD: CRF-domain based. | **Verified** on PERSON and POSITION subtypes; restricted users get the **same node**, sensitive fields silently omitted. | Smoke **H2–H6**, "Security differential" table |

---

## B. Answers to the six focus questions (evidence-bound)

> Categorised as **[CONFIRMED]** (implementation/tests prove it), **[INTENDED]** (documented design intent), **[CONFLICT]** (docs disagree), **[RUNTIME]** (needs live validation).

**1. Final merged value of `secureResultsUsingDomain` for `GET /navigables/{ID}`**
- **[CONFLICT → leaning `true`]** Three sources (Impl State §3/§4.3, `04-target`, `16-cliona-demo`) indicate `true`; one (`13-security-audit`) says `false`. The published Implementation State (latest, v7) treats it as active. **[RUNTIME]** Definitive value must be read from live SUV metadata on the base `orgchart/navigables` SCR (`3558acd28f1410000e3a06e7a6b50000`). *Note:* the value is **largely immaterial for Worker/Org object visibility** because of topic 4.

**2. Final value of `instanceBasedSecurityCompatibility`**
- **[CONFLICT — unresolved]** `04-target` = `false`; `13-security-audit` = `true`. **No Confluence source states it.** **[RUNTIME]** Read from live metadata. Genuine open question.

**3. Exact binding used to resolve the requested WID**
- **[CONFIRMED]** `Instance@get This Instance(GSS)(public)[rsmb]`, WID `d3ff1b9e446c11de98360015c5e6daf6` — a public resolve-any-instance binding. (TDD "Standard Navigable Lookup"; merged patch; `04`/`05`.)

**4. Is object-level visibility expected for the self endpoint?**
- **[INTENDED — ambiguous/undocumented]** The **TDD does not require it** (Security = TBD). Implementation State §3 *claims* SCR instance filtering secures which navigables you can resolve, but §4.2 states the base class cannot be object-secured.
- **[CONFIRMED — not enforced for Worker/Org]** Navigable class not contextually secured; discriminator CRFs reverted to Public Reporting Items; only field-level stripping protects data. **[CONFIRMED — Position]** object-level *detail* securing works (`detail→{}`), but node existence/descriptor still returned.
- **[RUNTIME]** Behavior for a genuinely hidden/out-of-hierarchy Worker/Org via `/self` is **untested** (all smoke nodes were visible to every persona). → Tests T-01/T-02/T-06/T-18.

**5. Is `Reports: Navigate Organization` meant to secure fields or the returned instance?**
- **[CONFIRMED]** It is the **operation/endpoint domain** (→403 if absent). It does **not** secure fields (those use their own CRF domains) and does **not** by itself secure the returned Worker/Org instance. Instance ("which navigables") securing is a *separate, claimed* Layer-3 mechanism that is structurally limited to the Positions Unfilled work set. (Impl State §3/§4; patch; Smoke I3/H*.)

**6. Expected HTTP behavior**
| Case | Verdict | Category | Evidence |
|---|---|---|---|
| Visible valid WID | **200** + envelope/detail | **[CONFIRMED]** | Smoke B/C/D |
| Inaccessible valid WID | **Undefined; likely 200 + public data (Worker/Org) or 200 + `detail:{}` (Position)** | **[RUNTIME]** | No smoke case; TDD silent; §4 inference |
| Invalid WID | **404** "not found" | **[CONFIRMED]** | Smoke I1/I2 |
| User without domain | **403** | **[CONFIRMED]** | Smoke I3; Impl State §3 |

---

## C. Confirmed facts vs intended vs conflicting vs runtime

**Confirmed implementation facts**
- Operation domain `Reports: Navigate Organization`; no-domain → **403**. (I3)
- Invalid/malformed WID → **404**, no stack leak. (I1/I2)
- Singular binding = `This Instance(GSS)(public)` (resolve any WID).
- Navigable class **not contextually secured**; discriminator CRFs = Public Reporting Items (reverted; exception `21430$174`).
- Data protection for Worker/Org is **field-level only**; restricted users receive the **same node** with sensitive fields omitted. (H2–H6, security-differential table)
- Positions Unfilled `detail` strips to `{}` for unauthorised persona, but the POSITION node + descriptor are still returned. (D1-sec/H6)
- Workers prompt domain-filtered + search-required (>500); navigableFilters prompt unsecured; positions prompt removed (404). (A1–A4, §4.4/§4.5)
- `navigableFilter` additive. (G2/D2)

**Intended design (documented)**
- TDD: read-only aggregation API for Agents; "Standard Navigable Lookup" for self; new CRFs use Public Reporting Items; **security domains left TBD**.
- Impl State: 4-layer model; explicitly states real security ≠ discriminator CRFs; production domain TBD (Reports: Navigate Organization vs View: People-View Org Chart).

**Conflicting documentation (unresolved by originals)**
- `secureResultsUsingDomain` on base SCR: **3 docs `true` vs 1 doc `false`** (Confluence leans true; audit doc is outlier).
- `instanceBasedSecurityCompatibility`: `04`=`false` vs `13`=`true`; **Confluence silent**.

**Runtime behavior still requiring validation (live SUV)**
1. Actual metadata values of `secureResultsUsingDomain` / `instanceBasedSecurityCompatibility` on the base SCR.
2. Whether `/self` returns a **genuinely hidden** Worker/Org (200+public data?) — the untested BOLA case.
3. Whether `secureResultsUsingDomain=true` has **any** per-instance effect on the non-contextually-secured base class, or only enforces the operation domain.
4. Whether `/children` set-filtering (org visibility) also applies to worker/position children, and whether counts/`hasChildren` reflect visible vs full hierarchy.
5. Expected HTTP for inaccessible valid WID (define the contract: 403 vs 404 vs 200).

---

## D. Remaining open questions for the team review (must resolve before finalizing security conclusions)

- **Q1 (metadata truth):** Read live values of `secureResultsUsingDomain` + `instanceBasedSecurityCompatibility` on `orgchart/navigables` and reconcile the doc conflict; correct whichever doc is wrong.
- **Q2 (semantics):** On a **non-contextually-secured** class, does `secureResultsUsingDomain=true` filter *instances*, or only gate by the operation domain? (Platform/XO-security SME needed — Brian Kilduff.)
- **Q3 (design intent):** Is object-level visibility on `/self` a **requirement** (recommended), or an **accepted, documented trade-off** (current audit stance)? The TDD never stated it; needs an explicit decision + security-advocate sign-off, especially given the "private/Agents-only" model.
- **Q4 (error contract):** Define the expected HTTP for an inaccessible valid WID (403 / 404 / 200-with-public-data) so it can be tested and documented.
- **Q5 (consistency):** Reconcile the internal tension inside the Implementation State page itself (§3 "SCR instance filtering secures which navigables" vs §4.2 "real security is not from the discriminator CRFs / class not contextually secured").
- **Q6 (prompts/filter):** Accept the unsecured `navigableFilters` prompt and the **additive** `navigableFilter` semantics, or constrain them.
