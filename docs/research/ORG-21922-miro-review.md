# ORG-21922 — Miro Threat Model Review (Phase 7)

**Board:** `https://miro.com/app/board/uXjVH2me7OQ=/` (linked from [ORG-21922](https://jira2.workday.com/browse/ORG-21922)).

> **Access limitation (important).** The Miro board is **auth-gated and could not be programmatically exported/read** during this review. Nothing below claims to reflect the board's *actual* contents. This document is a **reconciliation worksheet**: it uses only the board's **described scope** (from the ORG-21922 description — *"current API flow, endpoint inventory, STRIDE reference, and a first-pass security review for each endpoint"*) and maps my implementation-based findings against it. **Do not treat any row as a confirmed board fact until the board is exported and compared.** Every row is **TO CONFIRM against the exported board.**

To complete this phase properly, export the board (PDF/image) or paste its cells, and I will produce a definitive diff.

---

## 1. Reconciliation worksheet (implementation findings vs board's stated scope)

| Board area (described) | My implementation finding | Likely board state | Recommended action | TO CONFIRM |
|---|---|---|---|---|
| **API flow diagram** | 4-layer model: toggle → operation domain → SCR instance resolution → CRF field-level (review §2) | May show domain gate but under-represent the "instance resolution" layer | Ensure the flow explicitly shows **object-level visibility** as a *distinct* step from field-level stripping | ✔ |
| **Endpoint inventory** | 6 in-scope endpoints; **`positions` prompt removed (404)**; navigableFilters prompt is **unsecured** | May still list `positions`; may not flag prompt security divergence | Remove `positions`; annotate per-prompt security (workers=domain, orgs=ISD, navigableFilters=none) | ✔ |
| **STRIDE reference** | Emphasis on Information Disclosure + EoP; 13 threats catalogued (review §5) | Generic STRIDE table | Add the specific threats T-D01…T-E03 with endpoint + evidence | ✔ |
| **Per-endpoint first-pass review** | `/self` object-visibility **unproven/likely absent**; children filters orgs (workers/pos TO CONFIRM); prompts divergent | May assume "domain covers it" | Correct the assumption that domain = object authorization | ✔ |

## 2. Threats likely COVERED by the board (assumed)
- Authentication/spoofing (OAuth, tenant isolation) — platform-standard.
- Domain gate (Reports: Navigate Organization → 403).
- Read-only (no tampering/write vectors).

## 3. Threats likely MISSING or under-modeled (add these)
1. **BOLA on `GET /navigables/{ID}`** (T-D01) — direct-WID disclosure of hidden objects; the flagged "self" concern.
2. **Existence oracle** — inaccessible-valid vs invalid WID (T-D02).
3. **Inconsistent authorization across endpoints** (T-E03) — object hidden via `/children`/prompt but returned via `/self`.
4. **Relationship inference via `hasParent`/`hasChildren`** computed over full hierarchy (T-D05).
5. **Manager-identity disclosure** through any org node's `manager` embed (T-D06).
6. **Filter bypass / invalid-filter fallback** + **unsecured navigableFilters prompt** (T-E01).
7. **Pagination / count leakage** of hidden nodes (T-E02).
8. **`Navigable` class is not contextually secured** — the structural root cause; should be a first-class node on the board.

## 4. Incorrect assumptions to correct on the board
- "**Reports: Navigate Organization** secures the data" → it secures **endpoint access**, not **object visibility**.
- "**Field-level (Layer 4) filtering protects data**" → it protects *restricted fields*, **not** node existence or Public-Reporting-Items fields (name, type, manager identity, hasParent/hasChildren).
- "Prompt endpoints inherit the navigable security model" → **they diverge** (workers domain-filtered, orgs ISD, navigableFilters unsecured, positions removed).
- "`secureResultsUsingDomain` filters which navigables a user can see" → **disputed across docs** and **moot on a non-contextually-secured class** (review §3.3).

## 5. Controls PROVEN vs NOT PROVEN
- **Proven:** toggle gating; domain → 403 (design-level); CRF field-level stripping (ESS smoke-verified); read-only; no bulk dump (`getInstancesFromResourceClass=false`).
- **Not proven:** object-level visibility on `/self`; hidden-object exclusion from children counts/pagination; relationship-flag safety; filter non-bypass; cross-endpoint consistency.

## 6. Questions the board marked TO CONFIRM that this review can now inform
- Prompt filtering (ORG-22071 open Q) → **resolved in implementation**: workers now `Worker Secured [Singular]`; positions removed; navigableFilters unsecured (justified via exception). Update the board.
- Production domain → still **open** (Reports: Navigate Organization vs View: People-View Org Chart).

## 7. Recommended Miro updates (do not apply silently — for team review)
1. Add an explicit **"object-level visibility"** step to the flow, separate from field stripping.
2. Add the 8 missing/under-modeled threats (§3) as STRIDE cards with endpoint + evidence + severity.
3. Add a **root-cause card**: "Navigable class not contextually secured → no object-level domain securing possible."
4. Correct the 4 assumptions (§4).
5. Update endpoint inventory (remove positions; annotate prompt security).
6. Attach the test IDs (T-01…T-18) to each threat card as the validation plan.
7. Mark production-domain decision as an open owner-assigned item (Cliona).

## 8. Tests to add / remove (per board)
- **Add:** object-authorization suite (T-01…T-18), especially T-01/T-06/T-16/T-18.
- **Remove/reclassify:** treat existing happy-path smoke and RSMB unit tests as **functional**, not security evidence.

*Re-run this phase with an exported board to convert the worksheet into a definitive covered/missing diff.*
