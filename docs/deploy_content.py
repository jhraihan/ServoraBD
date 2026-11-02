# -*- coding: utf-8 -*-
"""
Content source for the ServoraBd Render deployment record.

Same (kind, payload) format as guide_content.py, rendered by build_deploy.py.
"""

TITLE = "ServoraBd"
SUBTITLE = "Local Service Marketplace"
DOC_TYPE = "Render Deployment Record"
VERSION = "1.1"
STATUS = "Live on the free tier"
DATE = "2 November 2026"
AUTHOR = "Jahid H. R."

PITCH = (
    "How this project was put on the internet: the code changes it needed, "
    "the two routes that failed, the one that worked, the move to Neon when "
    "Render's free database expired, and what is still outstanding."
)

DOC = []


def add(*items):
    DOC.extend(items)


# ======================================================================
# 1. Result
# ======================================================================
add(
    ("h1", "1. What was deployed"),

    ("table", {
        "cols": ["Piece", "Address", "Plan"],
        "widths": [0.22, 0.52, 0.26],
        "rows": [
            ["Static site",
             "<font face='Courier'>servorabd-web.onrender.com</font>",
             "Free"],
            ["API",
             "<font face='Courier'>servorabd-api.onrender.com</font>",
             "Free, sleeps when idle"],
            ["Database", "Neon PostgreSQL, outside Render",
             "Free, no expiry"],
        ],
    }),

    ("p", "Verified live: <font face='Courier'>/healthz/</font> returns "
          "<font face='Courier'>{\"status\": \"ok\", \"database\": \"ok\"}</font>, "
          "and the site serves 8 categories, 45 services and 38 locations "
          "through the API. Deployed from commit "
          "<font face='Courier'>36d4190</font> on "
          "<font face='Courier'>main</font>. The database first lived on "
          "Render and moved to Neon when Render deleted it; section 4.6 "
          "covers the move."),

    ("h2", "1.1 The shape of it"),

    ("code", [
        "Browser",
        "   |",
        "   v",
        "servorabd-web  (static site)",
        "   |  /                  index.html, hero prerendered",
        "   |  /providers, /...   app.html, the React app",
        "   |  /api, /admin,      rewritten to the API below,",
        "   |  /static            so the browser sees one origin",
        "   v",
        "servorabd-api  (web service)   Django + gunicorn",
        "   |",
        "   v",
        "Neon           (PostgreSQL, over TLS)",
    ]),

    ("p", "The browser only ever talks to the static site. It forwards "
          "<font face='Courier'>/api</font>, "
          "<font face='Courier'>/admin</font> and "
          "<font face='Courier'>/static</font> to Django behind the scenes, "
          "which is why no CORS configuration was needed anywhere."),

    ("pagebreak", None),
)


