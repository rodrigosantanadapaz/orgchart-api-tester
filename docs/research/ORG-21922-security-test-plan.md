# ORG-21922 — Org Chart REST API: Security Test Plan

**Target:** remote Workday Org Chart REST API (`orgchart` v1), toggle **ORG-21934**.
**Companion:** `ORG-21922-implementation-security-review.md` (findings this plan validates).
**Status legend (per case):** `NOT RUN` · `PASS` · `FAIL` · `BLOCKED` · `NEEDS INVESTIGATION`
**HTTP expectation legend:** where the contract does not define whether an inaccessible object returns 403/404/empty, the case is marked **TO CONFIRM** and the test's job is to *establish* the behavior.

---

## 1. Purpose
Validate, against a live SUV, whether the Org Chart REST API enforces authentication, the `Reports: Navigate Organization` domain, **object-level visibility**, and non-disclosure of hidden Organizations/Workers/Positions, relationships, counts, and PII — with special attention to `GET /navigables/{ID}` (the "self" endpoint flagged by Robert) and to prompt/filter enumeration paths.

## 2. Scope
The 6 in-scope endpoints only: `GET /navigables/{ID}`, `/navigables/{ID}/children`, `/navigables/{ID}/parent`, `GET /values/orgChartPrompts/workers`, `GET /values/orgChartPrompts/organizations`, `GET /navigables/{ID}/children?navigableFilter=…`. Dependencies included only where in the authorization flow (singular RSMB, children/parent RSMBs, prompt work sets, Layer-4 CRFs).

