# ORG-21922 — Architect Security Summary & Approval Review

**Reviewer role:** Principal Software Security Architect · **Date:** 2026-07-30
**Target:** remote Workday Org Chart REST API (`orgchart` v1, toggle ORG-21934)
**Companion docs:** implementation-security-review · security-test-plan · existing-test-coverage · miro-review · **tdd-reconciliation** (original TDD/Impl-State vs merged implementation)

---

## Executive summary

The Org Chart REST API is a **read-only, private (Agents-only), toggle-gated XO service** with a genuinely layered security design: a feature toggle, an operation-level domain (`Reports: Navigate Organization` → 403), instance resolution, and CRF field-level stripping that **provably works** for restricted worker fields (ESS smoke tests). For *field-level* confidentiality, the posture is sound.

**However, the object-level authorization story for the flagged `GET /navigables/{ID}` "self" endpoint is unproven and, on the balance of implementation evidence, likely not enforced.** The `Navigable` class is **not contextually secured** (securing its discriminator CRFs by domain threw a *Critical* exception and was reverted to `Public Reporting Items`), and the singular lookup uses `Instance@get This Instance(GSS)(public)` — a "resolve any WID" binding. The design docs **contradict each other** on the decisive SCR flag (`secureResultsUsingDomain` true vs false). The net effect, if the pessimistic reading holds, is that any caller holding the domain can retrieve the **existence, name/descriptor, type, manager identity, `hasParent`/`hasChildren`, and all Public-Reporting-Items fields** of *any* Navigable WID — including objects they cannot reach by navigation — while `/children` *does* filter (at least organizations). That asymmetry is a classic **Broken Object Level Authorization / information-disclosure** risk and is exactly what Robert flagged.

Because the highest-severity behavior is **TO CONFIRM** (needs a live-SUV test), and the platform itself tags this API with the **"Protected API Security Review Required"** graph constraint, I cannot approve today.

## Major risks (top 5)
1. **BOLA on `/navigables/{ID}` (self):** direct-WID disclosure of hidden Orgs/Workers/Positions' existence + public fields. *Severity: High. Status: Potential/TO CONFIRM.* (T-01, T-02, T-18)
2. **Inconsistent authorization across endpoints:** an object hidden via `/children`/prompt but returned via `/self`. *High. Potential.* (T-16)
3. **Existence oracle & relationship inference:** inaccessible-valid vs invalid WID distinguishable; `hasParent`/`hasChildren` computed over the full hierarchy. *Medium.* (T-06, T-12)
4. **Prompt/filter enumeration & filter bypass:** unsecured `navigableFilters` prompt; additive filter; possible invalid-filter fallback; worker/org enumeration within scope. *Medium.* (T-07–T-09, T-13, T-14)
5. **Pagination/count leakage of hidden nodes** and **worker/position children possibly less filtered than orgs**. *Medium.* (T-04, T-10, T-11)

## Mandatory tests before approval
P0 (blocking): **T-01, T-02, T-03, T-06, T-16, T-18**. Strongly recommended before GA: T-04, T-05, T-10–T-14. All defined in the test plan; all require a live SUV with Users A–D and seeded hidden objects.

> **Update (2026-07-30):** the original Confluence TDD + Implementation State were retrieved and reconciled (`ORG-21922-tdd-reconciliation.md`). They **strengthen** this finding: Implementation State §4.2 confirms verbatim that the Navigable class is *not contextually secured* and "real security … is not [from] the discriminator CRFs", and the smoke results (H2–H6/D1-sec) show restricted users are **never denied a node — only fields are stripped**. The `secureResultsUsingDomain` conflict now weighs **3 docs `true` : 1 `false`**, but is **moot for Worker/Org** object visibility. HTTP contract confirmed: no-domain→403, invalid→404; **inaccessible-valid WID remains undefined/untested**.