# ======================================================================
# 2. Code changes
# ======================================================================
add(
    ("h1", "2. What had to change in the code"),

    ("p", "The repository already had a "
          "<font face='Courier'>render.yaml</font> and deployment notes, but "
          "it would not have survived a first deploy. Five things were fixed, "
          "all in commit <font face='Courier'>36d4190</font>."),

    ("h2", "2.1 The build would have crashed"),

    ("p", "<font face='Courier'>config/settings/prod.py</font> required "
          "<font face='Courier'>EMAIL_HOST</font>, "
          "<font face='Courier'>EMAIL_HOST_USER</font>, "
          "<font face='Courier'>EMAIL_HOST_PASSWORD</font>, "
          "<font face='Courier'>DEFAULT_FROM_EMAIL</font> and the "
          "<font face='Courier'>S3_*</font> keys. The blueprint marked every "
          "one of them <font face='Courier'>sync: false</font>, meaning unset "
          "until filled in by hand, so Django raised "
          "<font face='Courier'>ImproperlyConfigured</font> before serving "
          "anything. They now have defaults: with no SMTP the mail backend "
          "discards messages instead of refusing to start, and with no bucket "
          "the storage backend falls back to local disk."),

    ("h2", "2.2 The health check could never have passed"),

    ("p", "<font face='Courier'>healthCheckPath</font> pointed at "
          "<font face='Courier'>/api/v1/categories/</font>, but "
          "<font face='Courier'>SECURE_SSL_REDIRECT</font> is on, so "
          "Render&rsquo;s internal HTTP probe received a "
          "<font face='Courier'>301</font> and the service would have been "
          "marked unhealthy forever. A "
          "<font face='Courier'>/healthz/</font> endpoint was added &mdash; it "
          "also runs <font face='Courier'>SELECT 1</font> against the database "
          "&mdash; and exempted from the redirect via "
          "<font face='Courier'>SECURE_REDIRECT_EXEMPT</font>. Confirmed: "
          "<font face='Courier'>/healthz/</font> answers 200 over plain HTTP "
          "while every other path still returns 301."),

    ("h2", "2.3 Every request would have returned 400"),

    ("p", "<font face='Courier'>ALLOWED_HOSTS</font> was empty on a fresh "
          "deploy. It now falls back to Render&rsquo;s own "
          "<font face='Courier'>RENDER_EXTERNAL_HOSTNAME</font>, which also "
          "feeds <font face='Courier'>CSRF_TRUSTED_ORIGINS</font>. This is why "
          "no host configuration was needed during the deploy."),

    ("h2", "2.4 Two smaller fixes"),

    ("bullets", [
        "A <font face='Courier'>/media/*</font> rewrite was missing. The dev "
        "proxy had one; production did not, so uploaded photos would 404 "
        "whenever object storage is off &mdash; which is the case on free.",
        "<font face='Courier'>WEB_CONCURRENCY</font> was added. The gunicorn "
        "config defaults to 3 workers, which is tight on a 512&nbsp;MB "
        "instance.",
    ]),

    ("h2", "2.5 Checked and deliberately left alone"),

    ("p", "The strict Content-Security-Policy was briefly relaxed for "
          "Tailwind, then reverted: the built bundle contains no inline "
          "script, no inline style and no runtime stylesheet injection, so "
          "<font face='Courier'>style-src 'self'</font> holds. The full "
          "backend test suite passes with all of the above."),

    ("pagebreak", None),
)


# ======================================================================
# 3. The routes that failed
# ======================================================================
add(
    ("h1", "3. Two routes that did not work"),

    ("p", "Worth recording, because both cost time and neither is obvious."),

    ("h2", "3.1 Blueprint, first attempt: a schema error"),

    ("p", "Render rejected "
          "<font face='Courier'>render.yaml</font> with "
          "<font face='Courier'>field command not found in type "
          "file.Service</font> on the two cron services. Render&rsquo;s cron "
          "schema uses <font face='Courier'>startCommand</font>, not "
          "<font face='Courier'>command</font>. Both were fixed and pushed."),

    ("h2", "3.2 Blueprint, second attempt: a demand for a card"),

    ("p", "With the schema valid, Render asked for payment details. A "
          "blueprint is all-or-nothing: Render validates and prices "
          "<b>every</b> service in the file before creating any of them, and "
          "<font face='Courier'>render.yaml</font> asks for a paid database "
          "and three paid services."),

    ("p", "A second blueprint, "
          "<font face='Courier'>render-free.yaml</font>, was written for the "
          "free tier &mdash; free database, no cron services, object storage "
          "off. It is committed and valid. The card prompt persisted anyway, "
          "so the blueprint route was abandoned in favour of creating the "
          "services by hand, which sidesteps whole-file pricing entirely."),

    ("callout", {
        "title": "If you return to the blueprint route",
        "body": "<font face='Courier'>render-free.yaml</font> is ready to use. "
                "Point the <b>Blueprint Path</b> field at it &mdash; the field "
                "defaults to <font face='Courier'>render.yaml</font>, which is "
                "the paid one and will be billed. Neither file creates a "
                "database any more: paste the Neon connection string into "
                "<font face='Courier'>DATABASE_URL</font> when Render asks.",
    }),

    ("pagebreak", None),
)


