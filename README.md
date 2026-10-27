# ServoraBd

A local service marketplace connecting customers with verified electricians,
plumbers, AC technicians and other tradespeople in Dhaka.

The point of this project is not the booking flow — that is a well-understood
problem. It is the **trust model**.


<img width="1892" height="857" alt="Screenshot 2026-09-30 004244" src="https://github.com/user-attachments/assets/fe0494b5-057d-407f-acb4-bdab3a7d2fc1" />
<img width="1892" height="855" alt="Screenshot 2026-09-30 004259" src="https://github.com/user-attachments/assets/8e35adf9-1ead-4f93-b92f-110fe2858c2b" />
<img width="1892" height="857" alt="Screenshot 2026-09-30 004311" src="https://github.com/user-attachments/assets/ebd192d2-96b6-4edd-8774-c5316bb028ff" />
<img width="1887" height="857" alt="Screenshot 2026-09-30 004324" src="https://github.com/user-attachments/assets/ebd06c32-c5e6-43fa-ad9b-07bd6b012b37" />


## What it is

Hiring a tradesperson in Dhaka runs on phone numbers passed between
neighbours. You get a name, you get a rate quoted over the phone, and you
find out whether the person is any good once they are already in your
kitchen. If they do not turn up, there is no record of it — the next
customer hears the same recommendation you did.

ServoraBd puts that whole exchange on a platform and, more importantly,
keeps a record of it. Customers browse by service and area, see what a job
should cost before they commit, and book a specific provider for a specific
day. Providers get a profile, control over the areas and hours they work,
and a verification badge that means something. Every step of the job —
requested, accepted, started, finished, cancelled — is a recorded event
rather than a phone call nobody can audit.

## What it does

- **Search and discovery.** Filter by category, area, date and price;
  results are ranked by trust, not by who paid for placement.
- **Provider profiles.** Service areas, weekly availability, price ranges,
  a full trust breakdown, and verification tiers from phone-only through
  national ID and trade certificate.
- **Booking lifecycle.** A state machine — requested → accepted → in
  progress → completed, with declines, cancellations and automatic
  expiry — so the platform knows what actually happened on every job.
- **Double-blind reviews.** Neither side sees the other's review until both
  have submitted or fourteen days pass, which removes the retaliation that
  makes ordinary marketplace ratings so uniformly positive.
- **Cash settlement.** Payment is cash on completion, the way this market
  already works. The platform records the payment, computes its commission,
  and keeps an append-only ledger that reconciles against every booking.
- **Trust scoring.** Six factors recomputed from recorded platform events,
  explained below and visible to customers as a breakdown rather than a
  single opaque number.

## The problem it solves

A marketplace is only useful if the ranking can be believed. The hard part
is not taking bookings — it is answering *which of these eleven
electricians should I let into my house*, using evidence the provider
cannot simply assert about themselves. Every factor in the trust score is
derived from something the platform observed: a verification document that
was checked, a booking that was accepted and then abandoned, the minutes
between a request and a reply. Nothing is self-reported.

Which brings us to why the usual answer does not work.

## The problem with star ratings

A provider with one 5-star review outranks a provider with two hundred jobs
averaging 4.8. Ratings cluster so tightly at 4.5–5.0 that they carry almost
no information. And they only measure jobs that were *completed* — a provider
who accepts ten bookings and abandons eight can hold a perfect score.

Consider two real profiles the system produces:

| | Kamal | Shakib |
|---|---|---|
| Star rating | 4.9 | 4.8 |
| Jobs completed | 4 of 4 | 18 of 30 |
| Cancellations | 0 | 12 (3 at under 4h notice) |
| Median response | 8 min | 6 hours |
| Verification | Full (NID + trade cert) | Phone only |
| **Trust score** | **84.2** | **53.5** |

On any conventional marketplace these two look nearly identical. Shakib
abandons 40% of the jobs he accepts and takes six hours to reply — and his
review score is the *highest* of his six factors, which is exactly the signal
a star rating would show you.

## How the trust score works

Six measurable factors, each derived from recorded platform events rather
than self-report:

| Factor | Weight | Captures |
|---|---|---|
| Verification depth | 20% | Has this person proven who they are? |
| Job volume | 15% | Is there enough evidence to judge them? |
| Completion reliability | 20% | When they commit, do they finish? |
| Cancellation discipline | 15% | How often do they break a commitment? |
| Responsiveness | 10% | How long does a customer wait? |
| Review quality | 20% | What do verified customers say? |

The three techniques that make it work:

- **Bayesian smoothing** on completion rate and reviews, so low-volume
  providers regress toward the platform mean instead of scoring 100 on a
  single job.
- **Damage-weighted, time-decayed cancellations** — cancelling an hour before
  costs 4× what cancelling two days ahead costs, and old cancellations fade
  with a 180-day half-life.
- **Logarithmic volume** saturating at 100 jobs, so farming trivial jobs has
  sharply diminishing returns.

Penalties for upheld disputes apply *after* the weighted sum, so one serious
incident cannot be diluted by strong performance elsewhere.

The full algorithm — formulas, anti-gaming design, worked examples — is in
[the PRD](docs/ServoraBd-PRD.pdf), section 7. A runnable reference
implementation lives in [`docs/verify_trust_math.py`](docs/verify_trust_math.py)
and asserts every figure printed in the document.

## Stack

Django 5.2 LTS · Django REST Framework · PostgreSQL 18 · React 18 (JavaScript) · Vite

No Docker, no Celery, no Redis in Phase 1. Recurring work runs as Django
management commands under Task Scheduler / cron; [PRD §8.5](docs/ServoraBd-PRD.pdf)
defines the thresholds that justify adopting a task queue and keeps the
migration to one line per call site.

