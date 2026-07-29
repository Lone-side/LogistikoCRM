# 🔧 Environment Configuration Guide

## 📁 Available Environment Files

| File | Purpose | Committed to Git? |
|------|---------|-------------------|
| `.env.example` | **Production template** - Full configuration with all features | ✅ Yes |
| `.env.development` | **Development template** - Detailed docs for local setup | ✅ Yes |
| `.env` | **Your active config** - Used by Django | ❌ No (gitignored) |

---

## 🚀 Quick Start (Development)

> **📖 Για πλήρη εγκατάσταση από το μηδέν βλ. [SETUP_GUIDE.md](SETUP_GUIDE.md)**
> (migrate → createcachetable → setupdata → runserver, με τη σωστή σειρά).

On a fresh clone there is **no `.env` yet** — create it from the development
template:

```bash
# Copy development template (the correct one for local use)
cp .env.development .env

# Edit as needed
nano .env  # or code .env

# Start Django (after the SETUP_GUIDE.md database steps)
python manage.py runserver 0.0.0.0:8000
```

With the development template the system uses:
- ✅ SQLite database (no setup required)
- ✅ Console email backend (prints to terminal)
- ✅ DEBUG=True (enables CORS for network access)
- ✅ All optional features disabled

---

## 🎯 Feature Flags

All **optional features** are **disabled by default**. Uncomment to enable:

### 🟢 Always Active (Required for basic operation)
- Django SECRET_KEY
- DEBUG mode
- Database (SQLite default)
- Email (Console default)

### 🟡 Optional Features (Disabled by Default)

#### 1. IoT Device Control (Tasmota)
Controls electric door lock via smart switch.

```env
TASMOTA_IP=192.168.178.27
TASMOTA_PORT=80
TASMOTA_DEVICE_NAME=Πόρτα Γραφείου
```

**How to test if working:**
- Go to: `http://localhost:8000/accounting/door-control/`
- If disabled: Button won't work (no error, feature just inactive)

---

#### 2. VoIP Call Logging (Fritz!Box)
Monitors office phone calls, creates tickets for unanswered calls.

```env
FRITZ_API_TOKEN=your-secure-random-token
```

**Generate secure token:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

**How to test if working:**
- Make a call to your Fritz!Box phone
- Check: `http://localhost:8000/admin/accounting/voipcall/`
- If disabled: No calls logged (feature inactive)

---

#### 3. Cloud PBX (Zadarma)
Click-to-call functionality, webhook notifications.

```env
ZADARMA_KEY=your-zadarma-api-key
ZADARMA_SECRET=your-zadarma-api-secret
```

**Get credentials:** https://zadarma.com/en/support/api/

**How to test if working:**
- Go to: `http://localhost:8000/accounting/voip/dashboard/`
- If disabled: Click-to-call buttons won't appear

---

#### 4. Tax Authority Integration (myDATA - ΑΑΔΕ)
Submit invoices to Greek Tax Authority.

```env
MYDATA_USER_ID=your-username
MYDATA_SUBSCRIPTION_KEY=your-key
MYDATA_IS_SANDBOX=True  # Use test environment
```

**How to test if working:**
- Go to: `http://localhost:8000/accounting/api/mydata/`
- If disabled: Endpoints return "Feature not configured"

---

#### 5. Network File Storage
Store client files on NAS or network drive.

```env
# Default: Uses project's media/ folder
# For network storage:
ARCHIVE_ROOT=/mnt/nas/logistiko/  # Linux
# or
ARCHIVE_ROOT=Z:\\Logistiko\\  # Windows mapped drive
```

**How to test if working:**
- Upload a client document
- Check if it appears in the configured path
- If not set: Files go to `PROJECT_ROOT/media/`

---

## 🌐 Local Network Access Setup

For **React frontend** or **multiple users** on local network:

### 1. Django Backend

**Your `.env` already has `DEBUG=True`** which enables:
- `CORS_ALLOW_ALL_ORIGINS=True` (allows API access from any IP)
- Network-wide access

Just start with:
```bash
python manage.py runserver 0.0.0.0:8000
```

### 2. React Frontend

Create `frontend/.env`:
```env
VITE_API_URL=http://192.168.178.22:8000/accounting
VITE_ENV=development
```

**Replace `192.168.178.22` with your actual IP!**

Find your IP:
```bash
# Linux/Mac
ip addr | grep 'inet ' | grep -v '127.0.0.1'

# Windows
ipconfig
```

Then:
```bash
cd frontend
npm start  # Restart if already running
```

