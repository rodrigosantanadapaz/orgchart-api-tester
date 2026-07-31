# Security

## Reporting vulnerabilities

This project is a **local testing harness** for Workday Org Chart REST APIs. It does not host production services.

If you discover a security issue in this repository (for example, accidental credential leakage in a commit), please report it privately to the repository maintainer rather than opening a public issue.

## Secrets and credentials

- **Never commit** `.env`, OAuth client secrets, refresh tokens, access tokens, or SUV passwords.
- Use `.env.example` as a template only; copy to `.env` locally (`.env` is gitignored).
- The web app holds credentials **in memory only** during an active session. `Disconnect` clears them.
- API responses redact `Authorization` and `Cookie` headers before returning data to the browser.
- Collected test evidence should be stored under `evidence/` (gitignored) with tokens redacted.

## Live mode risks

- Live mode issues real HTTP requests to configured hosts. Double-check host and tenant before connecting.
- OAuth tokens obtained via **Get token** are pasted into the Password field and sent only to your configured Workday host.
- A successful `POST /api/execute` (HTTP 200) is the **local proxy** completing; always inspect **Upstream status** for the real API result.

## Dependency updates

Keep Python dependencies current (`pip install -U -r requirements.txt`) and run `make test` after upgrades.
