# Security Decisions

This document records deliberate security trade-offs for LogistikoCRM. Each entry
states the decision, the rationale, the mitigations in place, and what would
change the decision.

---

## SD-001 — JWT stored in browser `localStorage` (XSS exposure)

**Status:** Accepted risk with mitigations · *revisit before scaling beyond a
handful of client-portal users handling sensitive tax data.*

### Context
The SPA stores the JWT access + refresh tokens in `localStorage`
(`frontend/src/stores/authStore.ts`, `frontend/src/api/client.ts`). Any
JavaScript running on the origin can read `localStorage`, so a successful XSS
attack could exfiltrate tokens and impersonate the user until the token expires.

The alternative — **`httpOnly` Secure cookies** — keeps tokens out of reach of
JavaScript, neutralising token theft via XSS. It is the stronger option but
requires server + client changes (cookie issuance on login/refresh, CSRF
protection for cookie-authenticated requests, and CORS `credentials` handling).

### Decision
Ship the first client release with `localStorage` tokens **plus the mitigations
below**, and treat the migration to `httpOnly` cookies as the recommended next
hardening step (tracked, not a launch blocker for a small, trusted client base).

### Mitigations currently in place
- **Refresh-token rotation + blacklist** (`SIMPLE_JWT.ROTATE_REFRESH_TOKENS=True`,
  `BLACKLIST_AFTER_ROTATION=True`) — a stolen refresh token is invalidated on next
  use; reuse is detectable.
- **Logout clears both storages** and the refresh token is blacklisted server-side.
- **HTTPS enforced in production** (`SECURE_SSL_REDIRECT`, HSTS) — prevents
  token capture in transit.
- **`X_FRAME_OPTIONS=SAMEORIGIN`**, `SECURE_CONTENT_TYPE_NOSNIFF`,
  `SECURE_BROWSER_XSS_FILTER` reduce some injection/clickjacking vectors.
- **React's default output encoding** — no `dangerouslySetInnerHTML` in the
  portal pages; the main structural XSS sink is avoided.
- **Tenant isolation is server-side** (fail-closed querysets + `IsStaffUser`),
  so a stolen *client* token still only exposes that one client's own data, never
  cross-tenant.

### Required hardening to keep the risk acceptable at launch
1. **Shorten the access-token lifetime.** Currently `ACCESS_TOKEN_LIFETIME=5h`
   (`webcrm/settings.py`). For financial data, **15–30 minutes** is appropriate
   — it bounds the window a stolen access token is useful. Refresh rotation makes
   short access tokens transparent to the user. **Do this before go-live.**
2. **Add a Content-Security-Policy.** There is currently no CSP. A strict CSP
   (e.g. `default-src 'self'`, no inline scripts) is the single most effective
   defence-in-depth against XSS-driven token theft. Add `django-csp` or set the
   header at the reverse proxy. **Strongly recommended before go-live.**

### What would flip this to "must use httpOnly cookies"
- Onboarding many client users, or any user with elevated/staff privileges using
  the SPA, or a third-party script dependency in the portal bundle.

### Migration sketch (future)
- Backend: issue access/refresh as `httpOnly; Secure; SameSite=Strict` cookies on
  `/api/auth/login/` and `/api/auth/refresh/`; read the access cookie in an
  authentication class; add CSRF protection for unsafe methods.
- Frontend: drop `localStorage` token handling; rely on the browser sending
  cookies (`withCredentials: true`); CORS `CORS_ALLOW_CREDENTIALS=True` with an
  explicit origin allowlist (no wildcard).

---

## SD-002 — Django admin behind a secret URL prefix

**Status:** Accepted (security-through-obscurity as *one* layer, not the only one).

Admin is mounted at `SECRET_ADMIN_PREFIX` (not `/admin/`) and the CRM at
`SECRET_CRM_PREFIX`. This reduces automated scanning noise but is **not** a
substitute for strong staff passwords + (recommended) 2FA. Treat the prefix as
obscurity only; the real control is authentication. Consider admin 2FA before
go-live if staff accounts are high-value.

---

## SD-003 — Throttling keyed by client IP

Login (`5/min`), set-password (`3/hour`), and VAT-read (`120/hour`) throttles are
keyed by client IP. Behind a reverse proxy, ensure `X-Forwarded-For` is handled
correctly (DRF `get_ident` uses `REMOTE_ADDR` unless `NUM_PROXIES` is configured)
so the throttle keys on the real client IP, not the proxy. **Verify proxy/IP
config at deploy time** (see GOLIVE.md).

---

## SD-004 — Client self-sync ΦΠΑ (scoped write-action breaks read-only portal)

### Context
The client portal is read-mostly: `ClientScopedQuerysetMixin` is fail-closed and
write methods return 403. One deliberate exception already exists — document
upload (`me_upload_document`), forced to the caller's own client. We add a second:
clients may trigger their **own** myDATA VAT sync from the portal
(`POST /api/client/me/vat/sync/`, `me_sync_vat`).

### Decision
Allow it, tightly scoped and guarded — clients sync their own data without the
accountant, but cannot abuse the myDATA integration or touch finalized data.

### Mitigations in place
- **Scope:** the target client is forced from the authenticated user via
  `_require_client`; any `client_id` in the body is ignored (no spoofing / no
  cross-tenant sync).
- **Throttle:** `VatSyncThrottle` `3/hour` per user (myDATA cost / abuse guard) —
  `SimpleRateThrottle` with fixed scope (not `ScopedRateThrottle`, which no-ops on
  function views).
- **Period restriction:** only the current or previous month; arbitrary/old ranges
  → 400.
- **Locked-period protection:** reuses the `mydata_sync_vat` locked-period guard;
  a submitted/locked period is never destroyed — the endpoint returns
  `skipped/locked` instead of a fake success (shared helper
  `mydata/services.py::summarize_vat_sync`).
- **No credential exposure:** uses the credentials the accountant already stored;
  they are never returned to the client.

### Note
Future portal write-actions (e-invoicing, ΕΦΚΑ debts) must follow the same pattern:
forced-own-scope + dedicated throttle + respect any finalized/locked state.
