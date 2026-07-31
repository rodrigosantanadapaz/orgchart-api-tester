*Security design review — progress update (implementation-based)*

*What was reviewed*
Implementation-based security design review of the remote Org Chart REST API (orgchart v1, toggle ORG-21934), scoped to the 6 endpoints: GET /navigables/{ID}, /children, /parent, prompts (workers, organizations) and /children?navigableFilter. Sources: merged code-review patch (xo-code-reviews/ORG raw_changes), ORG-22063 design + security-audit plans, readiness scorecards, FDSPA (ORG-21974), ORG-22071 follow-ups, TDD digest. (The local FastAPI tester was explicitly excluded.)

*What was found*
- Security model is 4-layer: toggle → operation domain (Reports: Navigate Organization → 403) → SCR instance resolution → CRF field-level stripping. Field-level ESS stripping is verified (smoke tests) and read-only/no-bulk-dump posture is good.
- Prompt security is now resolved (workers → Worker Secured [Singular], domain-filtered; positions removed/404; navigableFilters unsecured; orgs via ISD) — this answers the ORG-22071 open question, but prompts diverge from the navigable model.
- KEY CONCERN (Robert's flag substantiated): object-level visibility on GET /navigables/{ID} is likely NOT enforced. The Navigable class is not contextually secured (CRF domain-securing threw a Critical exception and was reverted to Public Reporting Items), and the singular binding is Instance@get This Instance(GSS)(public). So a caller with the domain may retrieve any WID's existence + public fields + manager identity + hasParent/hasChildren, even for objects not navigable to them — while /children does filter orgs. Potential BOLA / information-disclosure + inconsistent authorization.

*What remains TO CONFIRM*
1. Merged value of secureResultsUsingDomain / instanceBasedSecurityCompatibility on orgchart/navigables (design docs 04/05/16 say true; 13-security-audit says false).
2. HTTP for an inaccessible-but-valid WID (403 / 404 / 200-with-data?).
3. Whether worker/position children are visibility-filtered as strictly as orgs.
4. Whether hasParent/hasChildren and collection totals reflect the caller-visible vs full hierarchy.
5. Children RSMB "+???" review marker; navigableFilter on /parent; invalid-filter fallback behavior.
6. Production domain (Reports: Navigate Organization vs View: People-View Org Chart) — owner Cliona.

*Approval recommendation:* DO NOT APPROVE YET (object-level authorization behavior unresolved; platform tags API "Protected API Security Review Required").

*Next steps*
- Resolve TO-CONFIRM #1 from live SUV metadata.
- Execute P0 live tests on a SUV: hidden Org via /self (T-01), hidden Worker/Position (T-02), domain-less 403 (T-03), invalid-vs-inaccessible WID (T-06), cross-endpoint consistency (T-16), domain≠object (T-18).
- Extend [SU]: Org Chart API with the security suite (build on the ORG-21726 follow-up system-test story); track WATS-11032.
- Deliverables prepared: implementation-security-review, security-test-plan (18 mandatory cases), existing-test-coverage matrix, miro-review worksheet, architect-summary.

(Miro threat model board is referenced but was not accessible for this pass; a reconciliation worksheet + recommended updates are included and can be finalized against an exported board.)
