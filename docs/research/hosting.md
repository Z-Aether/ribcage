# Hosting: viable paths for a seasonal 10-user app, ranked by ops burden

Research for issue #7. Downstream consumers: #14 (tech stack), #16 (public access and security posture).

**All figures checked 2026-08-26** against the provider's own pricing/limits pages. Every claim links to the
page that owns it. Free tiers move fast — Fly removed its free allowance, Render's free Postgres became a
30-day trial, Hetzner raised prices in June 2026 — so re-verify before committing money.

**Workload (revised).** The app is **seasonal, not year-round**. It is stood up, run continuously for roughly
**4 weeks** while a marathon is organised (suggest → curate → vote → solve → pick → run day), then **retired
until the next one**, about **3 times a year**. Between marathons the app is deliberately dead. Per the
clean-slate rule, the only state that must survive teardown is **the user list** — a new Marathon carries no
movie library over — and that is backed up locally, to the dev's machine.

Two bars, deliberately separated:

- **In-window bar (unchanged and non-negotiable):** across the ~4 live weeks, losing votes mid-marathon is
  the failure that matters. Recovery to a point minutes-to-hours before an incident must be possible.
- **Cross-window bar (newly relaxed):** between marathons, ~10 rows of user records must survive. A file on
  the dev's laptop clears this bar. Point-in-time recovery does not need to span the gap.

This revision changes the answer materially. §3 states exactly which round-one conclusions survived and which
reversed.

---

## 1. Recommendation

**Ship on Render's paid tier, defined in a `render.yaml` Blueprint, and delete the stack between marathons.
~$12 per marathon, ~$36/year at three marathons.**

Reasoning, in the order it matters for *this* dev:

1. **Teardown genuinely stops the money, and it is prorated to the second.** Render's FAQ: *"Prorated by the
   second. If a service is active for ten seconds in a given month, you are billed only for those ten
   seconds."* ([Render FAQ](https://render.com/docs/faq)). The round-one figure of ~$156/year becomes
   **~$36/year** without changing anything about the platform.