# ======================================================================
# 4. The route that worked
# ======================================================================
add(
    ("h1", "4. The route that worked: services by hand"),

    ("h2", "4.1 Database &mdash; a Neon project"),

    ("p", "The first database was Render&rsquo;s free Postgres, created under "
          "<b>New &gt; Postgres</b>. Render deletes those 30 days after "
          "creation, so it is gone; section 4.6 describes the move. Today "
          "the database is a Neon project on the free plan:"),

    ("table", {
        "cols": ["Field", "Value"],
        "widths": [0.32, 0.68],
        "rows": [
            ["Plan", "Free &mdash; 0.5 GB, no expiry"],
            ["Region", "AWS Singapore, next to the API"],
            ["Connection string",
             "<b>Direct</b>, with connection pooling turned off, ending in "
             "<font face='Courier'>?sslmode=require</font>"],
        ],
    }),

    ("p", "The direct string, not the pooled one: Neon&rsquo;s pooler runs in "
          "transaction mode, which breaks the server-side cursors Django uses "
          "for large querysets. An idle Neon database pauses after a few "
          "minutes and wakes on the next query in well under a second."),

    ("h2", "4.2 API &mdash; New &gt; Web Service"),

    ("table", {
        "cols": ["Field", "Value"],
        "widths": [0.26, 0.74],
        "rows": [
            ["Name", "<font face='Courier'>servorabd-api</font>"],
            ["Language", "Python 3"],
            ["Region", "Singapore &mdash; must match the database"],
            ["Root Directory", "<font face='Courier'>backend</font>"],
            ["Instance Type", "Free"],
            ["Health Check Path", "<font face='Courier'>/healthz/</font>"],
        ],
    }),

    ("p", "Build command:"),

    ("code", [
        "pip install -r requirements.txt \\",
        "  && python manage.py collectstatic --no-input \\",
        "  && python manage.py migrate",
    ]),

    ("p", "Start command &mdash; the "
          "<font face='Courier'>../</font> resolves because Root Directory is "
          "<font face='Courier'>backend</font>:"),

    ("code", [
        "gunicorn --config ../deploy/gunicorn.conf.py",
    ]),

    ("p", "Eight environment variables, which is the whole set needed to "
          "boot:"),

    ("code", [
        "DJANGO_SETTINGS_MODULE = config.settings.prod",
        "PYTHON_VERSION         = 3.12.7",
        "WEB_CONCURRENCY        = 1",
        "DEBUG                  = False",
        "USE_OBJECT_STORAGE     = False",
        "TRUSTED_PROXY_COUNT    = 1",
        "DATABASE_URL           = <Neon connection string>",
        "SECRET_KEY             = <Generate>",
    ]),

    ("p", "The connection string carries the password. It lives in the "
          "Render environment and a password manager, never in the "
          "repository."),

    ("h2", "4.3 Front end &mdash; New &gt; Static Site"),

    ("table", {
        "cols": ["Field", "Value"],
        "widths": [0.32, 0.68],
        "rows": [
            ["Name", "<font face='Courier'>servorabd-web</font>"],
            ["Root Directory", "<font face='Courier'>frontend</font>"],
            ["Build Command",
             "<font face='Courier'>npm ci &amp;&amp; npm run build</font>"],
            ["Publish Directory",
             "<font face='Courier'>dist</font> &mdash; relative to Root "
             "Directory, so not "
             "<font face='Courier'>frontend/dist</font>"],
            ["Environment Variables",
             "None. Nothing in <font face='Courier'>src/</font> reads one; the "
             "API is called at the relative path "
             "<font face='Courier'>/api/v1</font>."],
        ],
    }),

    ("h2", "4.4 The five rewrites"),

    ("p", "Added under <b>Redirects/Rewrites</b> on the static site. Without "
          "these the landing page loads but every deep link 404s and no data "
          "ever arrives."),

    ("table", {
        "cols": ["Source", "Destination", "Action"],
        "widths": [0.18, 0.62, 0.20],
        "rows": [
            ["<font face='Courier'>/api/*</font>",
             "<font face='Courier'>https://servorabd-api.onrender.com/api/*"
             "</font>", "Rewrite"],
            ["<font face='Courier'>/admin/*</font>",
             "<font face='Courier'>https://servorabd-api.onrender.com/admin/*"
             "</font>", "Rewrite"],
            ["<font face='Courier'>/static/*</font>",
             "<font face='Courier'>https://servorabd-api.onrender.com/static/*"
             "</font>", "Rewrite"],
            ["<font face='Courier'>/</font>",
             "<font face='Courier'>/index.html</font>", "Rewrite"],
            ["<font face='Courier'>/*</font>",
             "<font face='Courier'>/app.html</font>", "Rewrite"],
        ],
    }),

    ("p", "Order matters: <font face='Courier'>/*</font> is a catch-all and "
          "swallows anything listed below it. The action must be "
          "<b>Rewrite</b>, not Redirect &mdash; a redirect changes the "
          "browser&rsquo;s address bar and breaks the single-origin "
          "arrangement."),

    ("h2", "4.5 Seeding"),

    ("p", "Free web services have no shell, so these were run locally against "
          "the Neon connection string, from "
          "<font face='Courier'>backend/</font> with the virtual environment "
          "active:"),

    ("code", [
        "$env:DATABASE_URL = \"<Neon connection string>\"",
        "$env:DJANGO_SETTINGS_MODULE = \"config.settings.prod\"",
        "$env:SECRET_KEY = \"one-off\"",
        "python manage.py seed_catalogue      # 8 categories, 45 services,",
        "                                     # 38 locations",
        "python manage.py createsuperuser",
    ]),

    ("callout", {
        "title": "createsuperuser does not ask for a name",
        "body": "The user model has "
                "<font face='Courier'>REQUIRED_FIELDS = []</font> and "
                "<font face='Courier'>full_name</font> is "
                "<font face='Courier'>blank=True</font>, so the admin account "
                "is created with an empty name and the site header shows "
                "nothing. Accounts made through the normal registration form "
                "are unaffected. Fix it in "
                "<font face='Courier'>/admin/</font> &gt; Users, or with "
                "<font face='Courier'>manage.py shell</font>.",
    }),

    ("h2", "4.6 Moving the database to Neon"),

    ("p", "Render&rsquo;s free database reached its 30-day limit and was "
          "deleted, and the site lost its data with it. The free plan has no "
          "backups, so there was nothing to copy across. The move was a fresh "
          "start:"),

    ("bullets", [
        "Created a Neon project as in 4.1 and copied the direct connection "
        "string.",
        "Replaced <font face='Courier'>DATABASE_URL</font> on "
        "<font face='Courier'>servorabd-api</font> with it. Saving the "
        "variable redeployed the service, and the build ran every migration "
        "against the empty database.",
        "Ran <font face='Courier'>seed_catalogue</font> and "
        "<font face='Courier'>createsuperuser</font> locally, as in 4.5.",
        "Signed in to <font face='Courier'>/admin/</font> as the new "
        "superuser and enrolled its authenticator app.",
    ]),

    ("p", "Checked afterwards: <font face='Courier'>/healthz/</font> reports "
          "the database <font face='Courier'>ok</font>, and the categories and "
          "services come back through both the API address and the static "
          "site&rsquo;s rewrite. Nothing in the code changed."),

    ("pagebreak", None),
)


