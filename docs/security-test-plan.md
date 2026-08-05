# ORG-21922 — Org Chart REST API: Security Test Plan

> **Canonical document (v4.1):** [`docs/ORG-21922-security-validation-plan.md`](ORG-21922-security-validation-plan.md)

This filename is retained for backward compatibility. All execution, evidence, and Skylab sign-off use the **Security Validation Plan v4.1** linked above.

**Quick reference:**
- **Environment:** Skylab `performance` (official) · SUV optional sanity only
- **Primary control:** Organization Visibility (`Everyone` / `Role Assignees`)
- **Endpoints:** navigables self, children, parent, workers prompt, organizations prompt, children+navigableFilter
- **Test IDs:** OC-NAV / OC-CHILD / OC-PARENT / OC-WRK / OC-ORG / OC-FLT / OC-X