## Status

| Milestone | State |
|---|---|
| M1 Foundation — auth, OTP, JWT, roles | Done |
| M2 Catalogue — services, locations, seed | Done |
| M3 Providers — profiles, areas, availability, verification | Done |
| M4 Trust engine — six factors, snapshots, audit trail | Done |
| M5 Discovery — search, filters, trust ranking | Done |
| M6 Booking — request lifecycle, state machine | Done |
| M7 Reviews — double-blind, trust feedback | Done |
| M8 Money — cash settlement, commission, earnings | Done |
| M9 Frontend — React client, mobile-first | Done |
| M10 Harden — security, performance, accessibility, deploy | Done |

Backend: 587 tests. Frontend: 47 unit and component tests, plus Playwright
runs of both golden paths and a WCAG 2.1 AA accessibility scan of every page,
in Chromium at a 360px phone viewport. All six trust factors run on real
platform data, and every provider's ledger reconciles against their bookings.
The trust engine reproduces both PRD worked examples exactly (base scores
84.19 and 53.48), and search ranks by trust rather than by price.

## Production readiness

| | Result | PRD target |
|---|---|---|
| Provider search, p95, 10,018 providers | 100 ms | 400 ms |
| Provider detail / trust breakdown, p95 | 42 ms / 16 ms | 250 ms |
| Nightly trust recompute, 10,018 providers | 175 s | 15 min |
| Landing page LCP, Slow 4G, 4x CPU slowdown | 1.58 s (2.63 s before M10) | 2.5 s |
| Accessibility | axe-core finds no WCAG 2.1 AA violations on any page | WCAG 2.1 AA |
| Known vulnerabilities (`pip-audit`, `npm audit`) | 0 | 0 |

The M10 security review fixed a rate-limit bypass through forged
`X-Forwarded-For` headers, stopped accepting HTML files renamed to `.jpg`,
added an audit that fails the suite if any API route forgets its permission
check, and upgraded to Django 5.2 LTS (clearing 37 known vulnerabilities).
Scheduled jobs record every run, and admins can see a job that has stopped.

The site runs on Render's free tier, as a static site and an API service
created by hand after the blueprint was rejected twice. What that costs is
worth knowing before you visit: no SMTP is configured, so login codes cannot
be sent and **nobody can register or sign in** — browsing works, and the
admin, which signs in with a password and an authenticator app, is unaffected. The free plan also allows no
cron services, so the seven scheduled jobs (booking expiry, review reveal,
trust recompute) only run when invoked by hand; uploads do not survive a
deploy; and the service sleeps after fifteen minutes, making the first
request take about fifty seconds. The free database is deleted 30 days after
creation, with no backups.
[`docs/ServoraBd-Render-Deployment.pdf`](docs/ServoraBd-Render-Deployment.pdf)
records what was actually done, including the two failed attempts and what is
still outstanding.

[`render.yaml`](render.yaml) already describes the paid arrangement that
removes those limits, and there are two documented routes onward:
[`deploy/RENDER.md`](deploy/RENDER.md) for Render, which needs no Linux
administration, and [`deploy/DEPLOY.md`](deploy/DEPLOY.md) for a plain Ubuntu
server with Nginx, gunicorn, systemd, cron and backups. CI (GitHub Actions)
runs the backend suite against PostgreSQL 18, the frontend checks, both golden
paths with the accessibility scan, and the dependency audits on every push.

## Getting started

Requires Python 3.12, PostgreSQL 16+, and Node 20+. The database needs no
extensions.

```bash
# database (once, as the postgres superuser)
psql -U postgres -c "CREATE DATABASE servorabd;"
psql -U postgres -c "CREATE USER servora WITH PASSWORD 'your-password' CREATEDB;"
psql -U postgres -d servorabd -c "ALTER SCHEMA public OWNER TO servora;"

# backend
cd backend
python -m venv venv
venv\Scripts\activate          # macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env           # fill in SECRET_KEY and DATABASE_URL
python manage.py migrate
python manage.py seed_catalogue
python manage.py seed_demo       # optional: 18 providers with real history
python manage.py runserver

# frontend, in a second terminal
cd frontend
npm install
npm run dev                    # http://127.0.0.1:5173
```

Full setup notes, including the PostgreSQL 15+ schema-grant that `migrate`
requires, are in [PRD §11](docs/ServoraBd-PRD.pdf) and
[`backend/README.md`](backend/README.md).

## Repository layout

```
docs/       PRD (PDF + the source that generates it), trust math reference
backend/    Django project — see backend/README.md
frontend/   React client — see frontend/README.md
deploy/     server configs, backup scripts, both deployment guides
render.yaml Render blueprint: database, API, cron jobs, static site
.github/    CI workflow
```

## Documentation

- [Product Requirements Document](docs/ServoraBd-PRD.pdf) — 40 pages, the full spec
- [Engineering & Interview Guide](docs/ServoraBd-Guide.pdf) — how to run it, how each layer works, why each decision was made
- [`backend/README.md`](backend/README.md) — running it, endpoints, design notes
- [`frontend/README.md`](frontend/README.md) — running it, checks, accessibility, performance
- [Render deployment record](docs/ServoraBd-Render-Deployment.pdf) — how the live site was actually deployed, and what is outstanding
- [`deploy/RENDER.md`](deploy/RENDER.md) — deploying on Render (the simpler route)
- [`deploy/DEPLOY.md`](deploy/DEPLOY.md) — deploying on your own Ubuntu server
- [`docs/README.md`](docs/README.md) — how the PRD is generated and verified