### 3. Access from Other Devices

Others can open:
- Django Admin: `http://192.168.178.22:8000/admin/`
- React App: `http://192.168.178.22:3000/`

---

## 🔒 Production Checklist

When deploying to production server:

### Required Changes

```env
# 1. Generate new secret key
SECRET_KEY=<output-from-get_random_secret_key>

# 2. Disable debug
DEBUG=False

# 3. Set allowed hosts
ALLOWED_HOSTS=yourdomain.com,www.yourdomain.com

# 4. Configure PostgreSQL
DB_ENGINE=django.db.backends.postgresql
DB_NAME=logistikocrm_prod
DB_USER=postgres_user
DB_PASSWORD=strong-password-here
DB_HOST=localhost
DB_PORT=5432

# 5. Configure real email
EMAIL_BACKEND_CONSOLE=false
EMAIL_HOST=smtp.gmail.com
EMAIL_HOST_USER=office@yourdomain.com
EMAIL_HOST_PASSWORD=app-specific-password
EMAIL_PORT=587

# 6. Enable security
SECURE_SSL_REDIRECT=True
SESSION_COOKIE_SECURE=True
CSRF_COOKIE_SECURE=True
SECURE_HSTS_SECONDS=31536000
```

### Optional Production Features

Based on your needs, configure:
- VoIP systems (Fritz!Box, Zadarma)
- myDATA for tax submissions
- IoT devices (Tasmota door control)
- Network archive storage
- Backup settings

---

## 🧪 Testing Configuration

### Verify Django Settings

```bash
python manage.py shell
```

```python
from django.conf import settings

# Check debug mode
print(f"DEBUG: {settings.DEBUG}")

# Check database
print(f"Database: {settings.DATABASES['default']['ENGINE']}")

# Check email backend
print(f"Email: {settings.EMAIL_BACKEND}")

# Check optional features
print(f"Tasmota IP: {getattr(settings, 'TASMOTA_IP', 'NOT SET')}")
print(f"Fritz Token: {'SET' if getattr(settings, 'FRITZ_API_TOKEN', None) else 'NOT SET'}")
```

### Health Check Endpoint

```bash
curl http://localhost:8000/accounting/api/health/
```

Should return:
```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "database": "connected",
    "debug": true,
    "version": "1.0.0"
  }
}
```

---

## 📋 Environment Variable Reference

### Core Settings

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `SECRET_KEY` | ✅ Yes | None | Django secret key for cryptography |
| `DEBUG` | ✅ Yes | False | Debug mode (True for dev, False for prod) |
| `DB_ENGINE` | ✅ Yes | sqlite3 | Database backend |
| `EMAIL_BACKEND_CONSOLE` | ✅ Yes | false | Use console email for development |

### Optional Features

| Variable | Feature | Description |
|----------|---------|-------------|
| `TASMOTA_IP` | IoT Door Control | Tasmota device IP address |
| `FRITZ_API_TOKEN` | Fritz!Box VoIP | Webhook authentication token |
| `ZADARMA_KEY` | Zadarma VoIP | Cloud PBX API key |
| `MYDATA_SUBSCRIPTION_KEY` | Tax Integration | AADE myDATA API key |
| `ARCHIVE_ROOT` | Network Storage | Custom path for client files |

---

## 🆘 Troubleshooting

### Problem: "Settings not loading"

**Check:**
```bash
# 1. File exists
ls -la .env

# 2. File is in project root (same dir as manage.py)
pwd
ls manage.py .env

# 3. python-dotenv is installed
pip show python-dotenv
```

### Problem: "Feature not working"

**Check:**
```bash
# Verify the variable is set
python manage.py shell -c "from django.conf import settings; print(settings.TASMOTA_IP)"

# If you see an error, the variable is not loaded
```

**Fix:** Restart Django server after editing `.env`!

### Problem: "CORS error from React"

**Check:**
```bash
# 1. DEBUG must be True
grep DEBUG .env

# 2. Django must be on 0.0.0.0
# Should see: Starting development server at http://0.0.0.0:8000/

# 3. React .env has correct IP
cat frontend/.env
```

---

## 📚 Related Documentation

- **Network Setup:** See `ΤΟΠΙΚΟ_ΔΙΚΤΥΟ.md`
- **React Troubleshooting:** See `REACT_TROUBLESHOOTING.md`
- **Production Deployment:** See `DEPLOYMENT.md`
- **Production Checklist:** See `PRODUCTION_CHECKLIST.md`

---

**Last Updated:** December 2025
