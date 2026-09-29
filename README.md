# NotifyHub — Notification System (StarClinch Backend Assignment)

The admin manages every notification from **one screen**. Each **trigger** (an event on the website) can send on **WhatsApp**, **Email** and **Web Push**, and each channel has its own template, on/off toggle and test-send button. Admins never have to open Meta, Brevo or OneSignal to create templates.

| Part | Tech | Hosted on |
|---|---|---|
| Backend | Python 3.12, Django 5, Django REST Framework, SimpleJWT, PostgreSQL | Render |
| Frontend | React 18 + Vite, react-router, react-onesignal | Vercel |
| WhatsApp | WhatsApp Cloud API (Meta **test number / sandbox**) | |
| Email | **Brevo** transactional API (free tier, 300 emails/day). I used Brevo instead of Postmark, as Section 4 of the brief allows | |
| Web Push | OneSignal (web push only, iOS/Android off) | |

**Live links**
- Frontend: `https://notification-system-theta.vercel.app`
- Backend: `https://notifyhub-api-g8jj.onrender.com/api/health/`


---

## Admin login

Open the frontend and log in with the admin credentials from the `ADMIN_USERNAME` / `ADMIN_PASSWORD` env vars. You are redirected to **Notification Settings**.

- Demo admin: `admin` / `<password shared in email>`
- A normal user can sign up from **Create account**. Users see the website only, not the admin panel.

## Triggers built

| Trigger key | Fires when | Where in code |
|---|---|---|
| `login` | User signs in | `LoginView` → `fire_trigger_async("login")` |
| `logout` | User signs out | `LogoutView` |
| `inactive_1d` | No visit for 24 h | hourly job `check_inactive_users()` |
| `inactive_1w` | No visit for 7 days | hourly job |
| `password_reset` | "Forgot password?" on the login page | `PasswordResetView` |
| `order_placed` | "Place demo order" button on the website | `OrderView` |

The admin can add more triggers with **+ Add trigger**. Each trigger row supports all 3 channels. **⚡ Fire for me** fires a row instantly for the logged-in admin, which is useful for demoing the inactivity triggers without waiting a day.

## How it works

```
Website action ──► Django view ──► fire_trigger(key, user)            (background thread, so the API stays fast)
                                       │
                                       ├─ load ENABLED templates of that trigger
                                       ├─ render variables {{name}}, {{order_id}} …
                                       ├─ provider adapter per channel
                                       │     whatsapp → Meta Cloud API  /messages
                                       │     email    → Brevo /v3/smtp/email
                                       │     webpush  → OneSignal /notifications (external_id = user.id)
                                       └─ NotificationLog (sent / failed + error)  → shown in admin
```

- **Channel isolation:** each channel is sent in its own try/except, so a failure (for example an expired WhatsApp token) never blocks email or push.
- **Variable mapping:** `{{name}}`-style placeholders are extracted into `Template.variables` in the order they appear. WhatsApp only accepts numbered params, so `variables[0] → {{1}}`, `variables[1] → {{2}}`, and so on. The backend converts them when it submits the template and when it sends a message.
- **WhatsApp templates from the admin panel:** saving a WhatsApp cell calls `POST /{WABA_ID}/message_templates`. **Sync** calls `GET /{WABA_ID}/message_templates?name=` and stores `PENDING / APPROVED / REJECTED`. Editing the body calls the Meta edit endpoint, and changing the template name creates a new template. A *free-form text* mode is also available; it only works inside the 24-hour window after the user messages the business number.
- **Web Push targeting:** after login the frontend calls `OneSignal.login(user.id)`. The backend targets `include_aliases.external_id = [user.id]` with `isAnyWeb: true, isIos: false, isAndroid: false`.
- **Inactivity:** `UserProfile.last_seen_at` is updated on login and on each visit (`/auth/me/`). A GitHub Actions cron (`.github/workflows/inactive-check.yml`) calls `POST /api/jobs/check-inactive/` every hour, protected by `X-Cron-Secret`. A user gets each inactivity message once per period, because we skip them if a log for that trigger already exists after their last visit.
- **Test send** works even when the toggle is off and is marked `test` in the logs. Real sends respect the toggle.

