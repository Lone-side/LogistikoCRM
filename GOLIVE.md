# GO-LIVE CHECKLIST — LogistikoCRM Client Portal

Pre-flight checklist for onboarding the **first real client** to the portal.
Work top to bottom. Anything marked **BLOCKER** must be done before a client logs in.

Legend: ✅ done in code · ⬜ operational task for you · 🔒 security decision

---

## 1. Code & application readiness ✅ (already done)

These are implemented, tested, and gated in CI — no action needed, listed for confidence.

- ✅ **Tenant isolation** — fail-closed querysets + `IsStaffUser`; client sees only own data. Two CRITICAL cross-tenant breaches (mydata API, document-upload IDOR) closed. (`tests/mydata/test_staff_only_access.py`, `tests/accounting/test_document_upload_idor.py`, `test_portal_isolation.py`)
- ✅ **Auth** — JWT login + refresh (rotation + blacklist), role-based routing.
- ✅ **Brute-force protection** — login `5/min`, set-password `3/hour`, VAT-read `120/hour`, all per-IP and **actually enforcing** (verified — the throttles were previously no-ops).
- ✅ **Constant-time** set-password token check (no user-enumeration oracle).
- ✅ **Upload safety** — extension/size validation + filename sanitization; client uploads forced to own account.
- ✅ **Production start-up guards** — app refuses to boot with default `SECRET_KEY` / placeholder `FRITZ_API_TOKEN` when `DEBUG=False` (asserted in CI).
- ✅ **Portal invite email** — set-password link emailed on account creation (`EmailService.send_portal_invite`).
- ✅ **Tests** — backend 88+ (incl. security suites), frontend 36 unit + 1 E2E (login→portal→VAT→upload), all green in CI.

### Recommended code hardening before go-live (small, from the security audit)
- ✅ **Access-token lifetime** is `timedelta(minutes=15)` (`webcrm/settings.py` `SIMPLE_JWT['ACCESS_TOKEN_LIFETIME']`); refresh rotation + blacklist enabled. SD-001.
- ✅ **Content-Security-Policy** active via `common/utils/csp_middleware.py` (`script-src 'self'`). SD-001.
- ⬜ **Enable admin 2FA (TOTP).** Implemented & gated (`ENABLE_ADMIN_2FA`, OFF by default — no lockout). To turn on: each staff enrolls a TOTP device in the admin, *(optional)* `manage.py addstatictoken <user>` for backup codes, then set `ENABLE_ADMIN_2FA=True`. See `docs/SECURITY_DECISIONS.md` SD-002.

---

## 2. Operational tasks ⬜

