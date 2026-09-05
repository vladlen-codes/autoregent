# Autoregent

<p align="center">
  <img height="180em" src="https://github.com/vladlen-codes/autoregent/blob/main/assets/logo.jpg" alt="Logo" />
</p>

<p align="center"><b>Your API just healed itself. Autoregent makes sure you find out.</b></p>

An API gateway that heals failing upstreams but is structurally incapable of doing it silently. When a request drifts from its expected schema, Gemini diagnoses it live in the request path and proposes a fix — but the caller's `200 OK` and the disclosure event fire together, every time. A heal is never a secret, and a write-path route is never healed at all.

**Live gateway:** https://autoregent-production.up.railway.app
**Live dashboard:** https://vladlen-codes.github.io/autoregent/
**Docs:** [DOCUMENTATION.md](DOCUMENTATION.md)

---

## The core rule

> Read paths may be healed. Write paths may never be healed.

Informational routes (balance lookups, transaction history) are eligible for AI-diagnosed schema remediation. Transactional routes (ledger writes, transfers, charges) get exactly one behavior on failure: **fail loudly, preserve the idempotency key, trip the circuit.** No AI-generated payload ever touches a write path — the route classifier enforces this before the request reaches any heal logic, not as a policy the model could be prompted around.

## How a heal actually happens

1. **Route classifier** tags the request `INFORMATIONAL` or `TRANSACTIONAL` before dispatch.
2. **Upstream dispatch** — on a transactional failure, the pipeline short-circuits here: fail loud, trip the circuit, done.
3. **Loop detector** — a fallback target already in this transaction's call stack means it would cycle forever; suppressed instead.
4. **Budget check** — per-transaction and rolling-window heal limits. Either one exhausted trips the circuit hard.
5. **Gemini diagnosis** — live in the request path: the failed payload, the expected schema, and the validation diff go to Gemini with a strict response schema. It returns a drift classification, a heal/fail_loud recommendation, a confidence score, and a field mapping.
6. **Four fail-loud guards**, none of them optional: confidence < 0.85 → fail loud. `drift_type == unrecoverable` → fail loud. Gemini times out (3s) or errors → fail loud. Gemini can *authorize* a heal; nothing it says can force one through.
7. **Heal executor** — pure field remapping only. No invented values. If a required field has no source in the upstream payload, the heal fails.
8. **Validation gate** — deterministic, no AI. The healed payload is re-validated against the expected schema before it can leave the gateway, regardless of what Gemini recommended.
9. **Telemetry inversion** — the caller gets `200` and a set of `X-Autoregent-*` headers (including an HMAC-signed trace). Simultaneously, a signed, queryable event lands in `/events` with the original payload, the healed payload, and Gemini's full reasoning side by side.

## Run the gateway locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in GEMINI_API_KEY
uvicorn app.main:app --reload --port 8000
```

## Endpoints

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | Liveness + per-route circuit states + budget config |
| GET | `/events` | Append-only, HMAC-signed heal-event log (JSON) |
| ANY | `/proxy/{path}` | The gateway itself — classifies, dispatches, heals or fails loud |
| ANY | `/mock/{scenario}` | Flaky mock upstream, informational routes |
| ANY | `/mock/txn/{scenario}` | Same scenarios, mounted where the classifier tags the route TRANSACTIONAL |

Mock scenarios: `healthy`, `field_rename`, `type_change`, `timeout`, `500`, `cascading`.

## See it work

```bash
BASE=https://autoregent-production.up.railway.app   # or http://localhost:8000

# Clean pass
curl $BASE/proxy/mock/healthy

# Schema drift -> Gemini diagnoses it live, heals it, discloses it. Real API call, not mocked.
curl -i $BASE/proxy/mock/field_rename

# Same drift, but the classifier tags this route TRANSACTIONAL -> always fails loud,
# idempotency key preserved, circuit trips on the first failure. No heal pipeline, ever.
curl -i -H "Idempotency-Key: abc-123" $BASE/proxy/mock/txn/field_rename

# Cascading failure -> loop detector suppresses the retry instead of cycling forever
curl $BASE/proxy/mock/cascading

# Hammer a route past its rolling-window budget -> circuit trips OPEN,
# subsequent requests fail fast until the cooldown elapses
for i in $(seq 1 6); do curl -s -o /dev/null -w "%{http_code}\n" $BASE/proxy/mock/type_change; done

curl $BASE/events   # every heal/fail/suppress/trip, signed, with the full call stack
curl $BASE/health   # circuit state per route
```

Logs are structured JSON on stdout.

## Dashboard

A Next.js static-export dashboard (`dashboard/`) polls `/health` and `/events` client-side and renders live circuit state, budget burn, and the event feed — including a divergence-alert banner that fires the instant a new heal lands, and a per-event pipeline diagram showing exactly which stage a request passed or stopped at.

```bash
cd dashboard
npm install
npm run dev   # http://localhost:3000
```

Deploys automatically to GitHub Pages via `.github/workflows/deploy-dashboard.yml` on every push touching `dashboard/`. The gateway URL is switchable at runtime in the dashboard's header (saved to `localStorage`), with one-click presets for local and live.

## Deploy

**Live on Railway.** Connect the repo, set `GEMINI_API_KEY` and `HMAC_SECRET` as service variables, generate a public domain, then set:

```
UPSTREAM_BASE_URL=http://localhost:8080
```

Not the public domain — **localhost**. The mock upstream lives in the same process as the proxy, and several PaaS providers (Railway included) block a container from calling back into its own public domain from inside itself (a "hairpin" request rejected at the edge). Since it's the same process, there's no reason to leave the container at all.

**Cloud Run** was the original target; GCP billing verification failed on the account used for this build (confirmed by the API itself, not just a console glitch), so this documents the intended path rather than what's actually running:

```bash
gcloud auth login
gcloud config set project <your-project-id>
gcloud services enable run.googleapis.com cloudbuild.googleapis.com
gcloud run deploy autoregent-gateway \
  --source . \
  --region asia-south1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=<your-key>,UPSTREAM_BASE_URL=http://localhost:8080
```

## Known limitations (v0.1)

Stated openly rather than discovered by a judge: state is in-memory, so this is single-node and a restart clears event history. The HMAC trace signature proves integrity, not non-repudiation — a real deployment needs asymmetric signing into WORM storage. There's no replay protection on the trace header. Circuit state isn't shared across instances, so horizontal scaling would currently break budget enforcement.

## License

BSD 3-Clause — see [LICENSE](LICENSE).
