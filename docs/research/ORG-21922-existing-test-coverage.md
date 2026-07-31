# ORG-21922 — Org Chart REST API: Existing Test Coverage

**Target:** remote `orgchart` v1 (toggle ORG-21934). **Rule:** a happy-path functional test is **not** proof of security.

---

## 1. Existing tests found

| Source | Test asset | Endpoint(s) | Scenario | Security config | Test data | Assertion | Domain? | Object visibility? | Hidden obj? | Pagination? | Prompt enum? | Filter? |
|---|---|---|---|---|---|---|:--:|:--:|:--:|:--:|:--:|:--:|
| UTG `Org Chart REST API Method Bindings` (`22041$60986`) — `15-deferred §1`, `decisions.md` | **3 RSMB unit tests** (custom RSMBs) | resolution methods | Method binding returns expected set | mocked | mocked instanceData | binding output shape | No | No | No | No | No | No |
| Service op `usedInWatsRest` — `14-followup-system-test-story` | **5 WATS REST cases** | `/navigables/{ID}` (worker/org/pos), `/children`, `/parent` | basic GET returns expected type/body | toggle ON, real data | seeded WIDs | HTTP 200 + field presence | Partial (happy path) | No | No | No | No | No |
| **Confluence Smoke Test Results `4451737446` v7** (retrieved 2026-07-30; run 2026-06-10, SUV `i-073aded5e67683e74`) | **25-case manual smoke (25 PASS / 0 FAIL)** — groups A–I | all 6 | render, polymorphism, pagination, prompts, errors, **field stripping** | `lmcneil`/`oreynolds` (priv), `smorgan`/`tkerr` (restricted), no-proxy (403) | live Marvel GMS data | see per-group below | **I3=403 only** | **Field-level only** | No | E2/E3 pages | G2 additive | A2 search-req |
| WATS-11032 (blocked) — `decisions.md` | navigableType/hasParent/hasChildren RAMB unit tests | envelope flags | — | — | — | **could not run** (11 tests deleted) | No | No | No | No | No | No |

**Personas used in smoke:** privileged (`lmcneil`/`oreynolds`), restricted (`smorgan`/`tkerr` — `smorgan` is *not* the CEO on this SUV), no-proxy system context (for 403). **Verified live (exact case IDs):**
- **Layer 2 gate:** `I3` no-proxy → **403**.
- **Error contract:** `I1` all-zeros WID → **404**; `I2` malformed reference → **404** (no stack leak).
- **Layer 4 field stripping:** `H2/H3/H4` (Worker/embed/org), `H6`/`D1-sec` (POSITION `detail`→`{}`), plus the "Security differential" table — **but restricted personas still RECEIVE the node**; only fields are stripped (⇒ no object-level access gate demonstrated).
- Additive `navigableFilter` (`G2`/`D2`, org 6620: 9→10); pagination (`E2`/`E3`); empty parent (`F2`); prompt search-required (`A2` total 0), prompts A1/A3/A4.

> **Gap made explicit by the smoke evidence:** every field-stripping case (`H*`) targets nodes the restricted persona **can already see**. **No case tests a Worker/Org the persona genuinely cannot see** (hidden/out-of-hierarchy) fetched by direct WID — i.e. the BOLA/self hypothesis (T-01/T-02/T-06/T-18) is entirely uncovered. There is also **no test for an inaccessible-but-valid WID** (only invalid→404 and no-domain→403).

## 2. Coverage matrix

| Endpoint | Existing Tests | Domain Security | Object Visibility | Hidden Object | Pagination | Filter | Enumeration | Gaps |
|---|---|:--:|:--:|:--:|:--:|:--:|:--:|---|
| `GET /navigables/{ID}` | Smoke + WATS GET | ⚠️ happy-path | ❌ | ❌ | n/a | n/a | n/a | **No hidden-org/worker/pos test; no inaccessible-vs-invalid WID; no domain-less (403) test** |
| `/navigables/{ID}/children` | Smoke + WATS GET | ⚠️ | ⚠️ orgs only | ❌ | ❌ | ⚠️ additive observed | n/a | **Mixed visible/hidden children; worker/position child filtering; count/pagination leakage** |
| `/navigables/{ID}/parent` | Smoke + WATS GET | ⚠️ | ❌ | ❌ | ❌ | ❌ | n/a | **Hidden-parent disclosure; navigableFilter on parent** |
| `workers` prompt | Smoke | ⚠️ | ⚠️ (secured set) | ❌ | ❌ | n/a | ❌ | **Enumeration of out-of-scope workers; 1-char/exact-name; terminated workers** |
| `organizations` prompt | Smoke (A4) | ⚠️ | ⚠️ (ISD) | ❌ | ❌ | n/a | ❌ | **Enumeration; consistency vs /self** |
| `/children?navigableFilter=` | Smoke (additive) | ⚠️ | ❌ | ❌ | ❌ | ⚠️ | n/a | **Invalid-filter fallback; filter security boundary; unsecured navigableFilters prompt** |

Legend: ✅ covered · ⚠️ partial/happy-path only · ❌ not covered.

## 3. Missing scenarios (the security gap)
1. **Object-level authorization** on `/self` for hidden Org/Worker/Position (T-01, T-02, T-18) — *entirely absent*.
2. **Domain-less (User C) 403** on every endpoint (T-03) — not automated.
3. **Inaccessible vs invalid WID** existence oracle (T-06).
4. **Mixed visible/hidden children + counts + pagination** (T-04, T-10, T-11).
5. **Hidden parent** (T-05) and **relationship-flag** leakage (T-12).
6. **Prompt enumeration** beyond visible scope (T-07–T-09).
7. **Filter bypass / invalid-filter fallback** (T-13, T-14) and **recursive reconstruction** (T-15).
8. **Cross-endpoint consistency** (T-16) — the highest-value missing test.
9. **RAMB dispatch (navigableType/hasParent/hasChildren)** — *blocked* by WATS-11032; only coverable via system REST tests.

## 4. Automation recommendations
- **System-level WATS REST tests** are the right home for object-level authorization (they run against real tenant data, which the RAMB dispatch requires — unit mocks fail per WATS-11032). Extend suite `[SU]: Org Chart API`; land the follow-up story drafted in `14-followup-system-test-story.md` and **add the security cases T-01…T-18** to it (the draft currently covers functional + basic ESS only).
- **Do NOT** place Workday object-authorization tests in the local FastAPI `orgchart-api-tester`; that proves nothing about platform authorization (see `ORG-21922-automation-assessment` in the architect summary / Phase 9). The tester is at most a *manual exploration harness* for reproducing findings by switching users.
- Keep the 3 RSMB unit tests; treat them as **non-security** regression.
- Track WATS-11032 as a dependency; until resolved, RAMB-flag correctness (`hasParent`/`hasChildren` respecting visibility) can only be asserted via system REST tests (T-12).
