# Milestone 4 — Task 7 Security Testing

**Status:** Focused source changes and SQLite/frontend checks completed. PostgreSQL concurrency and SMTP delivery remain unverified. This is not a security certification or a claim that every control has passed runtime testing.

## Scope and method

Reviewed the current authentication/JWT path, password-change/reset flow, admin user endpoints, last-active-admin serialization, user-deletion dependency cleanup, patient/case/image ownership filters, image content and analysis artifact routes, upload validation/storage path helpers, profile update flow, and analysis/worker error handling. Added focused API and UI source-contract tests using synthetic accounts, in-memory SQLite, temporary files, and mocked SMTP delivery. No live database, patient records, uploaded images, real credentials, SMTP provider, model inference, migrations, browser, or application services were used. The broader test suites and security scanners were not run.

## Controls inspected

- JWTs are signed with HS256, have an expiry, carry a persisted token version, and are checked against an active database user in `backend/app/core/security.py` and `backend/app/api/deps.py`.
- Passwords are hashed with `pwdlib` in `backend/app/core/security.py`; forced password changes and admin-only routes are enforced in `backend/app/api/deps.py` and `backend/app/api/v1/endpoints/users.py`.
- Patient, case, image, analysis-run and artifact queries enforce owner/admin access in their endpoint modules. Non-owner resources return 404. Image upload validates extension, decoded content and pixel bounds, generates storage names, and confines paths in `backend/app/services/storage.py`.
- User deletion computes dependent cases, images, preprocessing rows and runs from target-owned roots, commits database deletion before physical cleanup, and keeps a retry journal in `backend/app/services/user_deletion.py`.
- The last-active-admin routes lock active administrator rows in stable order before role/status mutation in `backend/app/api/v1/endpoints/users.py`.

## Findings and fixes

| Finding | Severity before fix | Change and current status |
|---|---|---|
| Login had no shared throttling, allowing repeated credential attempts across workers. | High | Added database-backed atomic PostgreSQL/SQLite upserts keyed by HMAC digests of normalized email and client address. Default: 10 attempts per 15-minute bucket. The limiter fails closed if the shared database cannot serve it. Migration 0006 must be applied before deployment; otherwise login returns a generic 503 because its table is absent. Focused API test passed. |
| A requested profile email change could become the account's login email without proof of control. | Medium | Email remains unchanged until a random, expiring, single-use token is confirmed. Only the SHA-256 token digest is stored; token is delivered through SMTP and never included in API responses or logs. Confirmation increments token version to invalidate existing sessions. API tests passed with a mocked mail sender. Real delivery is unavailable until operators configure SMTP. |
| Private image and analysis artifact responses did not explicitly forbid private caching. | Medium | Added `Cache-Control: private, no-store` to authenticated image and analysis artifact responses (including repaired combined artifacts). Focused API assertions passed. |
| Analysis failure logs could include exception detail; the isolated ML worker inherited stderr and could emit paths/runtime diagnostics. | Medium | API logs now include only run ID and exception class; worker stderr is discarded and the worker receives an allowlisted environment without app auth/database secrets. Focused tests passed. |
| SQLite tests cannot establish PostgreSQL locking behavior for concurrent last-admin changes. | Medium / verification gap | Added isolated PostgreSQL role/status race tests guarded to the dedicated loopback `coronai_security_test` database on port 55433. They were skipped because the dedicated URL was unset and no test DB listener was available. No PostgreSQL concurrency conclusion is claimed. |
| Email verification and SMTP delivery cannot be exercised without a mail provider. | Runtime limitation | Workflow is implemented, but external delivery remains unverified. With incomplete SMTP settings, email-change requests fail closed and the existing login email remains in use. |

Migration 0006 is additive. Its downgrade removes the login-attempt buckets and any outstanding email-verification records; it does not change user accounts or their current email addresses. A downgrade therefore resets active login throttle windows and invalidates pending verification links. Roll back only as a coordinated app/database deployment after accepting those consequences; this task did not execute it.

No additional concrete ownership, authorization, upload-path or artifact-access regression was found in the inspected source. This statement is limited to source review and focused tests; it does not establish absence of vulnerabilities.

## Files changed for Task 7

