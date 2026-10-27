# Deploying ServoraBd on Render

Render runs the server for you: no Linux administration, no Nginx, no
certificates. This is the easier of the two routes. For a plain Ubuntu server
instead, see [`DEPLOY.md`](DEPLOY.md).

> **Status:** `render.yaml` and the settings it depends on were written and
> checked locally against a real PostgreSQL database, including a boot under
> production settings, but **nothing here has been run on Render**. Expect to
> fix a detail or two on the first attempt. Step 7 is not optional — it is the
> one check that needs the live site.
>
> A first deploy now boots with **only** the values Render supplies
> automatically: SMTP and R2 are optional, and the service starts without them
> (mail is discarded, uploads go to the container's disk until you add R2).
> Fill them in as described in step 3 before inviting real users.

## What you get

```
Browser ──> servorabd-web (static site, free)
              ├─ /                  index.html, landing page with its hero prerendered
              ├─ everything else    app.html, the React app
              └─ /api, /admin       forwarded to the API service, so the browser sees one origin
            servorabd-api (web service)   Django under gunicorn
              └─ /healthz/          Render's health check: checks the database too
            servorabd-db  (PostgreSQL 18)
            two cron services              the seven scheduled jobs
            Cloudflare R2                  uploaded files
```

## Why files go to R2, not Render

Render gives each service a fresh, empty filesystem on every deploy and every
restart. Anything uploaded would vanish. A paid persistent disk does not solve
it either: a disk attaches to one service, and the cron service that purges
expired documents would not be able to reach it.

So uploads go to **Cloudflare R2**, which is free up to 10 GB and charges
nothing for downloads. Any S3-compatible service works — Backblaze B2, Wasabi,
AWS S3 — only the endpoint changes.

The bucket holds two separate areas, and they are not equally private:

| Prefix | Holds | Access |
|---|---|---|
| `media/` | work photos | plain URLs, anyone with the link |
| `private/` | NID scans and trade certificates | signed links that expire in 5 minutes |

**The bucket must never be made public.** Public access would expose the
`private/` prefix, which is exactly the leak the M9 security fix closed.
Verification documents reach admins through `/api/v1/admin/verifications/<id>/file/`,
which requires an admin account.

## Cost

Check Render's current prices; these were right when this was written.

| Piece | Free tier | Small paid |
|---|---|---|
| API service | sleeps after 15 min idle; first visit then takes ~1 min | ~$7/month, always on |
| PostgreSQL | deleted after 30 days | ~$6/month |
| Static site | free | free |
| Cron jobs | not available on free | a few cents each per month |
| Cloudflare R2 | free to 10 GB | free to 10 GB |

The free tier is fine for showing the project. It is not suitable for real
users: a sleeping service also means the scheduled jobs never run.

## 1. Storage bucket

In the Cloudflare dashboard, under R2:

1. Create a bucket named `servorabd`. **Leave public access disabled.**
2. Create an API token with **Object Read & Write**, limited to that bucket.
3. Note the Access Key ID, the Secret Access Key, and the S3 endpoint, which
   looks like `https://<account-id>.r2.cloudflarestorage.com`.

The secret is shown once. Store it in a password manager, not in the repository.

## 2. Create the services

Push the repository to GitHub first — Render deploys from it.

1. In Render, choose **New > Blueprint** and select the repository.
2. Render reads [`../render.yaml`](../render.yaml) and proposes a database,
   an API service, two cron services and a static site.
3. Apply it. The first build takes a few minutes.

Everything is defined in that file, so you do not create services by hand.

## 3. Fill in the settings

`render.yaml` deliberately leaves secrets blank (`sync: false`). Open
**servorabd-api > Environment** and set:

| Key | Value |
|---|---|
| `ALLOWED_HOSTS` | `servorabd-api.onrender.com` |
| `CSRF_TRUSTED_ORIGINS` | `https://servorabd-web.onrender.com` |
| `CORS_ALLOWED_ORIGINS` | leave empty |
| `S3_ENDPOINT_URL` | your R2 endpoint from step 1 |
| `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY` | from step 1 |
| `S3_BUCKET_NAME` | `servorabd` |
| `S3_PUBLIC_DOMAIN` | leave empty unless you attach a custom domain to the bucket |
| `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `DEFAULT_FROM_EMAIL` | your SMTP details |

Only `ALLOWED_HOSTS` and `CSRF_TRUSTED_ORIGINS` really need you on the first
deploy, and even they have a fallback: the service reads Render's own
`RENDER_EXTERNAL_HOSTNAME` and trusts that host automatically. Set them
explicitly once you attach a custom domain.

Leave `EMAIL_HOST` empty and mail is dropped rather than crashing the service —
useful for a first look, but **OTP login codes are sent by email**, so
registration will not work until SMTP is set. Likewise, leave `S3_BUCKET_NAME`
empty and uploads fall back to the container's own disk, which Render wipes on
every deploy and restart; set R2 up before anyone uploads anything they expect
to keep.

`CORS_ALLOWED_ORIGINS` stays empty on purpose. The static site forwards `/api`
to the backend, so the browser only ever talks to one origin and no
cross-origin permission is needed. Adding origins here would widen access for
no benefit.

Copy the same values into **both cron services**, which need the database and
the bucket to do their work.

If Render gives your services different names, update the three `destination`
lines in `render.yaml` to match, and redeploy.

## 4. First-time data

Open **servorabd-api > Shell**:

```bash
python manage.py seed_catalogue
python manage.py createsuperuser
```

Migrations already ran: they are part of the build command, so every deploy
applies them.

Do not run `seed_demo` — it refuses to run when `DEBUG` is off, because it
creates accounts with a password published in this repository.

## 5. Check the site

First, `https://servorabd-api.onrender.com/healthz/` should return
`{"status": "ok", "database": "ok"}`. If it reports the database is
unavailable, the service is up but `DATABASE_URL` is wrong — check it before
reading any other symptom.

Then visit `https://servorabd-web.onrender.com`:

- The landing page appears, and the headline shows before the page is interactive.
- `/providers` loads (served by `app.html`, not a 404).
- `/admin/` shows the Django login, styled — which proves static files work.
- Register a provider, upload a verification document, then look in the R2
  bucket: the file is under `private/`, not `media/`.
- As an admin, open the document from Django admin. It opens. Now sign out and
  open the same link: it is refused.

## 6. Backups

Render's paid database plans take daily backups and can restore to a point in
time. The free plan has none.

Render's backups do **not** include the R2 bucket. Cloudflare keeps the objects,
but nothing protects against a mistaken delete, so for real use enable object
versioning on the bucket.

To take your own database copy from a machine with `pg_dump` installed, using
the external connection string from the Render dashboard:

```bash
pg_dump --format=custom --no-owner --dbname="<external connection string>" --file=servorabd.dump
```

[`scripts/restore-check.sh`](scripts/restore-check.sh) verifies such a dump can
actually be restored. A backup nobody has restored is not yet a backup.

## 7. Check the rate limiting — do not skip this

Login, OTP and search limits identify a caller by IP address. Behind a proxy,
Django reads that from the `X-Forwarded-For` header, trusting as many entries
as `TRUSTED_PROXY_COUNT` says.

**If that number is too high, the limits stop working.** An attacker prepends a
made-up address to the header and gets a fresh allowance on every request,
which is the throttle bypass fixed during the security review. `render.yaml`
sets `1`, which is the documented behaviour for a single Render proxy, but I
could not verify it on a live deployment.

To check, set `EXPOSE_CLIENT_IDENT=True` in the API environment, wait for the
redeploy, then run locally:

```bash
python manage.py check_proxy_count https://servorabd-api.onrender.com/api/v1/categories/
```

It sends one request with a forged header and one without, and compares what
the rate limiter sees. If the forged address gets through, it tells you to
lower `TRUSTED_PROXY_COUNT` and try again.

**Set `EXPOSE_CLIENT_IDENT` back to `False` when you are done.** It is off by
default and should stay off; it exists only for this check.

## The admin panel

Open `https://servorabd-api.onrender.com/admin/`. The same path on the web
domain also works through the rewrite, but if it loads unstyled or its menus do
not open there, the static site's Content-Security-Policy is reaching the
admin. Use the API address, which sends no such header.

**Every staff account signs in with a password and an authenticator app.** The
first time someone signs in, the admin shows a QR code. They scan it with
Google Authenticator, Microsoft Authenticator or any TOTP app and type the
6-digit code. Every later sign-in asks for a fresh code.

Enrol your own superuser straight after the first deploy that includes this.
Until a staff account has enrolled, anyone who knows its password can enrol
their own phone in its place.

**Lost phone.** A superuser opens **Users**, picks the staff member and presses
**Reset two-factor**. They set up a new app at their next sign-in. Keep a
second superuser with its own app, so that one lost phone never locks the
platform out. If the last superuser is locked out, run this in
**servorabd-api > Shell** (paid plans only):

```bash
python manage.py shell -c "from django_otp.plugins.otp_totp.models import TOTPDevice; TOTPDevice.objects.filter(user__phone='+8801XXXXXXXXX').delete()"
```

**Staff roles.** Every deploy creates or refreshes four groups:

| Group | Can do |
|---|---|
| Support | View users, bookings and payments; suspend and reinstate users; resolve disputes |
| Moderator | Approve or reject verification documents; hide reviews; recompute trust |
| Finance | Resolve flagged payments; record settlements; view the ledger |
| Catalogue editor | Add and edit categories, services and locations |

To add a staff member, create the user, tick **Staff status** and add them to
one group. The groups are defined in `backend/apps/common/roles.py`. Changes
made to these four in the admin are overwritten on the next deploy, so create
a new group for anything bespoke. Only superusers can change groups or grant
permissions.

**Actions, not edits.** Payments, the ledger, bookings and their history are
read-only. Change them with the buttons at the top of a record: Suspend,
Reinstate, Reset two-factor, Approve, Reject, Hide, Show again, Resolve dispute,
Resolve flagged payment, Record settlement, Recompute trust. Each asks for
confirmation or a reason, and is recorded under **Admin activity**.

The JSON endpoints under `/api/v1/admin/` accept only a signed-in admin session
that has passed two-factor. A staff member's app token is refused, so a stolen
password alone cannot reach them.

## Updating

Push to `main`. Render rebuilds and runs the migrations. If a build fails, the
previous version keeps serving.

Take a database copy before any deploy that changes migrations, and read
Render's build log rather than guessing.

## What has and has not been verified

Checked locally:

- Production settings pass `check --deploy --fail-level WARNING` with object
  storage switched on.
- Uploads through the S3 backend write to the right prefix, read back
  correctly, never overwrite an existing file, and delete cleanly.
- A document URL comes back signed and expiring in 5 minutes; a work photo URL
  carries no credentials. Both are covered by tests
  (`apps/common/tests/test_storage_config.py`), so a change that unsigns
  document links fails CI.
- `render.yaml` parses, and the shared environment block reaches all three
  Python services.
- Production settings load with only the variables Render sets by itself —
  no SMTP, no bucket, no `.env` file — which is the state of a first deploy.
- Booted under `config.settings.prod` against a real PostgreSQL database:
  `/healthz/` returned `{"status": "ok"}` and `/api/v1/categories/` returned
  its 8 seeded rows.
- `/healthz/` answers over plain HTTP while every other path still redirects to
  HTTPS, so Render's internal health probe is not bounced by a 301.
- `collectstatic` writes through WhiteNoise to local disk even with object
  storage switched on, so the build step needs no bucket credentials.
- `gunicorn.conf.py` resolves from `rootDir: backend` and binds to `$PORT`.
- The frontend production build succeeds and emits both `index.html` and
  `app.html`; the bundle has no inline script or style, so the strict
  Content-Security-Policy in `render.yaml` does not need loosening.
- The full backend test suite passes with these settings changes.
- The nightly cron runs at 21:00 UTC, which is 03:00 in Dhaka, as the PRD
  requires.

Not verified, because it needs a live deployment:

- That Render's build and start commands work as written *on Render* — they
  were exercised locally, not in Render's build image.
- That the static site's rewrite rules behave as expected, particularly
  `/` versus every other path.
- **How many proxies sit in front of the app** — hence step 7.
- R2 credentials against the real service.