## Assumptions requiring team confirmation
- **TO CONFIRM #1:** exact live-metadata value of `secureResultsUsingDomain` (docs lean `true`) / `instanceBasedSecurityCompatibility` (unresolved; Confluence silent) on `orgchart/navigables`.
- **TO CONFIRM #1b (deeper):** on a non-contextually-secured class, does `secureResultsUsingDomain=true` filter *instances* at all, or only gate by the operation domain? (XO-security SME — Brian Kilduff.)
- Expected HTTP for an inaccessible-but-valid WID (403 vs 404 vs 200-empty) — define the contract.
- Whether worker/position children are visibility-checked as strictly as orgs.
- Production domain decision (Reports: Navigate Organization vs View: People-View Org Chart) — owner **Cliona**.
- Acceptability of the unsecured `navigableFilters` prompt (currently justified via exception #9/#10).

## Findings needing new Jira issues
- **New Security bug (Potential, pending T-01/T-18):** "Object-level visibility not enforced on GET /navigables/{ID}." Link ORG-21922 / Epic ORG-21726.
- **New task:** "Define & document Org Chart API error contract for inaccessible objects (403/404/empty)."
- **New test story:** extend `[SU]: Org Chart API` (build on `14-followup-system-test-story.md`) with security cases T-01…T-18.
- **Track:** WATS-11032 dependency; production-domain decision (already in ORG-22071).

## Implementation bugs vs documentation gaps
- **Doc gap / decision, not yet a bug:** conflicting `secureResultsUsingDomain` statements; production-domain TBD; children RSMB `+???` marker; parent `navigableFilter` presence.
- **Potential implementation bug (pending live proof):** `/self` returning hidden objects' public data; invalid-filter fallback; hidden nodes in counts/pagination.
- **Working as intended:** field-level stripping; read-only; no bulk dump; positions prompt removal.

## Highest-risk endpoints (ranked)
1. `GET /navigables/{ID}` (self) — BOLA epicenter.
2. `GET /navigables/{ID}/children` (+ `navigableFilter`) — enumeration/pagination/filter surface.
3. `GET /navigables/{ID}/parent` — hidden-parent inference.
4. `workers` / `organizations` prompts — enumeration & cross-endpoint consistency.

## For the team review
- Resolve the `secureResultsUsingDomain` conflict from live metadata **first**.
- Agree the inaccessible-object HTTP contract.
- Decide whether object-level visibility on `/self` is a requirement (recommended: **yes**) or an accepted, documented design trade-off (the current audit's stance) — and if accepted, get **explicit security-advocate (Brian Kilduff) sign-off** given the "private/Agents-only" framing, since agents may act with broader reach than a human UI user.
- Confirm prompt-security divergence is intentional.

---

## Phase 9 — Automation assessment

| Test | Classification |
|---|---|
| T-03 (domain 403), T-17 (PII fields) | **Suitable for integration automation** (deterministic, real data) |
| T-01, T-02, T-04–T-16, T-18 | **Requires live SUV + security configuration** (Users A–D, hidden objects) → integration automation *after* one-time manual confirmation |
| RAMB flag correctness (T-12) | **Blocked for unit** by WATS-11032 → system REST only |
| 3 existing RSMB unit tests | **Existing automated coverage** (functional, non-security) |

**Automation proposal**
- **Repository:** the **Org Chart API metadata/test repo** (WATS suite `[SU]: Org Chart API`, UTG `22041$60986`) — *not* the local FastAPI tester. Workday object authorization is a platform behavior; only a live-SUV WATS REST suite can validate it.
- **What to mock:** essentially nothing for the security assertions — object authorization depends on real tenant hierarchy + real security profiles (mocks fail per WATS-11032). Mocking is appropriate only for the local tester's *own* logic (already done, separate work).
- **What must run against a real SUV:** all of T-01…T-18.
- **Credential handling:** per-user OAuth refresh tokens stored outside the repo (env/secret store), redact `Authorization` in evidence, never commit tokens/passwords/cookies.
- **Test isolation:** read-only API → naturally isolated; ensure Users A–D and seeded hidden objects are stable fixtures on a dedicated SUV.
- **Required tenant setup:** toggle ON, target service published, hidden org/worker/position seeded, domain grant/revoke for User C/D.
- **CI suitability:** gate on SUV availability; run as a scheduled/manual security suite, not per-commit.
- **Risk of false confidence from mocked security tests:** **HIGH** — a mocked test of the FastAPI tester (or mocked XO instances) can "pass" while the real platform discloses hidden objects. Object-level authorization MUST be proven on real data. Do not let the local tester's green suite be read as evidence for ORG-21922.

---

## Conclusion

# DO NOT APPROVE YET

**Rationale:** The decisive object-level authorization behavior on `GET /navigables/{ID}` remains **TO CONFIRM**, the governing SCR setting is **contradicted across design docs**, and there is **no test** proving hidden Organizations/Workers/Positions are protected from direct-WID access or that authorization is consistent across endpoints. Per the review rules, APPROVE is not permissible while important object-level authorization behavior is unresolved.

**Path to APPROVE WITH CONDITIONS:** (1) resolve TO-CONFIRM #1 from live metadata; (2) execute P0 tests T-01/T-02/T-03/T-06/T-16/T-18 on a SUV with evidence; (3) if `/self` does not enforce object visibility, either implement enforcement or obtain explicit, documented security-advocate acceptance of the trade-off; (4) define the inaccessible-object HTTP contract; (5) land the security test story. If all pass/served, this moves to **APPROVE WITH CONDITIONS** for Preview.
