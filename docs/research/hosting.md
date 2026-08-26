# Hosting: viable paths for a 10-user app, ranked by ops burden

Research for issue #7. Downstream consumers: #14 (tech stack), #16 (public access and security posture).

**All figures checked 2026-08-26** against the provider's own pricing/limits pages. Every claim below links to
the page that owns it. Free tiers move fast — three of the providers surveyed have changed materially in the
last two years (Fly removed its free allowance, Render's free Postgres now self-destructs, Hetzner raised
prices in June 2026), so re-verify before committing money.

**Workload assumed:** 5–10 users, a few marathons a year, near-zero traffic for months at a time, then a burst.
Persistent relational data (marathons, suggestions, votes, slates). A solver that may run server-side for tens
of seconds. Must be HTTPS-reachable on a custom domain. Losing a marathon's votes mid-marathon is the failure
that matters.

---

## 1. Recommendation

**Ship on Render's paid tier (~$13/month), one always-on web service plus one managed Render Postgres.**

Reasoning, in the order it matters for *this* dev:

1. **It is the smallest number of new concepts.** One service, one database, one dashboard, git push to deploy.
   No VM sizing, no `fly.toml`, no serverless/function decomposition, no Durable Objects, no Linux box.
2. **The durability story is bought, not built.** Paid Render Postgres is continuously backed up with
   point-in-time recovery over the past 3 days on the Hobby workspace, 7 days on Pro
   ([Render backups docs](https://render.com/docs/postgresql-backups)). The dev never has to design, run,
   or test a backup — which is exactly the thing a first-time host gets wrong.
3. **It constrains the stack least.** Native runtimes *or* an arbitrary Dockerfile
   ([Render web services docs](https://render.com/docs/web-services)), so Node, Python, or even a C++ binary
   all work; the solver can be a normal in-process call, a background worker, or a Python MIP stack — no
   platform veto.
4. **No sleeping on paid**, so no cold-start weirdness during a live run-day view, and no "is it down?" from
   friends after four idle months.
5. **$13/month is the real number**, quoted by Render itself in July 2026 for exactly this shape —
   "an always-on Starter web service plus a Basic-256mb Postgres instance on a Hobby workspace typically ran
   about $13/month"
   ([Render, July 2026](https://render.com/articles/how-much-does-cloud-application-hosting-cost-for-small-businesses)).
   For a few marathons a year that is ~$156/year, or roughly one cinema ticket a month for the whole group.

**Runner-up: Fly.io (~$3–6/month)** if cost matters more than concept count, or if the solver wants a real
always-warm process and a native binary. Cheapest credible option with proper containers, but you must choose
SQLite-on-a-volume: Fly's Managed Postgres starts at **$38/month**, which dwarfs everything else here.

**Free alternative: Vercel Hobby + Neon Free ($0)** — genuinely viable now that Hobby functions allow
**300 s** max duration, but it forces a serverless architecture and a Node/Python-shaped app, and Hobby is
**non-commercial use only**. Fine for a friends' movie app; a dead end the moment money is involved.

**Do not** start on: Render's free tier (the database deletes itself), Supabase Free (pauses after a week
idle), Oracle Always Free (Oracle can reclaim an idle instance), or Cloudflare Workers free (10 ms CPU).
Details in §5.

---

## 2. Ranked shortlist

| Rank | Option | Real cost/mo | Why it ranks here |
|---|---|---|---|
| 1 | **Render** (Starter web + Basic-256mb Postgres, Hobby workspace) | **~$13** | Lowest concept count with a bought backup story. No sleep, free TLS, custom domain, any runtime via Docker. |
| 2 | **Fly.io** (shared-cpu-1x 256 MB + 1 GB volume, SQLite + Litestream) | **~$2.20–5** | Cheapest credible. Containers → zero stack constraint. Costs one more layer of understanding (Machines, volumes, autostop) and you own the SQLite backup design. |
| 3 | **Vercel Hobby + Neon Free** | **$0** | Zero ops, zero cost, 300 s function limit is enough for the solver. But serverless-only architecture, non-commercial licence, DB is a separate vendor. |

Honourable mention: **Railway Hobby ($5/mo including $5 of usage)** is functionally interchangeable with
Render for this workload and slightly cheaper; it drops a rank only because backups are opt-in scheduled jobs
you must remember to configure, and per-second metered billing makes the monthly number less predictable.

---

## 3. Comparison table

| | Cost at this scale | Sleeps / cold start | HTTPS | Custom domain | Database provisioning & backup | Ops burden |
|---|---|---|---|---|---|---|
| **Render** | ~$13/mo paid; free tier exists but see §5 | Paid: no. Free: spins down after **15 min** idle, ~**1 min** to wake | Free managed TLS | Yes | Managed Postgres, one click. Paid DBs continuously backed up; PITR **3 days** (Hobby workspace) / **7 days** (Pro). Storage $0.30/GB-mo | **Lowest**: git push + a dashboard |
| **Railway** | Hobby **$5/mo** incl. $5 usage; RAM ~$10/GB-mo, vCPU ~$20/vCPU-mo metered | Optional "Serverless" scale-to-zero; first request may return **502** | Yes | Yes | Postgres service on a volume (Hobby max **5 GB**). Backups **not automatic by default** — daily (kept 6 days), weekly (1 mo), monthly (3 mo) schedules, billed per incremental GB | **Low**, but you own the backup schedule |
| **Fly.io** | ~$2.02/mo shared-cpu-1x 256 MB always-on + $0.15/GB-mo volume; **no free tier** | Autostop/autostart or suspend; restart "well under a second"; stopped machines aren't billed for CPU/RAM | Free (first 10 hostname certs free) | Yes | **Managed Postgres from $38/mo** + $0.28/GB storage. Realistic path is SQLite on a volume: automatic **daily** snapshots, default **5-day** retention, configurable 1–60 days, first 10 GB/mo free | **Medium**: Machines, volumes, `fly.toml`, and you design the SQLite durability story |
| **Vercel** (+ Neon / Supabase / Turso) | Hobby **$0** (non-commercial only) | Functions cold-start; no always-on process | Automatic | Yes, 50 domains/project on Hobby | No storage of its own — bring Neon (free 0.5 GB/project, 100 CU-hr, scale-to-zero after **5 min**, PITR **6 h**), Turso (free 5 GB, PITR **1 day**), or Supabase (free 500 MB but **pauses after 1 week idle**) | **Lowest ops, highest architectural constraint** |
| **Cloudflare Workers/Pages + D1** | $0 free, or **$5/mo** Workers Paid | Effectively no cold start; D1 scale-to-zero billing | Automatic | Yes | D1: free 5 GB total / **500 MB max per DB**, paid 10 GB max per DB. Time Travel PITR **7 days** free / **30 days** paid — best free backup story surveyed | **Low ops, severe runtime constraint** (see §6) |
| **VPS — Hetzner** | CX23 **€5.49/mo** (ex VAT, since 15 Jun 2026) + **€0.50/mo** IPv4 + backups at **20%** of server price ⇒ ~**€7/mo ex VAT** | Never sleeps | You install it (certbot/Caddy) | You configure DNS | You install and tune Postgres or SQLite; automatic daily image backups, **7 slots**, oldest rotated out | **Highest: you now own a Linux box** |
| **VPS — DigitalOcean** | **$4/mo** (1 vCPU / 512 MiB / 10 GiB) + **20%** weekly backups ($0.80); DO Managed Postgres if wanted is **$15.15/mo** | Never sleeps | You install it | You configure DNS | Self-managed, or DO Managed Postgres $15.15/mo (1 GiB / 1 vCPU) | **Highest** |
| **Free-tier-only** (Oracle Always Free etc.) | $0 | n/a | You install it | Yes | You own everything | **Highest + reclamation risk** (§5) |

---

## 4. Deploy story per option

- **Render** — connect the GitHub repo, pick a branch; every push builds and deploys. Native runtime or
  `Dockerfile` ([docs](https://render.com/docs/web-services)). Long jobs can move to a Background Worker,
  a separate always-on service that receives no HTTP traffic ([docs](https://render.com/docs/background-workers)).
- **Railway** — connect repo, auto-detect or Dockerfile, push to deploy. Note that a service with a volume
  **cannot run two deployments at once**, so every redeploy causes brief downtime: *"To prevent data
  corruption, we prevent multiple deployments from being active and mounted to the same service"*
  ([docs](https://docs.railway.com/reference/volumes)).
- **Fly.io** — `fly launch` generates a `fly.toml` and a Dockerfile; `fly deploy` builds the image and rolls
  Machines. You will learn what a Machine, a volume, and a region are. That is real learning, but it is
  *infrastructure* learning, not web-architecture learning.
- **Vercel** — git push. Nothing else. The cost is that your app must be shaped as functions + static assets.
- **Cloudflare** — `wrangler deploy`. Config in `wrangler.jsonc`, bindings for D1/R2/Containers. A bespoke
  (if well-documented) mental model.
- **VPS** — you build the deploy story: ssh + git pull + systemd, or Docker Compose, or a CI runner with a
  deploy key. Plus TLS renewal, reverse proxy, firewall, unattended upgrades, and monitoring that it's all
  still working four months later.

---

## 5. Free tiers: what is actually true today (checked 2026-08-26)

The months-long idle gap makes "what happens to an unused free resource" the decisive question. It kills
several otherwise-attractive options.

- **Render free Postgres — disqualifying.** *"Free Render Postgres databases expire 30 days after creation"*,
  followed by a 14-day grace period, after which *"Render deletes the database (along with all of its data)"*.
  Free databases also get **no recovery capability at all**: *"Render does not provide recovery capabilities
  for databases on the Free instance type"* ([Render free tier docs](https://render.com/docs/free),
  [backups docs](https://render.com/docs/postgresql-backups)). Free *web services* are fine-ish — 750 free
  instance hours/month/workspace, spin down after 15 minutes idle, ~1 minute to wake — but the database makes
  the free tier unusable for anything you care about.
- **Supabase Free — disqualifying for this usage pattern.** *"Free projects are paused after 1 week of
  inactivity. Limit of 2 active projects."* Free plans get **no automatic backups**; daily backups with 7-day
  retention start on Pro at **$25/mo**, PITR is a **$100/mo** add-on
  ([Supabase pricing](https://supabase.com/pricing)). Paused projects can be restored manually, but a paused
  DB the night before a marathon is exactly the failure mode to avoid.
- **Neon Free — viable.** 0.5 GB storage/project, 100 CU-hours/project, up to 100 projects; compute
  scale-to-zero after **5 minutes** and it *"cannot [be] disable[d]"* on Free. History/PITR window is
  **6 hours (1 GB limit)**. Neon's plan docs state **no** policy of deleting inactive free projects — the
  documented consequence of exceeding limits is compute suspension until the next billing month
  ([Neon pricing](https://neon.com/pricing), [Neon plans](https://neon.com/docs/introduction/plans)).
  First paid tier (Launch) is usage-based with no monthly minimum: $0.106/CU-hour, $0.35/GB-month.
- **Turso Free — viable.** 100 databases, 5 GB storage, 500 M monthly row reads, 10 M writes, PITR **1 day**.
  Developer plan $4.99/mo ([Turso pricing](https://turso.tech/pricing)). Turso's pricing page states no
  idle-archival policy, so treat "does an idle DB survive six months" as unverified.
- **Fly.io — the free tier is gone.** What remains is a trial: *"2 hours of machine runtime or 7 days of
  access, whichever comes first"*, after which *"your apps will stop running"* until you add a card
  ([Fly free trial docs](https://fly.io/docs/about/free-trial/)). Billing afterwards is pure usage-based with
  no plan fee and no minimum ([Fly billing docs](https://fly.io/docs/about/billing/)).
- **Railway — effectively no free tier.** Trial is a one-time $5 grant; the Free plan gives **$1 of credit per
  month** with 0.5 GB RAM and 0.5 GB volume — not enough for an app plus a database
  ([Railway plans](https://docs.railway.com/reference/pricing/plans)). Hobby at **$5/mo** is the real entry point.
- **Cloudflare Workers Free — usable for the app, not for the solver.** 100,000 requests/day but only
  **10 ms of CPU time per invocation** ([Workers limits](https://developers.cloudflare.com/workers/platform/limits/)).
  D1 free gives 5 M row reads/day, 100 K writes/day, 5 GB total, 500 MB max per database, and **7 days** of
  Time Travel PITR ([D1 pricing](https://developers.cloudflare.com/d1/platform/pricing/),
  [D1 limits](https://developers.cloudflare.com/d1/platform/limits/)).
- **Vercel Hobby — free but licence-limited.** *"the Hobby plan restricts users to non-commercial, personal
  use only"* ([Vercel Hobby plan](https://vercel.com/docs/plans/hobby)). Included: 1 M function invocations,
  4 CPU-hours active CPU, 360 GB-hours provisioned memory, 100 deployments/day, 50 domains per project.
- **Oracle Cloud Always Free — do not build the marathon on it.** Generous on paper (1,500 OCPU-hours +
  9,000 GB-hours/month of Ampere A1 ≈ 2 OCPU / 12 GB, 200 GB block storage, 10 TB egress) but Oracle states:
  *"Idle Always Free compute instances may be reclaimed by Oracle"* — deemed idle if over a 7-day period the
  95th-percentile CPU is under 20%, network under 20%, and (on A1) memory under 20%
  ([Oracle Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)).
  An app that is idle for four months at a time is the textbook reclamation candidate.

---

## 6. Runtime constraints — what would rule an option out

These are the flags for **#14 (tech stack)**.

**Hard stack constraints:**

- **Cloudflare Workers constrains the stack more than any other option here.** The runtime is JS/WASM: no
  native binaries, no arbitrary process. Python Workers are **in open beta**, built on Pyodide/PyEmscripten
  wheels, and *"WebAssembly support for Python packages is still in early stages, and some packages may not
  yet be available as PyEmscripten wheels on PyPI"*; only async HTTP clients (aiohttp, httpx) work
  ([Python Workers](https://developers.cloudflare.com/workers/languages/python/),
  [packages](https://developers.cloudflare.com/workers/languages/python/packages/)). **A pip-installed MIP
  solver with C extensions will not run on Workers.** On the free plan the 10 ms CPU limit forces the solver
  into the browser regardless. On Workers Paid ($5/mo) CPU rises to 30 s default / **5 min max** per request,
  which would be enough — but only for a WASM-compiled solver.
  *Escape hatch:* **Cloudflare Containers** (Workers Paid) runs *"code written in any programming language,
  built for any runtime"* from a container image, scales to zero, and includes 25 GiB-hours memory /
  375 vCPU-minutes / 200 GB-hours disk per month
  ([Containers pricing](https://developers.cloudflare.com/containers/pricing/)). This rescues the solver but
  buys a bespoke Worker + Durable Object + Container programming model — exactly the "master a proprietary
  runtime" cost this project is trying to avoid.
- **Vercel constrains the architecture, not the language.** No always-on process and no local filesystem, so
  the database must be external and any long job is a function invocation. But the timeout is no longer the
  blocker it used to be: with fluid compute, **Hobby max duration is 300 s** (Pro 800 s, 1800 s in beta),
  memory 2 GB / 1 vCPU on Hobby ([Vercel function limits](https://vercel.com/docs/functions/limitations)).
  The Python runtime supports 3.12/3.13/3.14 with dependencies from `requirements.txt` / `pyproject.toml`, and
  bundles up to **250 MB (500 MB for Python)**
  ([Vercel Python runtime](https://vercel.com/docs/functions/runtimes/python)). A tens-of-seconds MIP solve
  fits inside 300 s. Request/response bodies are capped at **4.5 MB** — irrelevant at this data size.
- **Render, Railway, Fly and any VPS impose no language constraint** — all four run arbitrary Docker images,
  so Node, Python + a MIP solver, or a compiled C++ binary are all on the table. If preserving the option of
  writing part of the backend in C++ matters, these are the four that keep it open.
- **Unverified:** Render's docs do not document a hard HTTP request timeout for web services (checked
  2026-08-26). Do not design around a 60-second synchronous solve request on faith — see below.

**Architectural advice that follows, regardless of host:** do not run a tens-of-seconds solve inside a
synchronous HTTP request. Kick off a job, return an id, poll or stream progress. That pattern works on every
option in this document, removes the timeout question entirely, and is itself a good web-architecture lesson.
On Render that means a Background Worker; on Fly a second process or Machine; on Vercel a second function
invocation; on Cloudflare a Queue consumer (15 min limit) or a Container.

---

## 7. Data durability: SQLite on a volume vs managed Postgres

The failure that matters is losing votes mid-marathon. Two credible answers:

**Managed Postgres (recommended).** Someone else runs the backups and you can restore to a point in time.
Cheapest credible options: Render Postgres inside the ~$13/mo bundle (PITR 3 days on Hobby workspace, 7 on
Pro), Neon Free ($0, PITR 6 hours), Turso Free ($0, PITR 1 day), Cloudflare D1 free (Time Travel 7 days).
Avoid: **Fly Managed Postgres at $38/mo Basic** ([Fly MPG](https://fly.io/docs/mpg/overview/)) — more than
double the entire Render bundle; DigitalOcean Managed Postgres at $15.15/mo.

**SQLite on a volume (viable, cheapest, but you own it).** Works fine at 10 users — but a single volume is a
single copy. Fly is explicit: *"If you only have a single copy of your data on a single volume, and the host
fails, then any data stored between the time when the snapshot was taken and the time when the failure
occurred will be lost"*; automatic daily snapshots default to **5-day** retention, configurable 1–60 days
([Fly volume snapshots](https://fly.io/docs/volumes/snapshots/)). The cheap fix is
[**Litestream**](https://litestream.io/) — open source, streams SQLite changes continuously to object storage,
no application code changes — replicating to **Cloudflare R2**, whose free tier is 10 GB-month with **zero
egress charges** ([R2 pricing](https://developers.cloudflare.com/r2/pricing/)). Total durability cost: $0.
Total durability *understanding* cost: you must set it up and actually test a restore, which a first-time
host usually doesn't.

**Explicitly avoid Fly's unmanaged Postgres.** Fly's own docs warn: *"We are not able to provide support or
guidance for unmanaged Postgres"* and note it is *"not the same thing as a managed database service"*
([Fly Postgres docs](https://fly.io/docs/postgres/)). That is a managed-DB-shaped thing with none of the
guarantees — the worst of both worlds for someone who has never hosted anything.

**Verdict:** for a few marathons a year, a managed Postgres is worth the money. $13/mo buys away the entire
class of "I thought I had backups" failures. If the budget must be $0–3, take Fly + SQLite + Litestream to R2
and *test the restore before the first marathon*.

---

## 8. Security posture — what the dev must understand (input to #16)

Roughly in order of how much you must learn:

- **Vercel / Render / Railway / Fly / Cloudflare:** TLS certificates are issued and renewed for you, and the
  platform terminates HTTPS at its edge. There is no OS to patch and no SSH port to leave open. Your
  remaining responsibilities are application-level: authentication, session handling, secrets in environment
  variables (never in the repo), and not writing SQL injection. That is the correct set of things for a
  web-architecture learning project to be worrying about.
- **VPS:** everything above, plus SSH key-only login, a firewall, unattended security upgrades, a reverse
  proxy, certbot/Caddy renewal, database network exposure, and noticing when any of it breaks. This is a
  second discipline (Linux sysadmin) bolted onto the first, and it is the single strongest argument against
  the VPS path for this dev — the €7/mo price is not the real cost.
- **Useful shortcut for a fixed group of friends:** **Cloudflare Access** can gate the whole app behind an
  identity provider or an email one-time PIN before any request reaches the origin, and the Zero Trust free
  plan *"protects up to 50 users at no cost"*
  ([Cloudflare blog](https://blog.cloudflare.com/teams-plans/),
  [Access policies docs](https://developers.cloudflare.com/cloudflare-one/policies/access/)). For a 5–10
  person marathon this is a legitimate way to be "safely reachable over the internet" without writing an auth
  system on day one. It works in front of any origin, including Render or Fly — it is not Cloudflare-hosting
  lock-in. Note the free-seat figure comes from Cloudflare's own blog; the plans page did not render a
  machine-readable figure on 2026-08-26, so confirm in the dashboard before relying on it.

---

## 9. Price-change watchlist

- **Hetzner raised cloud prices on 15 June 2026, 8 AM CEST.** Examples from Hetzner's own notice: CX23
  €3.99 → **€5.49/mo**, CAX11 €4.49 → **€5.99/mo**, CPX22 €7.99 → **€19.49/mo**, CCX13 €15.99 → **€42.99/mo**
  (all ex VAT and ex IPv4)
  ([Hetzner price adjustment](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/)).
  Primary IPv4 is **€0.50/mo excl. VAT** ([Hetzner server docs](https://docs.hetzner.com/cloud/servers/overview/));
  backups cost **20% of the server's monthly price** for seven daily slots
  ([Hetzner billing FAQ](https://docs.hetzner.com/cloud/billing/faq/),
  [backups](https://docs.hetzner.com/cloud/servers/getting-started/enabling-backups/)). Older Hetzner
  marketing pages still quoting CX22 at €3.79/mo ([press release](https://www.hetzner.com/pressroom/new-cx-plans/))
  are pre-adjustment — the VPS price advantage narrowed substantially.
- **Fly.io removed its free allowance**; a card is required and billing is per-second usage-based.
- **Render's free Postgres became a 30-day trial**, not a free tier.
- **Render's live pricing page renders client-side** and could not be read on 2026-08-26; the $13/mo figure
  comes from Render's own July 2026 article and the legacy instance table (Postgres Starter $7/mo,
  [legacy types](https://render.com/docs/postgresql-legacy-instance-types)). Confirm the current Starter web
  service price in the dashboard before committing.

---

## 10. Sources

Fly.io: [pricing](https://fly.io/docs/about/pricing/) · [billing](https://fly.io/docs/about/billing/) ·
[free trial](https://fly.io/docs/about/free-trial/) · [autostop/autostart](https://fly.io/docs/launch/autostop-autostart/) ·
[machines overview](https://fly.io/docs/machines/overview/) · [volume snapshots](https://fly.io/docs/volumes/snapshots/) ·
[Managed Postgres](https://fly.io/docs/mpg/overview/) · [unmanaged Postgres warning](https://fly.io/docs/postgres/)

Railway: [pricing](https://railway.com/pricing) · [plans](https://docs.railway.com/reference/pricing/plans) ·
[volumes](https://docs.railway.com/reference/volumes) · [backups](https://docs.railway.com/reference/backups) ·
[app sleeping / serverless](https://docs.railway.com/reference/app-sleeping)

Render: [free tier](https://render.com/docs/free) · [web services](https://render.com/docs/web-services) ·
[background workers](https://render.com/docs/background-workers) · [Postgres backups](https://render.com/docs/postgresql-backups) ·
[Postgres flexible plans](https://render.com/docs/postgresql-refresh) · [legacy Postgres types](https://render.com/docs/postgresql-legacy-instance-types) ·
[instance types](https://render.com/docs/compute-plans) · [cost article, July 2026](https://render.com/articles/how-much-does-cloud-application-hosting-cost-for-small-businesses)

Vercel: [function limits](https://vercel.com/docs/functions/limitations) · [Hobby plan](https://vercel.com/docs/plans/hobby) ·
[Python runtime](https://vercel.com/docs/functions/runtimes/python)

Cloudflare: [Workers limits](https://developers.cloudflare.com/workers/platform/limits/) ·
[Workers pricing](https://developers.cloudflare.com/workers/platform/pricing/) ·
[Python Workers](https://developers.cloudflare.com/workers/languages/python/) ·
[Python packages](https://developers.cloudflare.com/workers/languages/python/packages/) ·
[D1 pricing](https://developers.cloudflare.com/d1/platform/pricing/) · [D1 limits](https://developers.cloudflare.com/d1/platform/limits/) ·
[Containers](https://developers.cloudflare.com/containers/) · [Containers pricing](https://developers.cloudflare.com/containers/pricing/) ·
[R2 pricing](https://developers.cloudflare.com/r2/pricing/) · [Access policies](https://developers.cloudflare.com/cloudflare-one/policies/access/) ·
[Zero Trust free plan (blog)](https://blog.cloudflare.com/teams-plans/)

Databases: [Neon pricing](https://neon.com/pricing) · [Neon plans](https://neon.com/docs/introduction/plans) ·
[Supabase pricing](https://supabase.com/pricing) · [Turso pricing](https://turso.tech/pricing) · [Litestream](https://litestream.io/)

VPS: [Hetzner price adjustment](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/) ·
[Hetzner billing FAQ](https://docs.hetzner.com/cloud/billing/faq/) · [Hetzner backups](https://docs.hetzner.com/cloud/servers/getting-started/enabling-backups/) ·
[Hetzner servers overview](https://docs.hetzner.com/cloud/servers/overview/) · [Hetzner CX press release](https://www.hetzner.com/pressroom/new-cx-plans/) ·
[DigitalOcean droplets](https://www.digitalocean.com/pricing/droplets) · [DigitalOcean managed databases](https://www.digitalocean.com/pricing/managed-databases) ·
[Oracle Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