## 3. Out of scope
- Local `orgchart-api-tester` FastAPI app security (covered separately; do not conflate).
- Performance/load ([ORG-21938](https://jira2.workday.com/browse/ORG-21938)) — except where large result sets, pagination, or recursion affect *security enforcement* (T-10, T-11, T-15).
- Write operations (none exist — read-only API).
- The `positions` prompt (removed in v1; returns 404).
- Cross-tenant testing (platform tenant isolation assumed).

## 4. Architecture summary
Four security layers: (1) toggle ORG-21934, (2) operation domain *Reports: Navigate Organization* (→403), (3) SCR instance resolution (`secureResultsUsingDomain`/`instanceBasedSecurityCompatibility` — **value disputed**, singular binding is `This Instance(GSS)(public)`), (4) CRF field-level domains (silent field stripping, ESS-verified). See review doc §2–§3.

## 5. Security model under test
- **Endpoint gate** proven (domain → 403). **Object-level visibility on `/self` is unproven and likely absent** because the `Navigable` class is *not contextually secured* (CRF-domain securing threw a Critical exception and was reverted to `Public Reporting Items`). Field stripping protects *restricted fields only*, not node existence or Public-Reporting-Items fields.
- **Prompts diverge:** workers = `Worker Secured [Singular]` (domain-filtered), orgs = Organization ISD, navigableFilters = unsecured, positions = removed.

## 6. Assumptions
- The SUV has toggle ORG-21934 ON and the target service (not the POC) published.
- Demo hierarchy has hidden/restricted orgs relative to at least one ESS user (e.g. tkerr).
- Platform OAuth + tenant isolation work as designed (not re-tested here).
- `Reports: Navigate Organization` is the domain under test (production domain TBD).

## 7. Preconditions
- VPN + SUV reachable; OAuth client + refresh tokens per test user; toggle ON.
- Known WIDs seeded per §10; ability to grant/revoke the domain and object-level access for User C/D.
- Trace logging available to distinguish "domain 403" from "empty/allowed".

## 8. Required test users
| User | Access profile | Purpose |
|---|---|---|
| **User A** | Full access + `Reports: Navigate Organization` (e.g. `oreynolds`/CEO-level) | Baseline "everything visible" |
| **User B** | Has domain; **restricted hierarchy** (can see own subtree only) (e.g. `tkerr` / `lmcneil`) | Object-visibility deltas |
| **User C** | Authenticated, **WITHOUT** `Reports: Navigate Organization` | Domain-gate (403) tests |
| **User D** | Has domain; **segmented** — can see a source node but NOT all of its parents/children | Mixed visible/hidden traversal |

> Note (data caveat from `memory/decisions.md`): `smorgan` was restricted on the build SUV and `oreynolds` was used as the privileged persona — pick personas per the SUV's actual policy, not by title.

## 9. Required security configurations
- Toggle ORG-21934 ON.
- A **hidden Organization** and a **hidden Worker** that User B/D cannot reach by navigation but whose WIDs are known to the tester.
- A **visible parent org** with **mixed visible+hidden children** (incl. an unfilled position).
- A **visible node with a hidden parent** for User D.

## 10. Required test data
| Item | Symbol | Notes |
|---|---|---|
| Visible Organization WID | `ORG_VIS` | e.g. 1000 GMS |
| Hidden Organization WID | `ORG_HID` | not reachable by User B via nav |
| Visible Worker WID | `WKR_VIS` | e.g. CEO |
| Hidden Worker WID | `WKR_HID` | in a hidden org |
| Visible Position WID | `POS_VIS` | unfilled position child of ORG_VIS |
| Hidden Position WID | `POS_HID` | in hidden subtree |
| Visible object w/ hidden parent | `CHILD_HP` | for User D |
| Visible parent w/ mixed children | `PARENT_MIX` | some children hidden to User B |
| Multi-page hierarchy | `ORG_BIG` | e.g. CEO 142 children |
| Invalid WID | `WID_BAD` | malformed / 32-hex nonexistent |
| Nonexistent valid-format WID | `WID_GHOST` | correct pattern, no object |
| Search term (visible+hidden matches) | `SEARCH_MIX` | matches names across visibility |
| Valid navigableFilter | `FLT_OK` | e.g. Open Positions `6ea473c87495100024a9b7cd96820030` |
| Invalid navigableFilter | `FLT_BAD` | bogus/unauthorized WID |

## 11. Endpoint test cases

> Each case: **Test ID · Priority · Endpoint · Risk · Objective · Preconditions · Required user · Required data · Steps · Expected security behavior · Expected HTTP · Evidence · Impl ref · Existing coverage · Automation · Manual? · Potential Jira title if failed · Confidence · Status.**

### T-01 — Direct access to a HIDDEN Organization via self **(MANDATORY #1)**
- **Priority:** P0 · **Endpoint:** `GET /navigables/{ORG_HID}` · **Risk:** BOLA / Info-Disclosure (T-D01)
- **Objective:** Prove whether a restricted user can retrieve an org they cannot navigate to.
- **Preconditions:** ORG_HID hidden to User B. **Required user:** User B. **Data:** `ORG_HID`.
- **Steps:** As User B, GET `/navigables/{ORG_HID}`. Repeat as User A (control).
- **Expected security behavior:** User B should **not** learn the org's existence, name, manager identity, or `hasChildren`.
- **Expected HTTP:** **TO CONFIRM** (should be 404 or 403; **must not** be 200-with-data). 
- **Evidence:** full response bodies + status for A and B; trace log.
- **Impl ref:** review §3.3, §4.1; `This Instance(GSS)(public)`; decisions.md revert.
- **Existing coverage:** none. **Automation:** integration (WATS REST, live). **Manual?** Yes initially.
- **Potential Jira if FAIL:** "Org Chart API discloses hidden Organizations via GET /navigables/{ID} (BOLA)."
- **Confidence:** Medium it will FAIL. **Status:** NOT RUN.

### T-02 — Direct access to HIDDEN Worker and Position via self **(MANDATORY #2)**
- **Priority:** P0 · **Endpoint:** `GET /navigables/{WKR_HID}`, `/navigables/{POS_HID}` · **Risk:** BOLA / PII (T-D01, T-D06)
- **Objective:** Same as T-01 for Worker and Unfilled Position subtypes (verify per-type behavior).
- **Required user:** User B. **Data:** `WKR_HID`, `POS_HID`.
- **Steps:** GET each as User B; compare to User A.
- **Expected security behavior:** hidden worker/position existence + public fields not disclosed to User B.
- **Expected HTTP:** **TO CONFIRM.** **Evidence:** bodies/status. **Impl ref:** §4.1.
- **Automation:** integration. **Manual?** Yes. **Confidence:** Medium FAIL. **Status:** NOT RUN.
- **Potential Jira if FAIL:** "Org Chart API discloses hidden Worker/Position public fields via direct WID."

### T-03 — Authenticated user WITHOUT the domain **(MANDATORY #3)**
- **Priority:** P0 · **Endpoint:** all 6 · **Risk:** EoP / domain gate
- **Objective:** Confirm 403 for every endpoint when `Reports: Navigate Organization` is absent.
- **Required user:** User C. **Data:** any valid WID/search.
- **Steps:** Call each endpoint as User C.
- **Expected security behavior:** access denied at gate; no data, no prompt values.
- **Expected HTTP:** **403** on all. **Evidence:** status per endpoint. **Impl ref:** §3.1 (domain High).
- **Existing coverage:** none automated. **Automation:** integration. **Manual?** No (automatable).
- **Confidence:** High PASS. **Status:** NOT RUN. **Jira if FAIL:** "Org Chart API accessible without Reports: Navigate Organization."

### T-04 — Visible parent with MIXED visible/hidden children **(MANDATORY #4)**
- **Priority:** P0 · **Endpoint:** `GET /navigables/{PARENT_MIX}/children` · **Risk:** hierarchy enumeration / pagination
- **Required user:** User B. **Data:** `PARENT_MIX` (some children hidden to B).
- **Steps:** GET children as A (full set) then B; diff sets and `total`.
- **Expected security behavior:** B's response omits hidden children **and** hidden children are **not** reflected in `total` or any count.
- **Expected HTTP:** 200 (filtered). **Evidence:** both bodies, `total`, page counts.
- **Impl ref:** §4.2; CONTEXT.md (orgs filtered; workers/positions TO CONFIRM). **Automation:** integration. **Manual?** Yes.
- **Confidence:** Medium (orgs pass; worker/position children TO CONFIRM). **Status:** NOT RUN.
- **Jira if FAIL:** "Org Chart API leaks hidden children (or their count) via /children."

### T-05 — Visible child with a HIDDEN parent **(MANDATORY #5)**
- **Priority:** P1 · **Endpoint:** `GET /navigables/{CHILD_HP}/parent` · **Risk:** relationship inference (T-D04)
- **Required user:** User D. **Data:** `CHILD_HP` (parent hidden to D).
- **Steps:** GET parent as D; compare to A.
- **Expected security behavior:** hidden parent's existence/WID/name/type not disclosed to D.
- **Expected HTTP:** 200 with empty/omitted parent, or 403/404 — **TO CONFIRM.**
- **Impl ref:** §4.3 (`suppressParentSecurityEvaluation=false`). **Automation:** integration. **Manual?** Yes.
- **Confidence:** Medium. **Status:** NOT RUN. **Jira if FAIL:** "Org Chart API reveals hidden parent via /parent."

### T-06 — Invalid WID vs INACCESSIBLE valid WID response comparison **(MANDATORY #6)**
- **Priority:** P0 · **Endpoint:** `GET /navigables/{ID}` · **Risk:** existence oracle (T-D02)
- **Required user:** User B. **Data:** `WID_BAD`, `WID_GHOST`, `ORG_HID`.
- **Steps:** GET each; record status, body, headers, timing.
- **Expected security behavior:** an inaccessible-but-valid object must be **indistinguishable** from a nonexistent one (no existence oracle).
- **Expected HTTP:** invalid → **404** (confirmed in smoke); inaccessible valid → **TO CONFIRM** (should match 404).
- **Evidence:** status/body/headers/timing table. **Impl ref:** §5 T-D02. **Automation:** integration. **Manual?** Yes.
- **Confidence:** Medium FAIL (likely distinguishable). **Status:** NOT RUN.
- **Jira if FAIL:** "Org Chart API leaks object existence (inaccessible WID distinguishable from invalid)."

### T-07 — Worker prompt exact & partial-name enumeration **(MANDATORY #7)**
- **Priority:** P1 · **Endpoint:** `GET /values/orgChartPrompts/workers?search=` · **Risk:** enumeration/PII (T-D03)
- **Required user:** User B. **Data:** `SEARCH_MIX`, exact name of `WKR_HID`, 1-char search.
- **Steps:** As B, search exact hidden-worker name, partial, and 1-char; compare to A.
- **Expected security behavior:** results limited to workers within B's `Worker Secured` domain scope; hidden workers absent.
- **Expected HTTP:** 200. **Evidence:** result sets + totals for A/B. **Impl ref:** §4.4 (Worker Secured [Singular]).
- **Automation:** integration. **Manual?** Yes. **Confidence:** Medium-High PASS. **Status:** NOT RUN.
- **Jira if FAIL:** "Worker prompt enumerates workers outside caller's security scope."

### T-08 — Organization prompt exact & partial-name enumeration **(MANDATORY #8)**
- **Priority:** P1 · **Endpoint:** `GET /values/orgChartPrompts/organizations?search=` · **Risk:** enumeration/consistency
- **Required user:** User B. **Data:** exact `ORG_HID` name, partial, 1-char.
- **Steps:** Search as B and A; diff.
- **Expected security behavior:** ORG_HID absent for B (ISD-secured).
- **Expected HTTP:** 200. **Impl ref:** §4.5. **Automation:** integration. **Manual?** Yes.
- **Confidence:** Medium. **Status:** NOT RUN. **Jira if FAIL:** "Org prompt lists organizations outside caller scope."

### T-09 — Broad prompt searches return only visible objects **(MANDATORY #9)**
- **Priority:** P2 · **Endpoint:** workers + orgs prompts · **Risk:** bulk harvest
- **Required user:** User B. **Data:** empty/broad search, `limit=1000`.
- **Steps:** Broad search as B; verify every returned item is independently visible.
- **Expected:** no hidden items in large result set. **Expected HTTP:** 200. **Automation:** integration. **Manual?** Partial.
- **Confidence:** Medium. **Status:** NOT RUN.

### T-10 — Pagination across a mixed-security hierarchy **(MANDATORY #10)**
- **Priority:** P1 · **Endpoint:** `/navigables/{ORG_BIG}/children?limit=&offset=` · **Risk:** pagination leakage (T-E02)
- **Required user:** User B. **Data:** `ORG_BIG` with hidden children scattered across pages.
- **Steps:** Page through all children with small `limit`; check no hidden node appears on any page and offsets stay stable.
- **Expected:** hidden nodes never surface; page boundaries consistent. **Expected HTTP:** 200.
- **Impl ref:** §5 T-E02. **Automation:** integration. **Manual?** Yes. **Confidence:** TO CONFIRM. **Status:** NOT RUN.
- **Jira if FAIL:** "Hidden children surface on later pages of /children."

### T-11 — Hidden objects not in total counts / metadata **(MANDATORY #11)**
- **Priority:** P1 · **Endpoint:** collections · **Risk:** count leakage
- **Steps:** Compare `total` for A vs B on `PARENT_MIX`/`ORG_BIG`; verify B's `total` == count of visible children.
- **Expected:** `total` reflects **caller-visible** set only. **Expected HTTP:** 200. **TO CONFIRM.**
- **Automation:** integration. **Manual?** Yes. **Status:** NOT RUN.

### T-12 — `hasParent`/`hasChildren` do not reveal restricted relationships **(MANDATORY #12)**
- **Priority:** P1 · **Endpoint:** `/navigables/{ID}` · **Risk:** relationship inference (T-D05)
- **Steps:** On a node where B's only children/parents are hidden, read `hasChildren`/`hasParent`; compare to A.
- **Expected:** flags reflect **caller-visible** relations (if B has no visible children, `hasChildren=false`). 
- **Expected HTTP:** 200. **Impl ref:** §5 T-D05; 15-deferred §11. **TO CONFIRM.** **Automation:** integration. **Manual?** Yes.
- **Status:** NOT RUN. **Jira if FAIL:** "hasParent/hasChildren computed over full hierarchy leak hidden relations."

### T-13 — Filtered vs unfiltered children keep the SAME security boundary **(MANDATORY #13)**
- **Priority:** P1 · **Endpoint:** `/navigables/{ID}/children?navigableFilter=FLT_OK` · **Risk:** filter bypass (T-E01)
- **Steps:** As B, call children with and without `FLT_OK`; verify filter only changes *selection*, never exposes hidden nodes.
- **Expected:** filtered set ⊆ (unfiltered visible set ∪ intended additive nodes), all independently visible.
- **Expected HTTP:** 200. **Impl ref:** §4.6 (additive filter). **Automation:** integration. **Manual?** Yes. **Status:** NOT RUN.

### T-14 — Invalid `navigableFilter` does NOT fall back to unrestricted **(MANDATORY #14)**
- **Priority:** P1 · **Endpoint:** `/navigables/{ID}/children?navigableFilter=FLT_BAD` · **Risk:** filter bypass
- **Steps:** Send bogus/unauthorized/malformed filter values as B.
- **Expected:** 400 (validation) or an *empty/again-secured* set — **never** an unfiltered superset. **Expected HTTP:** **TO CONFIRM** (400 vs 200-empty).
- **Automation:** integration. **Manual?** Yes. **Status:** NOT RUN. **Jira if FAIL:** "Invalid navigableFilter falls back to unrestricted children."

### T-15 — Recursive traversal cannot reconstruct a hidden hierarchy **(MANDATORY #15)**
- **Priority:** P1 · **Endpoint:** children+parent (recursive) · **Risk:** hierarchy enumeration (T-D04)
- **Steps:** As B, recurse children/parent from visible roots; verify the reachable graph excludes hidden subtrees.
- **Expected:** no hidden org/worker/position reachable via any traversal path. **Expected HTTP:** 200.
- **Automation:** integration (scripted crawl). **Manual?** Yes. **Confidence:** Medium. **Status:** NOT RUN.

### T-16 — Consistent authorization across self / prompt / parent / children **(MANDATORY #16)**
- **Priority:** P0 · **Endpoint:** all · **Risk:** inconsistent authz (T-E03)
- **Steps:** For `ORG_HID`/`WKR_HID`, as B: (a) direct self, (b) prompt search, (c) as a child of a visible parent, (d) as a parent of a visible child — record visible/hidden verdict for each path.
- **Expected:** **identical** authorization verdict across all four paths.
- **Expected HTTP:** consistent. **Impl ref:** §5 T-E03. **Automation:** integration. **Manual?** Yes.
- **Confidence:** Medium FAIL (self likely inconsistent with children/prompt). **Status:** NOT RUN.
- **Jira if FAIL:** "Inconsistent object authorization: object hidden via /children but returned via /navigables/{ID}."

### T-17 — Response fields do not expose unnecessary PII **(MANDATORY #17)**
- **Priority:** P2 · **Endpoint:** self/children · **Risk:** excessive data / PII (T-D07)
- **Steps:** As B (cross-worker) inspect returned fields vs the documented Layer-4 matrix; confirm restricted fields stripped and only intended public fields present.
- **Expected:** matches `13-security-audit` matrix (email/photo/orgMembership public; phone/fte/positions stripped).
- **Expected HTTP:** 200. **Existing coverage:** ESS smoke (partial). **Automation:** integration. **Manual?** No.
- **Confidence:** High PASS. **Status:** NOT RUN.

### T-18 — Domain access alone does not bypass object-level visibility **(MANDATORY #18)**
- **Priority:** P0 · **Endpoint:** `/navigables/{ID}` · **Risk:** the core BOLA hypothesis
- **Steps:** User B (has domain) attempts `ORG_HID`/`WKR_HID` via self; confirm the domain grant does **not** by itself yield the object.
- **Expected:** object not returned merely because the domain is held. **Expected HTTP:** **TO CONFIRM.**
- **This is the summarizing assertion for T-01/T-02/T-16.** **Automation:** integration. **Manual?** Yes.
- **Confidence:** Medium FAIL. **Status:** NOT RUN. **Jira if FAIL:** "Reports: Navigate Organization alone grants any-WID object access."

## 12. Cross-endpoint tests
T-16 (consistency) and T-15 (recursive reconstruction) are the primary cross-endpoint cases. Add **T-19 (self vs children consistency for the same node set)** and **T-20 (prompt WID → self)**: take a WID from a prompt as User B and confirm `/self` returns the *same* visibility verdict.

## 13. Negative tests
`WID_BAD`/`WID_GHOST` (T-06), `FLT_BAD` (T-14), User C domain-less (T-03), malformed `ID` not matching `^([0-9a-f]{32})|(\S+=\S+)$` → expect 400, oversized `limit` (>100 nav / >1000 prompt) → clamp/400.

## 14. Evidence requirements
For every case capture: request URL + user identity, HTTP status, **full response body**, response headers (`wd-stat-request-id`, rate-limit headers, content-type), server-side trace where available, and A-vs-B/D diffs. **Never** store passwords/tokens/cookies in evidence files (redact `Authorization`). Store under `evidence/<test-id>/`.

## 15. Defect handling
Any FAIL that discloses hidden objects/relationships/counts/PII → raise a **Security bug** on Epic ORG-21726, link ORG-21922, set severity per review §5, and block GA. Use the "Potential Jira title if failed" strings above. Attach redacted evidence.

## 16. Entry criteria
- SUV with toggle ORG-21934 ON + target service published; Users A–D provisioned; test data §10 seeded; trace logging on; TO-CONFIRM #1 (SCR settings) resolved from metadata.

## 17. Exit criteria
- All P0 (T-01,T-02,T-03,T-06,T-16,T-18) executed with evidence; no open High/Critical disclosure defect; expected-HTTP TO-CONFIRM items resolved into a documented contract; object-level visibility on `/self` **proven** (either enforced, or a bug is filed and fixed).

## 18. Open questions
Mirror review §6 — resolve #1 (SCR settings) and #2 (inaccessible-WID HTTP code) before P0 execution.

## 19. Approval recommendation (from this plan)
Do **not** grant Preview/Production sign-off until T-01/T-02/T-06/T-16/T-18 PASS on a live SUV. See `ORG-21922-architect-summary.md`.

---

### Test index & results template

| Test ID | Endpoint | Risk | Priority | Automation | Manual? | Expected HTTP | Confidence | Status |
|---|---|---|---|---|---|---|---|---|
| T-01 | /navigables/{ID} | BOLA hidden org | P0 | Integration | Yes | TO CONFIRM | Med FAIL | NOT RUN |
| T-02 | /navigables/{ID} | BOLA hidden wkr/pos | P0 | Integration | Yes | TO CONFIRM | Med FAIL | NOT RUN |
| T-03 | all | domain 403 | P0 | Integration | No | 403 | High PASS | NOT RUN |
| T-04 | /children | mixed children | P0 | Integration | Yes | 200 filtered | Med | NOT RUN |
| T-05 | /parent | hidden parent | P1 | Integration | Yes | TO CONFIRM | Med | NOT RUN |
| T-06 | /navigables/{ID} | existence oracle | P0 | Integration | Yes | 404 vs TO CONFIRM | Med FAIL | NOT RUN |
| T-07 | workers prompt | enumeration | P1 | Integration | Yes | 200 | Med-High | NOT RUN |
| T-08 | orgs prompt | enumeration | P1 | Integration | Yes | 200 | Med | NOT RUN |
| T-09 | prompts | broad harvest | P2 | Integration | Partial | 200 | Med | NOT RUN |
| T-10 | /children | pagination leak | P1 | Integration | Yes | 200 | TO CONFIRM | NOT RUN |
| T-11 | collections | count leak | P1 | Integration | Yes | 200 | TO CONFIRM | NOT RUN |
| T-12 | /navigables/{ID} | relationship flags | P1 | Integration | Yes | 200 | TO CONFIRM | NOT RUN |
| T-13 | /children?filter | filter boundary | P1 | Integration | Yes | 200 | Med | NOT RUN |
| T-14 | /children?filter | invalid filter | P1 | Integration | Yes | TO CONFIRM | Med | NOT RUN |
| T-15 | children+parent | recursion | P1 | Integration | Yes | 200 | Med | NOT RUN |
| T-16 | all | consistency | P0 | Integration | Yes | consistent | Med FAIL | NOT RUN |
| T-17 | self/children | PII | P2 | Integration | No | 200 | High PASS | NOT RUN |
| T-18 | /navigables/{ID} | domain≠object | P0 | Integration | Yes | TO CONFIRM | Med FAIL | NOT RUN |