# ======================================================================
# 5. Verification
# ======================================================================
add(
    ("h1", "5. How it was verified"),

    ("h2", "5.1 Before deploying, locally"),

    ("bullets", [
        "Production settings load with only the variables Render sets by "
        "itself &mdash; no SMTP, no bucket, no "
        "<font face='Courier'>.env</font> file &mdash; which is the state of a "
        "first deploy. This is the check that caught the crash in 2.1.",
        "Booted under <font face='Courier'>config.settings.prod</font> against "
        "a real PostgreSQL database: "
        "<font face='Courier'>/healthz/</font> returned "
        "<font face='Courier'>ok</font> and "
        "<font face='Courier'>/api/v1/categories/</font> returned its rows.",
        "<font face='Courier'>check --deploy --fail-level WARNING</font> clean "
        "both bare and fully configured.",
        "<font face='Courier'>collectstatic</font> writes through WhiteNoise "
        "to local disk even with object storage on, so the build step needs no "
        "bucket credentials.",
        "<font face='Courier'>gunicorn.conf.py</font> resolves from "
        "<font face='Courier'>rootDir: backend</font> and binds to "
        "<font face='Courier'>$PORT</font>.",
        "The frontend build emits both "
        "<font face='Courier'>index.html</font> and "
        "<font face='Courier'>app.html</font>.",
        "The full backend test suite passes.",
    ]),

    ("h2", "5.2 After deploying, against the live site"),

    ("table", {
        "cols": ["Check", "Result"],
        "widths": [0.46, 0.54],
        "rows": [
            ["<font face='Courier'>/healthz/</font>",
             "<font face='Courier'>{\"status\": \"ok\", "
             "\"database\": \"ok\"}</font>"],
            ["<font face='Courier'>/</font>", "200, landing page"],
            ["<font face='Courier'>/providers</font>",
             "200, served from <font face='Courier'>app.html</font>"],
            ["<font face='Courier'>/services</font>", "200"],
            ["<font face='Courier'>/admin/login/</font>", "200, styled"],
            ["Hashed admin CSS",
             "200 &mdash; proves WhiteNoise&rsquo;s manifest storage works"],
            ["<font face='Courier'>/api/v1/categories/</font>",
             "8 categories through the rewrite"],
            ["<font face='Courier'>/api/v1/locations/</font>",
             "38 locations"],
        ],
    }),

    ("pagebreak", None),
)