### 2.1 Environment file (`.env`) — **BLOCKER**
Copy and fill every value. **Never commit `.env`.**
```bash
cp .env.example .env
# Generate a strong SECRET_KEY:
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```
Set at minimum:
- `DEBUG=False`
- `SECRET_KEY=<the generated value>`  (NOT the default — the app won't boot otherwise)
- `ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com`
- `PORTAL_URL=https://portal.yourdomain.com`  (used in invite/set-password links)
- `DB_*` (strong `DB_PASSWORD`)
- `FRITZ_API_TOKEN=<random>`  (`python -c "import secrets; print(secrets.token_urlsafe(32))"`)
- Email block (see 2.3)

Verify the guards pass with your real values:
```bash
DEBUG=False python manage.py check --deploy
```
Expect **no errors** (warnings about HSTS preload etc. are acceptable if behind a configured proxy).

### 2.2 HTTPS / TLS — **BLOCKER**
Tokens and credentials must never travel in clear text.
- ⬜ Obtain a certificate (Let's Encrypt / `certbot`) for `yourdomain.com` and `portal.yourdomain.com`.
- ⬜ Terminate TLS at Nginx/Caddy in front of gunicorn; redirect HTTP→HTTPS.
- ⬜ With `DEBUG=False` the app already sets `SECURE_SSL_REDIRECT`, HSTS, and `Secure` cookies — confirm the proxy forwards `X-Forwarded-Proto: https` so Django sees requests as secure (set `SECURE_PROXY_SSL_HEADER` if needed).
- 🔒 **Proxy IP note (SD-003):** ensure the proxy passes the real client IP (`X-Forwarded-For`) or the per-IP throttles key on the proxy. Configure DRF `NUM_PROXIES` / trusted proxy accordingly.

### 2.3 SMTP (email delivery) — **BLOCKER**
Portal invites and set-password links are emailed; without working SMTP a client cannot get in.
- ⬜ Set in `.env`: `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_USE_TLS=true`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL`, and `EMAIL_BACKEND_CONSOLE=false`.
  (Gmail: use an **App Password**, not the account password.)
- ⬜ **Live send test** before onboarding:
  ```bash
  python manage.py shell -c "from django.core.mail import send_mail; \
    send_mail('LogistikoCRM test', 'ok', None, ['you@yourdomain.com'])"
  ```
  Confirm the message arrives.
- ⬜ End-to-end invite test: create a portal account for a *test* client with a real inbox via the admin action **"Δημιουργία λογαριασμού Portal + αποστολή πρόσκλησης"**, click the link, set a password, log in.

### 2.4 Database & migrations — **BLOCKER**
- ⬜ Provision PostgreSQL (the compose file uses `postgres:15`); create the DB/user matching `.env`.
- ⬜ Apply migrations:
  ```bash
  python manage.py migrate --noinput
  python manage.py collectstatic --noinput
  ```
- ⬜ Create the first staff/superuser:
  ```bash
  python manage.py createsuperuser
  ```
- ⬜ Do **NOT** run `seed_demo` in production (it creates a demo client `099000117`). If it ever ran, remove it: `python manage.py shell -c "from accounting.models import ClientProfile; ClientProfile.objects.filter(afm='099000117').delete()"`.

### 2.5 Backups — **BLOCKER** (a portal that loses tax data is worse than no portal)
- ⬜ Configure `BACKUP_DIR` and `BACKUP_RETENTION_DAYS` in `.env`.
- ⬜ A backup command exists: `python manage.py backup_database`. Schedule it (cron) — see `scripts/backup_cron.sh`:
  ```bash
  # crontab -e  — daily at 02:00
  0 2 * * * cd /srv/logistikocrm && /srv/logistikocrm/venv/bin/python manage.py backup_database
  ```
  Or use Postgres directly: `pg_dump -Fc logistikocrm_db > backup.dump`.
- ⬜ **Restore drill (do this once, now):** take a backup, restore it into a scratch DB, confirm data integrity. An untested backup is not a backup.
- ⬜ Also back up the **media/ archive** (uploaded client documents) — these are files on disk, not in the DB.

### 2.6 Deployment
- ⬜ Deploy via Docker compose (`docker compose up -d`) or gunicorn+nginx. The compose `web` defaults are dev-safe; **production must set `.env`** (DEBUG=False etc. — the compose file warns about this).
- ⬜ Run Celery worker + beat (the compose file includes them) for async email/obligation tasks.
- ⬜ Confirm health endpoint: `curl https://yourdomain.com/api/health/` → `200`.
- ⬜ Smoke-test in production: log in as the test client, open ΦΠΑ tab, upload a document.

### 2.7 Monitoring (recommended, not a blocker)
- ⬜ Error tracking (Sentry) for the backend.
- ⬜ Log aggregation / alert on repeated `429` (throttle hits = possible attack) and `5xx`.
- ⬜ Uptime check on `/api/health/`.

---

## 3. Security decisions 🔒

Full detail in **`docs/SECURITY_DECISIONS.md`**. Summary:

- **SD-001 — JWT in `localStorage`:** accepted risk for a small, trusted client
  base, **conditional on** the two recommended hardenings (short access TTL + CSP)
  above. Migrate to `httpOnly` cookies before scaling to many client users or
  giving staff SPA access. *Decision owner: project owner — acknowledge before launch.*
- **SD-002 — Admin secret URL prefix:** obscurity layer only; rely on strong staff
  passwords. Consider admin 2FA before go-live.
- **SD-003 — IP-based throttling:** verify reverse-proxy `X-Forwarded-For` handling
  so throttles key on the real client IP.

---

## 4. First-client onboarding (once 1–3 are green)

1. Create the client record in admin (with a valid **email**).
2. Admin action → **"Δημιουργία λογαριασμού Portal + αποστολή πρόσκλησης"**.
3. Client receives the email, opens the `PORTAL_URL/set-password?...` link, sets a password.
4. Client logs in at `PORTAL_URL/login` → lands on the portal (ΦΠΑ / Υποχρεώσεις / Έγγραφα).
5. If the link expires, use admin action **"Επαναποστολή πρόσκλησης Portal"**.

---

### Quick "are we ready?" gate
- [ ] `.env` filled, `python manage.py check --deploy` clean
- [ ] HTTPS live on app + portal domains
- [ ] Test invite email received and set-password worked end-to-end
- [ ] Migrations applied, superuser created, no demo data in prod
- [ ] Backup taken **and restore verified**
- [ ] Access-token TTL shortened + CSP added (SD-001)
- [ ] SD-001 risk acknowledged by the project owner