2. **Re-provisioning is one commit, not an afternoon of clicking.** Blueprints are *"Render's
   infrastructure-as-code (IaC) model for defining, deploying, and managing multiple resources with a single
   YAML file"*, and *"You can create multiple Blueprints from a single YAML file. Each Blueprint creates and
   manages a completely independent set of resources"*
   ([Render Blueprints](https://render.com/docs/infrastructure-as-code)). Web service + Postgres + env groups
   are declared in the repo. Spin-up for marathon #2 is: push, connect, Deploy Blueprint. This is the single
   strongest argument for Render under the new model, and it is a stronger argument than the one round one
   used.
3. **It still clears the in-window bar without you building anything.** Paid Render Postgres is continuously
   backed up with PITR over the past 3 days on a Hobby workspace
   ([backups docs](https://render.com/docs/postgresql-backups)). Three days comfortably covers "someone
   dropped the votes table on Tuesday".
4. **It still constrains the stack least** — native runtimes or an arbitrary Dockerfile
   ([web services docs](https://render.com/docs/web-services)) — so Node, Python + a MIP solver, or a compiled
   C++ binary all remain on the table. No platform veto on the solver.
5. **The rebuild is itself the lesson.** The dev's stated goal is web-dev design and architecture
   fundamentals. Declaring infrastructure in a file, tearing it down, and rebuilding it from that file three
   times a year is a better version of that lesson than a server that has been quietly running since March.

**Margin note, stated honestly: this is now a close call, and it was not close in round one.** On pure money
and pure recurring toil, **Fly.io wins** — leave it standing with autostop and the whole year costs roughly
**$5–10** with *zero* teardown/rebuild cycles. Render is recommended over it because Fly makes you design,
run, and *test* your own SQLite backup, and the in-window bar did not relax. If the dev would rather spend an
afternoon learning Litestream once than spend $30/year and do a dump/restore dance three times a year, Fly is
the correct choice and not a mistake.

**Recommended variant if the dump/restore step is unappealing:** run the web service on Render (or Fly) but
put Postgres on **Neon Free** and never tear the database down. Neon Free costs $0, scale-to-zero after
5 minutes is mandatory and harmless here, and Neon's plan docs state no policy of deleting inactive free
projects ([Neon plans](https://neon.com/docs/introduction/plans)). The user list simply persists between
marathons with no export step at all, and the annual bill drops to ~$20. Cost: one more vendor, and Neon
Free's history window is only 6 hours, so the in-window bar needs a nightly dump during the live weeks.

**Do not** use: Oracle Always Free (§6), a VPS (§5), or Cloudflare Workers if the solver runs server-side (§8).

---

## 2. Re-ranked shortlist

| Rank | Option | Per marathon | Per year (×3) | Teardown required? | Why it ranks here |
|---|---|---|---|---|---|
| 1 | **Render paid** — Starter web + Basic-256mb Postgres, `render.yaml` Blueprint | **~$12** | **~$36** | Yes, delete both | Fewest new concepts; managed in-window PITR; one-commit rebuild; per-second proration |
| 2 | **Fly.io** — 256 MB Machine + 1 GB volume, SQLite + Litestream, autostop, **left standing** | **~$1–3** | **~$5–10** | **No** | Cheapest credible and zero recurring toil, but you own the durability design |
| 3 | **Supabase Free** (+ any free frontend host) | **$0** | **$0** | **No — pause is automatic** | Round one's biggest reversal: auto-pause after a week idle now matches the usage pattern exactly. Weak spot is no automatic backups on Free |

Close behind: **Vercel Hobby + Neon Free ($0/year, nothing to tear down)** — unbeatable on cost and toil, but
it forces a serverless architecture and Hobby is non-commercial-use-only. **Railway Hobby (~$15/year if you
cancel the subscription between marathons)** is functionally fine but its IaC is explicitly *"experimental"*
([Railway IaC](https://docs.railway.com/infrastructure-as-code)), which is the wrong property for a thing you
only touch three times a year.

---

## 3. What survived from round one, and what reversed

**Reversed:**

| Round one said | Round two says | Why |
|---|---|---|
| Supabase Free is **disqualifying** — pauses after 1 week idle | **Actively well-suited**, now a top-3 option | Pausing *is* the seasonal model. Data is retained; *"The project will return to its previous state, including data and configurations"*; resume is self-service — *"Click **Resume project** and confirm"*; the restore window is *"a 1-year window to restore the project on the platform from within Supabase Studio"* ([Supabase project pausing](https://supabase.com/docs/guides/platform/free-project-pausing)) |
| Sleeping / cold starts are a **disqualifier** | **A non-issue** | An app that is dead for four months by design cannot be embarrassed by a 15-minute idle spin-down or a 5-minute scale-to-zero |
| Render's free tier is **unusable** | **Conditionally viable, with one sharp edge** | The 30-day database clock is now *nearly* long enough for a 28-day marathon. See §6 — the edge is sharp and worth naming precisely |
| "No sleeping on paid" was a **top-3 reason to pick Render** | **Deleted as a reason** | Replaced by per-second proration and Blueprints, which are better reasons |
| "Bought, not built" cross-window durability justifies **$13/mo** | Justifies **~$12 per marathon**; cross-window durability is now a `pg_dump` or a checked-in file | Only the user list must cross the gap |
| Oracle Always Free rejected because **idle reclamation is fatal** | Still rejected, but for **rebuild burden + undocumented reclamation semantics** | Intending the instance to die defuses the original objection; the replacement objections are stronger (§6) |
| Annual cost of the recommendation: **~$156** | **~$36** (or ~$20 with Neon Free) | Seasonal billing |

**Survived unchanged:**

- **Render is still the recommendation** — but on different pillars, at a quarter of the cost, and by a much
  narrower margin over Fly.
- **The in-window durability bar.** Nothing about the seasonal model makes it acceptable to lose votes on
  day 12 of a marathon.
- **Cloudflare Workers is still the sharpest stack constraint** (§8) — 10 ms CPU on free, JS/WASM only, Python
  in open beta. Unaffected by seasonality.
- **Vercel Hobby is still non-commercial-use-only** and still forces serverless architecture.
- **Fly Managed Postgres at $38/mo is still absurd** at this scale — worse now, since it would be $35 per
  marathon for a database holding ten users and forty films.
- **A VPS is still the worst ops burden** — and seasonality made it *worse*, not better (§5).
- **The June 2026 Hetzner price rise and Fly's removed free tier** are facts, not judgements (§10).

---

## 4. Cost per marathon and per year

A marathon window of 4 weeks is 28 days ≈ **0.92 of a month**; 672 hours. Three per year ≈ 2.76 billed months.

| Option | Cost while idle | Per marathon | Per year (×3) | What you must do to actually hit this number |
|---|---|---|---|---|
| **Render paid** (Starter web + Basic-256mb PG, Hobby workspace $0) | $0 | **~$12** | **~$36** | Delete both resources at teardown; rebuild from `render.yaml` |
| **Render paid web + Neon Free PG** | $0 | **~$6.50** | **~$20** | Delete only the web service; DB just sits there free |
| **Fly.io** (shared-cpu-1x 256 MB $2.02/mo always-on, 1 GB volume $0.15/mo) | ~$0.30/mo storage | **~$1–3** | **~$5–10** | **Nothing.** Autostop handles it; leave it standing |
| **Railway Hobby** ($5/mo incl. $5 usage) | $5/mo unless cancelled | **~$5** | **~$15** | Cancel the subscription between marathons |
| **Render free tier** | $0 | **$0** | **$0** | Accept the 30-day database clock (§6) |
| **Vercel Hobby + Neon Free** | $0 | **$0** | **$0** | Nothing |
| **Supabase Free** | $0 (auto-pauses) | **$0** | **$0** | Nothing; click Resume before each marathon |
| **Cloudflare Workers free + D1** | $0 | **$0** | **$0** | Nothing |
| **Hetzner CX23** (€5.49/mo ex VAT + €0.50 IPv4 + 20% backups) | €0 only if deleted | **~€6** | **~€18** | Delete the server every time; keep a snapshot (billed per GB-month) and rebuild from it |
| **Oracle Always Free** | $0 | $0 | $0 | Not recommended — §6 |

Render's per-marathon figure derives from Render's own July 2026 statement that *"an always-on Starter web
service plus a Basic-256mb Postgres instance on a Hobby workspace typically ran about $13/month"*
([Render](https://render.com/articles/how-much-does-cloud-application-hosting-cost-for-small-businesses)),
scaled by 0.92. Render's live pricing page renders client-side and could not be read on 2026-08-26; confirm
the current Starter price in the dashboard before committing.

---

## 5. Does teardown actually stop the billing?

This is the crux of whether seasonal use saves real money or just adds toil. It is **not** uniform.

- **Render — yes, cleanly.** *"Prorated by the second. If a service is active for ten seconds in a given
  month, you are billed only for those ten seconds"* ([FAQ](https://render.com/docs/faq)); storage is
  likewise *"prorated to the second"*
  ([flexible plans](https://render.com/docs/postgresql-refresh)). **Unverified:** Render's docs do not state
  in so many words that a *suspended* (as opposed to deleted) database stops billing. Assume you must
  **delete**, not suspend, the Postgres instance — and therefore that `pg_dump` before teardown is mandatory.
- **Fly.io — partially, and this is the trap.** Stopped or suspended Machines are not billed for CPU and RAM,
  but storage keeps ticking: *"Each 1GB of rootfs for a Machine stopped for 30 days is $0.15"*, and volumes
  are billed on provisioned capacity — *"You'll be charged for volumes that you create, whether they are
  attached to a Machine or not, including when an attached Machine is stopped"*
  ([Fly pricing](https://fly.io/docs/about/pricing/)). Also note *"Managed Postgres lives outside your apps.
  Deleting an app won't delete its database."* The amounts are trivial (~$1.80/year for a 1 GB volume), which
  is precisely why **the right move on Fly is not to tear down at all** — autostop already reduces the idle
  bill to loose change, and leaving it standing eliminates the entire re-provisioning cycle.
- **Hetzner — only if you delete the server.** *"We will bill you for your servers until you delete them,
  independent of their state"* ([Hetzner billing FAQ](https://docs.hetzner.com/cloud/billing/faq/)). Powering
  a VPS off saves nothing. Preserving the built machine across the gap means a snapshot, billed per
  gigabyte-month.
- **Railway — the $5/mo Hobby fee is a subscription**, not usage; usage stops when services are removed, but
  the subscription does not stop by itself. Deleted volumes are recoverable only briefly: *"When a volume is
  deleted, it is queued for deletion and will be permanently deleted within 48 hours"*
  ([Railway volumes](https://docs.railway.com/reference/volumes)).
- **Vercel Hobby / Neon Free / Supabase Free / Cloudflare free — nothing to stop.** These cost $0 idle by
  construction, which under the seasonal model is a structural advantage, not a consolation prize.

---

## 6. Free tiers re-judged under seasonal use

**Render free Postgres — the sharpest question in this round. Verdict: usable for a first marathon, but know
exactly where the edge is.**

Verbatim from [Render's free tier docs](https://render.com/docs/free):

- *"Free Render Postgres databases expire 30 days after creation."* — **the clock runs from creation, not from
  last use.** Idling the app does not buy time.
- At expiry: *"An expired Free database is inaccessible unless you upgrade it to a paid instance type."*
- Then: 14 days of grace, after which *"Render **deletes** the database (along with all of its data)."*
- *"Only one Free Render Postgres database can be active for any given workspace."*
- *"Render notifies you via email when you're approaching a Free database expiration, and then again when
  you're approaching the end of the grace period."*

**A 28-day marathon against a 30-day clock leaves two days of slack.** Read the failure mode precisely,
because it is less catastrophic than it first sounds: at day 30 the app **breaks** (the database becomes
inaccessible) but the data is **not yet gone** — there are 14 further days in which a one-click upgrade to a
paid instance restores access with data intact. So a marathon that slips a week costs an unplanned ~$6–7 and
an evening of confusion, not a lost vote set — *provided* the dev reads the warning email and acts inside the
grace window. If the dev is the sort to ignore a provider email for two weeks, this is a real data-loss path.

Two further cautions: free web services also spin down after 15 minutes idle and take about a minute to wake
(fine for organising, mildly annoying on run day), and the 750 free instance hours per workspace per month is
just over the 672 hours in a 28-day window — enough for **one** always-on free service, with no room for a
second. **Not verified:** whether creating a fresh free database for each marathon, three times a year, is
within Render's intended use. Their docs do not address it and contain no fair-use language about it. Treat it
as an open question with support rather than an assumption — the honest framing is that the free tier makes a
good *first* marathon (a genuine 30-day trial that happens to match the window), after which ~$12 buys the
question away.

**Supabase Free — reversed to a recommendation.** *"A Free plan project is considered inactive if it does not
receive sufficient user database activity over the past week"*, after which it pauses; data and configuration
are retained (*"The project will return to its previous state, including data and configurations"*); resume is
a single self-service button; and the restore window is a full year
([project pausing](https://supabase.com/docs/guides/platform/free-project-pausing)). The pricing page's limit
of **2 active free projects** is not binding here ([pricing](https://supabase.com/pricing)). Its remaining
weakness is the in-window bar, not the cross-window one: **Free gets no automatic backups** — daily backups
with 7-day retention start at Pro ($25/mo), PITR is a $100/mo add-on. On Supabase Free you must take your own
dumps during the live weeks (§7).

**Neon Free — unchanged and quietly ideal for this model.** 0.5 GB storage and 100 CU-hours per project;
scale-to-zero after 5 minutes, mandatory on Free (*"cannot [be] disable[d]"*); history/PITR window 6 hours,
1 GB limit; the documented consequence of exceeding limits is compute suspension until the next billing
month, **not** project deletion ([Neon pricing](https://neon.com/pricing),
[plans](https://neon.com/docs/introduction/plans)). A Neon project makes an excellent permanent home for a
user list that outlives every other resource.

**Turso Free** — 5 GB, 500 M monthly row reads, PITR 1 day, Developer plan $4.99/mo
([Turso pricing](https://turso.tech/pricing)). Turso's pricing page states no idle-archival policy, so
"does an idle database survive six months" remains **unverified** — the deciding question under this model,
and it is unanswered.

**Cloudflare D1 free** — 5 GB total, 500 MB max per database, 5 M row reads/day, 100 K writes/day, and
**7 days of Time Travel point-in-time recovery on the free plan** (30 days paid)
([D1 pricing](https://developers.cloudflare.com/d1/platform/pricing/),
[limits](https://developers.cloudflare.com/d1/platform/limits/)). That is the strongest free in-window
durability story surveyed. It is attached, unfortunately, to the most stack-constraining runtime (§8).

**Oracle Always Free — still rejected, for better reasons.** Intending the instance to die defuses round one's
objection, but two new ones replace it. First, the semantics are undocumented: Oracle states only that *"Idle
Always Free compute instances may be reclaimed by Oracle"* (idle = 7 days of sub-20% CPU p95, network, and —
on A1 — memory), and the page **does not say** whether a reclaimed instance is stopped or terminated, whether
boot volumes survive, or whether notice is given
([Oracle Always Free](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)).
You cannot plan a teardown/rebuild cycle around a mechanism whose outcome the vendor declines to specify.
Second, whatever reclamation destroys, you rebuild a Linux box from scratch — the worst re-provisioning burden
on this list, three times a year, by a dev who has never hosted anything. Free is not cheap enough for that.

**Fly and Railway have no meaningful free tier.** Fly's trial is *"2 hours of machine runtime or 7 days of
access, whichever comes first"* ([Fly free trial](https://fly.io/docs/about/free-trial/)); Railway's Free plan
is $1/month of credit with 0.5 GB RAM ([Railway plans](https://docs.railway.com/reference/pricing/plans)).
Neither is a seasonal option; both are priced low enough that it doesn't matter.

---

## 7. Durability: the two bars, and the concrete backup flow

**In-window (the ~4 live weeks) — the bar did not move.** Ranked by what you get without building anything:

| Option | In-window recovery | Verdict |
|---|---|---|
| Render Postgres (paid) | Continuous backup, PITR **past 3 days** (Hobby workspace) / 7 days (Pro) | Clears the bar, zero work |
| Cloudflare D1 (free) | Time Travel **7 days** free | Clears the bar, zero work |
| Neon Free | **6 hours** history | Thin — pair with a nightly dump during live weeks |
| Turso Free | **1 day** PITR | Adequate |
| Fly + SQLite on a volume | Automatic **daily** snapshots, default **5-day** retention (configurable 1–60) | Adequate *only* with Litestream on top — see below |
| Supabase Free | **No automatic backups** | Does **not** clear the bar unaided; you must dump nightly yourself |
| Railway volume | Backups **not automatic by default**; daily (kept 6 days) / weekly / monthly schedules must be configured | Clears the bar only if you remember to switch it on |

On Fly, a volume is a single copy and Fly says so plainly: *"If you only have a single copy of your data on a
single volume, and the host fails, then any data stored between the time when the snapshot was taken and the
time when the failure occurred will be lost"* ([volume snapshots](https://fly.io/docs/volumes/snapshots/)).
The fix is [**Litestream**](https://litestream.io/) — open source, streams SQLite changes continuously to
object storage with no application code changes — replicating to **Cloudflare R2**, free up to 10 GB-month
with zero egress charges ([R2 pricing](https://developers.cloudflare.com/r2/pricing/)). Cost: $0. Setup:
an afternoon, once. **Test the restore before the first marathon** — an untested backup is a rumour.

**Cross-window (the months between) — newly trivial.** Concretely, per option:

- **Render.** The dashboard exposes an external connection URL and a ready-made **PSQL Command**: *"Tools and
  systems outside of Render can connect to your database via its external URL"*
  ([connecting docs](https://render.com/docs/postgresql-creating-connecting)). Teardown is
  `pg_dump "$EXTERNAL_URL" -t users -Fc -f users.dump`; spin-up is `pg_restore -d "$NEW_URL" users.dump`.
  Render documents psql and its own on-demand logical exports; `pg_dump` against the external URL is standard
  Postgres and works, but is not itself spelled out in their docs.
- **Neon.** Documented directly: `pg_dump -Fc -v -d <connection_string> -f mydumpfile.bak` and
  `pg_restore -v -O -d <connection_string> mydumpfile.bak`, with two caveats worth heeding — *"Avoid using
  `pg_dump` over a pooled connection string...Use an unpooled connection string instead"*, and pass
  `-O/--no-owner` because *"the `neon_superuser` is not a PostgreSQL `superuser`. It cannot run `ALTER OWNER`
  statements"* ([Neon migration docs](https://neon.com/docs/import/migrate-from-postgres)).
- **Supabase.** `supabase db dump --linked --data-only -f users.sql` — the CLI runs `pg_dump` in a container
  against the remote project via `--linked` or `--db-url`
  ([CLI reference](https://supabase.com/docs/reference/cli/supabase-db-dump)). Or simply don't tear down: the
  automatic pause already retains everything.
- **Fly + SQLite.** Copy the database file off the volume with flyctl's ssh/sftp before teardown — or, again,
  don't tear down.

**The honest answer, though: for ten rows, a database is the wrong home between marathons.** If the surviving
state is a handful of display names and email addresses, keep it as a **seed file in the repo** (or an
environment variable) and apply it at spin-up. That converts cross-window persistence from an ops problem
into a code problem: it is versioned, diffable, reviewable, impossible to forget to export, and it makes
"spin up marathon #4" a single deploy with no restore step. Two caveats: keep it to identities, not secrets
or password hashes (delegate auth — see §9), and make sure the list stays editable *without* a redeploy once
the marathon is live, so adding a late-joining friend isn't a git push.

---

## 8. Runtime constraints — what would rule an option out

Flags for **#14 (tech stack)**. Seasonality changes none of these; they are properties of the runtimes.

- **Cloudflare Workers constrains the stack more than anything else here.** JS/WASM only: no native binaries,
  no arbitrary process. Free plan allows **10 ms of CPU time per invocation**
  ([Workers limits](https://developers.cloudflare.com/workers/platform/limits/)), which forces the solver into
  the browser outright. Workers Paid ($5/mo) raises this to 30 s default / **5 min max** per request, but only
  for WASM-compiled code. Python Workers are **in open beta** on Pyodide/PyEmscripten wheels, where
  *"WebAssembly support for Python packages is still in early stages, and some packages may not yet be
  available as PyEmscripten wheels on PyPI"*, and only async HTTP clients (aiohttp, httpx) work
  ([Python Workers](https://developers.cloudflare.com/workers/languages/python/),
  [packages](https://developers.cloudflare.com/workers/languages/python/packages/)). **A pip-installed MIP
  solver with C extensions will not run on Workers.** The escape hatch is **Cloudflare Containers** on Workers
  Paid — *"Run code written in any programming language, built for any runtime"*, scale-to-zero, with
  25 GiB-hours memory / 375 vCPU-minutes / 200 GB-hours disk included per month
  ([Containers pricing](https://developers.cloudflare.com/containers/pricing/)) — but that buys a bespoke
  Worker + Durable Object + Container model, exactly the proprietary-runtime cost this project avoids. This is
  a shame, because D1's free 7-day Time Travel is the best free durability story surveyed.
- **Vercel constrains architecture, not language.** No always-on process and no local filesystem, so the
  database is a second vendor and every long job is a function invocation. The timeout is no longer a blocker:
  with fluid compute, **Hobby max duration is 300 s** (Pro 800 s, 1800 s beta), memory 2 GB / 1 vCPU on Hobby
  ([function limits](https://vercel.com/docs/functions/limitations)). Python 3.12/3.13/3.14 with
  `requirements.txt` / `pyproject.toml` dependencies and bundles to 250 MB (500 MB for Python)
  ([Python runtime](https://vercel.com/docs/functions/runtimes/python)). A tens-of-seconds MIP solve fits
  inside 300 s. Request/response bodies cap at 4.5 MB — irrelevant here. Hobby remains
  *"non-commercial, personal use only"* ([Hobby plan](https://vercel.com/docs/plans/hobby)).
- **Render, Railway, Fly and any VPS impose no language constraint** — all run arbitrary Docker images. These
  four keep open the option of writing part of the backend in C++.
- **Unverified:** Render's docs do not document a hard HTTP request timeout for web services (checked
  2026-08-26). Don't design around a 60-second synchronous solve on faith.

**Architecture advice that follows regardless of host:** don't run a tens-of-seconds solve inside a
synchronous HTTP request. Start a job, return an id, poll or stream progress. That pattern works everywhere in
this document, deletes the timeout question, and is itself good web-architecture practice. On Render that's a
Background Worker ([docs](https://render.com/docs/background-workers)); on Fly a second process or Machine; on
Vercel a second invocation; on Cloudflare a Queue consumer (15 min) or a Container.

---

## 9. Re-provisioning, config rot and URL stability

Under the seasonal model, **re-provisioning burden replaces steady-state ops burden as the headline axis.**
Setup is no longer a one-time cost amortised over years; it recurs every marathon, each time after a
four-month memory gap.

**Spin-up effort, best to worst:**

1. **Nothing to spin up** — Supabase Free (click Resume), Neon Free (wakes on connection), Vercel Hobby
   (deployment never went away), Fly with autostop (wakes on request; *"Usually this takes well under a
   second"* — [Machines overview](https://fly.io/docs/machines/overview/)). Under a seasonal model this is a
   real and underrated category: **the cheapest re-provisioning is not re-provisioning.**
2. **One commit** — Render Blueprints. `render.yaml` in the repo declares services, databases and environment
   groups; *"Each push to the linked branch that modifies your Blueprint file triggers a deploy of any added
   or modified resources"* ([Blueprints](https://render.com/docs/infrastructure-as-code)).
3. **A few commands** — Fly, if you *do* tear down: `fly launch` / `fly deploy` against the `fly.toml` in the
   repo, plus recreating the volume and restoring the data. The extra steps are the ones most likely to be
   misremembered in four months.
4. **Dashboard clicking, or experimental IaC** — Railway. Its new IaC declares *"services, databases, volumes,
   buckets, custom domains, environment variables, replicas, and canvas groups"* from `.railway/railway.ts`
   applied with `railway config apply`, with *"one project definition, one apply, omit means delete"* — but it
   is explicitly marked **experimental**, and *"Generated `.railway/railway.ts` formatting may change while
   the DSL is experimental"* ([Railway IaC](https://docs.railway.com/infrastructure-as-code)). The older
   config-as-code covers only build and deploy settings, is deprecated with legacy support until 1 Dec 2026,
   and cannot define services, volumes or databases
   ([config as code](https://docs.railway.com/reference/config-as-code)).
5. **An afternoon, every time** — VPS and Oracle. Rebuild the box, or restore a snapshot and then patch four
   months of security updates before you dare expose it.

**Config rot is a genuine recurring cost of this model, and pretending otherwise would be dishonest.** Across a
four-month gap you should expect: base images and language runtimes deprecated, dependency lockfiles that no
longer resolve, expired API tokens (the movie-metadata provider is the obvious candidate), platform UI and
defaults moved, and free-tier terms changed. Two observations:

- **Declared infrastructure rots less than remembered infrastructure.** A `render.yaml` or `fly.toml` in the
  repo is the difference between "rebuild it the way I did last time" and "rebuild it the way the file says".
  This is the strongest practical argument for Render or Fly over click-configured Railway.
- **Rebuilding forces rot to surface at a moment you are paying attention** — at spin-up, three weeks before
  anyone votes — rather than mid-marathon. Options that never tear down (Fly-left-standing, Supabase) trade
  this for the risk that the first `fly deploy` in four months is the one that fails, on the day you needed a
  fix. Neither is strictly safer; the mitigation for both is the same: **spin up a week early and click
  through the whole flow once before inviting anyone.** Put that in the runbook.

**URL stability — genuinely under-documented, so plan around it rather than trusting it.** Render's docs do
not state how `onrender.com` subdomains are assigned, whether they must be globally unique, or whether a
deleted service releases its name; Fly's docs likewise do not state whether app names are globally unique or
reclaimable (both checked 2026-08-26). Given the seasonal model deletes and recreates resources by design,
**assume the platform subdomain may change and buy a cheap custom domain.** That decouples the URL the friends
bookmark from whatever is running underneath, survives a provider switch entirely, and costs ~$10–15/year —
comparable to the entire hosting bill. Render includes 2 custom domains on the Hobby workspace, *"automatically
creates and renews TLS certificates for all custom domains"*, and *"All HTTP traffic to a custom domain is
automatically redirected to HTTPS"* ([custom domains](https://render.com/docs/custom-domains)). **This raises
the value of a custom domain from a nicety to a structural requirement — feed it into #16.**

---

## 10. Security posture — what the dev must understand (input to #16)

- **Vercel / Render / Railway / Fly / Cloudflare:** TLS certificates are issued and renewed for you and
  HTTPS is terminated at the platform edge. No OS to patch, no SSH port left open. Your remaining
  responsibilities are application-level: authentication, session handling, secrets in environment variables
  (never in the repo — and note this constrains the "checked-in user list" idea in §7 to identities only), and
  not writing SQL injection.
- **VPS:** all of the above plus SSH key-only login, a firewall, unattended upgrades, a reverse proxy,
  certificate renewal, database exposure, and monitoring. Under the seasonal model this gets **worse**: a box
  rebuilt three times a year, or restored from a four-month-old snapshot full of unpatched packages, is
  harder to keep safe than one that is continuously maintained. The €18/year is not the cost.
- **A seasonal-specific risk worth naming:** an app that is publicly reachable but unattended for four months
  is a liability. If you do leave something standing (the Fly option), either keep it behind access control or
  take the public route down between marathons. "Dead between marathons" should mean *unreachable*, not merely
  *unused*.
- **Useful shortcut for a fixed group of friends:** **Cloudflare Access** gates the whole app behind an
  identity provider or an email one-time PIN before any request reaches the origin, and the Zero Trust free
  plan *"protects up to 50 users at no cost"* ([Cloudflare blog](https://blog.cloudflare.com/teams-plans/),
  [Access policies](https://developers.cloudflare.com/cloudflare-one/policies/access/)). It works in front of
  any origin — Render, Fly, anything — so it is not hosting lock-in. It also fits the seasonal model neatly:
  the "user list" becomes a list of email addresses in an Access policy, which is both the auth story and the
  cross-window state, and it is edited in a dashboard rather than a deploy. The free-seat figure comes from
  Cloudflare's own blog; their plans page did not render a machine-readable figure on 2026-08-26, so confirm
  in the dashboard before relying on it.

---

## 11. Price-change watchlist

- **Hetzner raised cloud prices on 15 June 2026, 8 AM CEST**: CX23 €3.99 → **€5.49/mo**, CAX11 €4.49 →
  **€5.99/mo**, CPX22 €7.99 → **€19.49/mo**, CCX13 €15.99 → **€42.99/mo**, all ex VAT and ex IPv4
  ([price adjustment](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/)).
  Primary IPv4 is **€0.50/mo excl. VAT** ([servers overview](https://docs.hetzner.com/cloud/servers/overview/));
  backups are **20% of the server's monthly price** for seven daily slots
  ([billing FAQ](https://docs.hetzner.com/cloud/billing/faq/),
  [backups](https://docs.hetzner.com/cloud/servers/getting-started/enabling-backups/)). Marketing pages still
  quoting CX22 at €3.79/mo ([press release](https://www.hetzner.com/pressroom/new-cx-plans/)) are
  pre-adjustment.
- **Fly.io removed its free allowance**; a card is required, billing is per-second usage-based with no plan fee
  and no minimum ([billing](https://fly.io/docs/about/billing/)).
- **Render's free Postgres is a 30-day trial**, not a free tier — the single most important expiry date in this
  document.
- **Supabase's paused-project restore window has moved before**: a June 2024 changelog set it at 90 days, while
  the current docs state one year. Re-check it if the plan depends on a long gap.
- **Railway's IaC is experimental** and its predecessor is deprecated with legacy support only until
  **1 December 2026**.
- **Render's live pricing page renders client-side** and could not be read on 2026-08-26; the ~$13/mo bundle
  figure comes from Render's own July 2026 article plus the legacy instance table (Postgres Starter $7/mo,
  [legacy types](https://render.com/docs/postgresql-legacy-instance-types)).

---

## 12. Sources

Fly.io: [pricing](https://fly.io/docs/about/pricing/) · [billing](https://fly.io/docs/about/billing/) ·
[free trial](https://fly.io/docs/about/free-trial/) · [autostop/autostart](https://fly.io/docs/launch/autostop-autostart/) ·
[machines overview](https://fly.io/docs/machines/overview/) · [volume snapshots](https://fly.io/docs/volumes/snapshots/) ·
[Managed Postgres](https://fly.io/docs/mpg/overview/) · [unmanaged Postgres warning](https://fly.io/docs/postgres/)

Railway: [pricing](https://railway.com/pricing) · [plans](https://docs.railway.com/reference/pricing/plans) ·
[volumes](https://docs.railway.com/reference/volumes) · [backups](https://docs.railway.com/reference/backups) ·
[app sleeping / serverless](https://docs.railway.com/reference/app-sleeping) ·
[Infrastructure as Code](https://docs.railway.com/infrastructure-as-code) ·
[config as code (deprecated)](https://docs.railway.com/reference/config-as-code)

Render: [free tier](https://render.com/docs/free) · [FAQ (billing proration)](https://render.com/docs/faq) ·
[Blueprints / IaC](https://render.com/docs/infrastructure-as-code) · [web services](https://render.com/docs/web-services) ·
[background workers](https://render.com/docs/background-workers) · [Postgres backups](https://render.com/docs/postgresql-backups) ·
[Postgres flexible plans](https://render.com/docs/postgresql-refresh) · [creating & connecting to Postgres](https://render.com/docs/postgresql-creating-connecting) ·
[legacy Postgres types](https://render.com/docs/postgresql-legacy-instance-types) · [instance types](https://render.com/docs/compute-plans) ·
[custom domains](https://render.com/docs/custom-domains) ·
[cost article, July 2026](https://render.com/articles/how-much-does-cloud-application-hosting-cost-for-small-businesses)

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
[Neon pg_dump/pg_restore](https://neon.com/docs/import/migrate-from-postgres) ·
[Supabase pricing](https://supabase.com/pricing) · [Supabase project pausing](https://supabase.com/docs/guides/platform/free-project-pausing) ·
[supabase db dump](https://supabase.com/docs/reference/cli/supabase-db-dump) ·
[Turso pricing](https://turso.tech/pricing) · [Litestream](https://litestream.io/)

VPS / free-tier-only: [Hetzner price adjustment](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/) ·
[Hetzner billing FAQ](https://docs.hetzner.com/cloud/billing/faq/) · [Hetzner backups](https://docs.hetzner.com/cloud/servers/getting-started/enabling-backups/) ·
[Hetzner servers overview](https://docs.hetzner.com/cloud/servers/overview/) · [Hetzner CX press release](https://www.hetzner.com/pressroom/new-cx-plans/) ·
[DigitalOcean droplets](https://www.digitalocean.com/pricing/droplets) · [DigitalOcean managed databases](https://www.digitalocean.com/pricing/managed-databases) ·
[Oracle Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm)