# ======================================================================
# 6. Outstanding
# ======================================================================
add(
    ("h1", "6. What is still outstanding"),

    ("h2", "6.1 Two things to act on"),

    ("callout", {
        "title": "Delete the expired Render database",
        "body": "<font face='Courier'>servorabd-db</font> still appears in the "
                "Render dashboard as expired. Nothing uses it. Delete it so "
                "no one mistakes it for the live database.",
    }),

    ("callout", {
        "title": "Take your own copies",
        "body": "Neon&rsquo;s free plan keeps only a few hours of history to "
                "restore from, so a mistake noticed the next day cannot be "
                "undone there. Take a <font face='Courier'>pg_dump</font> "
                "(6.3) before anything risky and keep it off the server. If "
                "the connection string is ever shown on screen or pasted "
                "anywhere, reset the role&rsquo;s password in Neon and update "
                "<font face='Courier'>DATABASE_URL</font>.",
    }),

    ("h2", "6.2 Working as designed, but limited"),

    ("table", {
        "cols": ["Limitation", "Consequence"],
        "widths": [0.30, 0.70],
        "rows": [
            ["No SMTP configured",
             "Login codes are e-mailed, so <b>nobody can register or log "
             "in</b>. Browsing works; the admin account is unaffected because "
             "it is password-based. Set "
             "<font face='Courier'>EMAIL_HOST</font>, "
             "<font face='Courier'>EMAIL_HOST_USER</font>, "
             "<font face='Courier'>EMAIL_HOST_PASSWORD</font> and "
             "<font face='Courier'>DEFAULT_FROM_EMAIL</font> to switch the "
             "mail backend on."],
            ["No cron services on free",
             "The seven scheduled jobs never run: bookings do not auto-expire, "
             "reviews do not reveal after 14 days, trust scores do not "
             "recompute. Run them by hand with "
             "<font face='Courier'>manage.py run_scheduled_jobs</font>."],
            ["No persistent disk",
             "Uploads are written to the container filesystem, which is wiped "
             "on every deploy and every wake-from-sleep."],
            ["Service sleeps after 15 minutes",
             "The first visit after a quiet period takes roughly 50 seconds. "
             "Open the site a minute before showing it to anyone."],
        ],
    }),

    ("h2", "6.3 Moving to paid"),

    ("p", "<font face='Courier'>render.yaml</font> already describes the paid "
          "arrangement: a service that never sleeps, two cron services, and "
          "object storage for uploads. The database stays on Neon; a paid "
          "Neon plan adds storage and a longer restore window. Take a copy "
          "of the data first:"),

    ("code", [
        "pg_dump --format=custom --no-owner \\",
        "        --dbname=\"<Neon connection string>\" \\",
        "        --file=servorabd.dump",
    ]),

    ("p", "<font face='Courier'>deploy/RENDER.md</font> covers the paid route "
          "in full, including the object storage bucket and the rate-limiting "
          "check that needs a live deployment."),

    ("h2", "6.4 One check worth doing"),

    ("p", "Rate limits identify a caller by IP address, read from "
          "<font face='Courier'>X-Forwarded-For</font>, trusting as many "
          "entries as <font face='Courier'>TRUSTED_PROXY_COUNT</font> says. "
          "Too high a number and a forged header buys a fresh allowance on "
          "every request. It is set to "
          "<font face='Courier'>1</font>, correct for a single Render proxy, "
          "but unconfirmed against a live deployment. To check, set "
          "<font face='Courier'>EXPOSE_CLIENT_IDENT=True</font>, wait for the "
          "redeploy, then run locally and set it back to "
          "<font face='Courier'>False</font> afterwards:"),

    ("code", [
        "python manage.py check_proxy_count \\",
        "    https://servorabd-api.onrender.com/api/v1/categories/",
    ]),

    ("h2", "6.5 Updating the live site"),

    ("p", "Push to <font face='Courier'>main</font>. Both services rebuild, "
          "and the API runs its migrations as part of the build. A failed "
          "build leaves the previous version serving, so a broken push does "
          "not take the site down."),
)