### Data model
- `Trigger(key, name, description, is_active)`: one row in the admin table
- `Template(trigger, channel, subject, title, body, variables, is_enabled, wa_* fields)`, with `unique(trigger, channel)`: one cell
- `UserProfile(user, phone, last_seen_at)`
- `NotificationLog(trigger, channel, user, recipient, status, is_test, response, error)`

### API
| Method | Endpoint | |
|---|---|---|
| POST | `/api/auth/register/`, `/api/auth/login/`, `/api/auth/logout/` | website auth (fires triggers) |
| GET/PATCH | `/api/auth/me/` | profile + phone |
| POST | `/api/orders/`, `/api/auth/password-reset/` | fire `order_placed` / `password_reset` |
| GET | `/api/admin/matrix/` | whole admin table in one call |
| CRUD | `/api/admin/triggers/`, `POST …/{id}/fire/` | triggers |
| CRUD | `/api/admin/templates/` | templates |
| POST | `/api/admin/templates/{id}/toggle/` · `/test/` · `/sync/` | cell actions |
| GET | `/api/admin/logs/` | last 50 deliveries |
| POST | `/api/jobs/check-inactive/` | hourly cron |

---

## Environment variables

**Backend (`backend/.env` locally, Render → Environment in production).** See `backend/.env.example`.

| Var | Purpose |
|---|---|
| `SECRET_KEY`, `DEBUG`, `ALLOWED_HOSTS`, `DATABASE_URL` | Django (`DATABASE_URL` is empty locally, so SQLite is used) |
| `CORS_ALLOWED_ORIGINS`, `FRONTEND_URL` | Vercel URL |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_EMAIL`, `ADMIN_PHONE` | admin user created on every deploy |
| `WHATSAPP_ACCESS_TOKEN`, `PHONE_NUMBER_ID`, `WHATSAPP_BUSINESS_ACCOUNT_ID` | Meta WhatsApp sandbox |
| `BREVO_API_KEY`, `BREVO_FROM_EMAIL` | Brevo email |
| `ONESIGNAL_APP_ID`, `ONESIGNAL_REST_API_KEY` | OneSignal web push |
| `CRON_SECRET` | protects the inactivity job endpoint |

**Frontend (`frontend/.env`, Vercel → Environment Variables):** `VITE_API_URL`, `VITE_ONESIGNAL_APP_ID`.

`.env` files are git-ignored. No real tokens are committed.

## Run locally

```bash
# backend
cd backend
python -m venv venv && venv\Scripts\activate        # mac/linux: source venv/bin/activate
pip install -r requirements.txt
copy .env.example .env                                # fill in the keys
python manage.py migrate
python manage.py seed_triggers
python manage.py ensure_admin
python manage.py runserver

# frontend (new terminal)
cd frontend
npm install
copy .env.example .env
npm run dev                                           # http://localhost:5173
```

Tests: `cd backend && python manage.py test notifications`. The tests mock the providers and cover rendering, WhatsApp positional mapping, channel isolation, toggle, test send, permissions, auth triggers and the inactivity job.

## Deploy
1. **Render:** New → Blueprint → select this repo (`render.yaml`), then fill in the env vars marked `sync: false`. Alternatively, create it by hand: New Web Service, root `backend`, build `bash build.sh`, start `gunicorn config.wsgi:application`, plus a free PostgreSQL database.
2. **Vercel:** Import repo → Root Directory `frontend` → env `VITE_API_URL=https://<api>.onrender.com`, `VITE_ONESIGNAL_APP_ID=…`.
3. Put the Vercel URL into Render `CORS_ALLOWED_ORIGINS` + `FRONTEND_URL`, and into OneSignal → Settings → Web → Site URL.
4. GitHub → Settings → Secrets → Actions: `BACKEND_URL`, `CRON_SECRET`.

## Sandbox notes / limitations
- WhatsApp uses Meta's **test number**. Only numbers added to the test recipient list receive messages, and the temporary token expires about every 24 h, so regenerate it in Meta → API Setup when sends fail. New templates need Meta approval; press **Sync** to refresh the status. An approved template can be edited only a limited number of times per day.
- The email sender is a verified Gmail address, so mails may land in Spam. In production I would authenticate our own domain (SPF/DKIM/DMARC) in Brevo.
- Render's free tier sleeps after inactivity, so the first request can take around 50 s.
- Sends run in a background thread, which keeps the free tier simple. At scale I would move them to a queue (Celery/RQ + Redis) with retries and exponential backoff.