- Backend configuration and models: `backend/app/core/config.py`, `backend/app/models/security_state.py`, `backend/app/models/__init__.py`, `backend/app/schemas/user.py`.
- Backend routes/services: `backend/app/api/v1/endpoints/auth.py`, `backend/app/api/v1/endpoints/images.py`, `backend/app/api/v1/endpoints/analysis.py`, `backend/app/services/login_rate_limit.py`, `backend/app/services/email_delivery.py`, `backend/app/services/analysis_inference.py`.
- Migration and configuration guidance: `backend/migrations/versions/0006_security_controls.py`, `backend/.env.example`, `backend/README.md`, `compose.security-test.yaml`.
- Frontend email verification: `src/pages/SettingsPage.tsx`, `src/pages/VerifyEmailChangePage.tsx`, `src/App.tsx`, `src/preferences/workspace-preferences.mjs`.
- Focused tests: `backend/tests/test_api.py`, `backend/tests/test_analysis.py`, `backend/tests/test_postgres_security_concurrency.py`, `tests/security-email-verification.test.mjs`.
- Progress record: `PROJECT_HANDOVER_UPDATED.md`.

## Commands and actual results

All backend commands below ran from `backend/` using its existing `.venv` Python. No full backend suite was run.

1. `python -m pytest -q tests/test_api.py -k "profile_email_change or expired_email_change or login_rate_limit or user_management_migration or image_upload_listing_persistence"` — **6 passed, 25 deselected**, one Starlette/httpx deprecation warning.
2. `python -m pytest -q tests/test_analysis.py::test_analysis_persists_metadata_and_protects_artifacts tests/test_analysis.py::test_analysis_failure_is_logged_safely_persisted_and_can_be_retried tests/test_analysis.py::test_ml_worker_startup_suppresses_private_stderr_and_auth_environment` — **3 passed**, one Starlette/httpx deprecation warning.
3. `python -m pytest -q tests/test_postgres_security_concurrency.py` — **2 skipped** because `CORONAI_SECURITY_TEST_DATABASE_URL` was not configured. Safe availability checks found no listener on port 55433; Docker CLI was present, but `docker info` could not connect to Docker Desktop's named pipe. No database connection was attempted by the tests.
4. `node --test tests/security-email-verification.test.mjs` — **2 passed, 0 failed**.
5. `npm run build` — **passed** (`tsc -b` and Vite production bundle completed).

The first focused API run exposed invalid use of the reserved `.test` email domain in two SMTP test fixtures. The fixtures were corrected to `.com`, then the command above passed. No production validation rule was changed.

No migration was run. No live PostgreSQL integration, SMTP delivery, browser verification, full frontend suite, full backend suite, or clinical/security scanner was run. The production frontend build was run as a compile check for the verification-route integration; it is not evidence of live behavior.

## External configuration and safe next steps

1. Back up the intended deployment database and review/apply `0006_security_controls` via `alembic upgrade head` as a controlled deployment operation. Do not apply it to a different database accidentally; the migration has not been run in this task.
2. In ignored `backend/.env`, configure `EMAIL_VERIFICATION_FRONTEND_URL`, `SMTP_HOST`, `SMTP_PORT`, `SMTP_FROM_EMAIL`, TLS mode, and both SMTP username/password if the provider requires authentication. Use provider-issued credentials stored in a secret manager or ignored local environment file. No credentials are supplied in source. Port 587 uses STARTTLS; implicit TLS uses SSL with STARTTLS disabled.
3. For PostgreSQL concurrency tests only, provision the isolated Compose service in `compose.security-test.yaml`, inject a temporary test-only password, and set `CORONAI_SECURITY_TEST_DATABASE_URL` to the required local test database. The test rejects any other host, port, username or database, and creates/drops only its random schema. Do not point this variable at development/live PostgreSQL.
4. In a deployment behind a proxy, configure the trusted proxy layer so `request.client.host` reflects the intended client address. The application deliberately does not trust arbitrary forwarded-IP headers.

## Honest final status

Task 7's shared rate limiter, email verification workflow, no-store artifact headers, safer analysis diagnostics, focused tests and documentation are implemented. Focused SQLite and frontend source-contract tests passed. PostgreSQL concurrency and real SMTP delivery are pending external setup, and migration 0006 remains unapplied. This work does not constitute a passed end-to-end security test or clinical validation.
