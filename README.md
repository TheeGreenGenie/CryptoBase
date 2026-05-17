# CryptoBase

Flask + HTMX + Web3 MVP for testnet lending, trading, risk monitoring, and human-approved agent suggestions.

## Prerequisites

- Python 3.11+
- [Foundry](https://book.getfoundry.sh/getting-started/installation) (includes `anvil` and `forge`)
- Redis (for Celery background tasks; optional for basic dev use)
- MetaMask or any EIP-1193 compatible browser wallet

## Local Setup

```powershell
python -m venv .MidnightVenv
.\.MidnightVenv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
```

Edit `.env` and set `SECRET_KEY` to a random string. Leave the rest as defaults for local Anvil development.

### Run database migrations

```powershell
flask --app run.py db upgrade
```

### Start the app

```powershell
flask --app run.py run --debug
```

Open `http://127.0.0.1:5000`.

## Full Local Demo

Run these in separate terminals:

**Terminal 1 — local chain:**

```powershell
anvil --state chainstate.json
```

The `--state` flag saves chain state to `chainstate.json` on shutdown and reloads it on next startup, so your balances survive restarts.

**Terminal 2 — deploy contracts:**

```powershell
.\.MidnightVenv\Scripts\Activate.ps1
forge --root contracts build
forge script contracts/script/Deploy.s.sol --rpc-url http://127.0.0.1:8545 --broadcast
python scripts/sync_contract_abis.py
```

Copy the printed contract addresses into `.env`:

```env
LENDING_POOL_ADDRESS=0x...
WBTC_TOKEN_ADDRESS=0x...
DEBT_TOKEN_ADDRESS=0x...
PRICE_ORACLE_ADDRESS=0x...
```

**Terminal 3 — Redis (if installed):**

```powershell
redis-server
```

**Terminal 4 — Celery worker (optional):**

```powershell
.\.MidnightVenv\Scripts\Activate.ps1
celery -A celery_worker.celery worker --loglevel=info
```

**Terminal 5 — Flask:**

```powershell
.\.MidnightVenv\Scripts\Activate.ps1
flask --app run.py run --debug
```

### MetaMask setup

1. Add a custom network: RPC `http://127.0.0.1:8545`, Chain ID `31337`.
2. Import one of the Anvil dev accounts using its private key (printed by `anvil` on startup).
3. Open `http://127.0.0.1:5000/auth/connect` and click **Connect MetaMask**.

## Contract Tests

```powershell
forge --root contracts test -v
```

All 8 lending invariant tests must pass before running the demo.

## Python Tests

```powershell
pytest
```

## Code Quality

```powershell
ruff check .
black .
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `FLASK_ENV` | `development` | `development`, `testing`, or `production` |
| `SECRET_KEY` | `dev-only-change-me` | Flask session secret — change for production |
| `DATABASE_URL` | SQLite in `instance/` | Database connection string |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis for Celery |
| `CHAIN_ID` | `31337` | EVM chain ID |
| `RPC_URL` | `http://127.0.0.1:8545` | JSON-RPC endpoint |
| `LENDING_POOL_ADDRESS` | — | Deployed LendingPool address |
| `WBTC_TOKEN_ADDRESS` | — | Deployed mock WBTC collateral token address |
| `DEBT_TOKEN_ADDRESS` | — | Deployed mUSDC debt token address |
| `PRICE_ORACLE_ADDRESS` | — | Deployed price oracle address |
| `LLM_PROVIDER` | `none` | `none`, `openai`, `grok`, or `qwen` |
| `OPENAI_API_KEY` | — | OpenAI key (required when `LLM_PROVIDER=openai`) |
| `GROK_API_KEY` | — | xAI Grok key (required when `LLM_PROVIDER=grok`) |
| `QWEN_BASE_URL` | `http://localhost:11434/v1` | Ollama base URL (required when `LLM_PROVIDER=qwen`) |
| `QWEN_MODEL` | `qwen2.5:7b` | Ollama model name |
| `FAUCET_PRIVATE_KEY` | — | Anvil account 0 private key for dev token minting — never use a real key |
| `FAUCET_AMOUNT` | `10000` | Token amount to mint per faucet request |
| `API_RATE_LIMIT` | `60/minute` | Flask-Limiter rate limit string |

Never commit `.env` or real API keys.

## LLM Providers

Agent suggestions work without an LLM (`LLM_PROVIDER=none` uses rule-based suggestions only). To enable AI-generated suggestions, set one of:

**Local Ollama (free, no API key):**
```env
LLM_PROVIDER=qwen
QWEN_BASE_URL=http://localhost:11434/v1
QWEN_MODEL=qwen2.5:7b
```
Install [Ollama](https://ollama.com), then run `ollama pull qwen2.5:7b`. First response takes 30–60 s while the model loads.

**OpenAI:**
```env
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
```

**xAI Grok:**
```env
LLM_PROVIDER=grok
GROK_API_KEY=xai-...
```

## Testnet Deployment (Sepolia / Base Sepolia)

1. Set `CHAIN_ID` and `RPC_URL` in `.env` to the target testnet.
2. Fund a deployer EOA with testnet ETH from a faucet.
3. Deploy contracts:

```bash
forge script contracts/script/Deploy.s.sol \
  --rpc-url $RPC_URL \
  --private-key $DEPLOYER_PRIVATE_KEY \
  --broadcast \
  --verify
```

4. Copy the printed contract addresses into `.env`.
5. Run `python scripts/sync_contract_abis.py` to copy ABI files.
6. Deploy the Flask app (see Render/Fly.io below) with the updated `.env` variables.

## Production Deployment

### Render

1. Create a new **Web Service** pointing to this repo.
2. Build command: `pip install -r requirements.txt && flask --app run.py db upgrade`
3. Start command: `gunicorn run:app --workers 2 --bind 0.0.0.0:$PORT --timeout 30`
4. Add a **Redis** add-on and set `REDIS_URL`.
5. Set all required environment variables in the Render dashboard.
6. Set `FLASK_ENV=production` and `SECRET_KEY` to a secure random value.

Optional: add a **Background Worker** with the command `celery -A celery_worker.celery worker --loglevel=info`.

### Fly.io

```bash
fly launch
fly secrets set SECRET_KEY=<random> FLASK_ENV=production DATABASE_URL=<postgres-url> REDIS_URL=<redis-url>
fly deploy
```

Use `fly.toml` to configure the `[processes]` section for both `web` and `worker` if running Celery.

## Partner API MVP

The API is sandbox/testnet-only for early company integrations.

Base URLs:

- Local: `http://127.0.0.1:5000/api/v1`
- Testnet: `<deployed-url>/api/v1`

**Authentication:**

```http
X-API-Key: <your-api-key>
```

Generate an API key from the Agent page after signing in, or via:

```http
POST /api/v1/api-keys
```
(requires wallet session auth)

**Supported scopes:**

| Scope | Description |
|---|---|
| `read:positions` | Read wallet positions |
| `read:risk` | Read health factor and risk class |
| `read:opportunities` | Read yield opportunities |
| `write:actions` | Build unsigned action transactions |

**Endpoints:**

| Method | Path | Scope |
|---|---|---|
| `GET` | `/health` | none |
| `GET` | `/positions` | `read:positions` |
| `GET` | `/risk` | `read:risk` |
| `GET` | `/yield-opportunities` | `read:opportunities` |
| `POST` | `/actions/build` | `write:actions` |
| `POST` | `/api-keys` | wallet session |
| `GET` | `/api-keys` | wallet session |
| `DELETE` | `/api-keys/<id>` | wallet session |

**Example (PowerShell):**

```powershell
Invoke-RestMethod `
  -Uri http://127.0.0.1:5000/api/v1/risk `
  -Headers @{ "X-API-Key" = "<your-key>" }
```

**Response envelope:**

```json
{ "ok": true, "data": {}, "error": null }
```

**Standard error codes:**

| Code | Meaning |
|---|---|
| `unauthorized` | Missing, invalid, or revoked API key |
| `forbidden` | Valid key, insufficient scope |
| `rate_limited` | Rate limit exceeded |
| `validation_error` | Bad request body or parameters |
| `unsupported_chain` | Chain not configured |
| `unsupported_asset` | Token not supported |
| `quote_unavailable` | Cannot produce a trading quote |
| `internal_error` | Unexpected server error |

**Safety note:** All transaction-building endpoints return **unsigned** payloads. User wallets must sign all user-fund transactions. The backend never holds private keys.

## Midnight Privacy Layer

CryptoBase uses the [Midnight network](https://midnight.network) to keep sensitive financial data — collateral amounts, debt amounts, and health factors — hidden from the public ledger while remaining mathematically verifiable.

### How it works

1. **Commitment** — when your position is attested, your collateral and debt USD values are hashed with a secret salt: `SHA-256(amount || salt)`. The raw amounts cannot be recovered from the hash.
2. **Zero-knowledge circuit** — the `attest_health` circuit in `contracts/midnight/private_lending.compact` proves your position is overcollateralized (`collateral ≥ 150% of debt`) inside a ZK proof without broadcasting the values.
3. **Public attestation** — the Midnight network records only the proof hash, the overcollateralization result (`yes/no`), and the risk class (`healthy/watch/danger/liquidatable`). No amounts on chain.

### What's hidden

| Data | Visibility |
|---|---|
| Collateral amount (USD) | Hidden — commitment hash only |
| Debt amount (USD) | Hidden — commitment hash only |
| Health factor (exact value) | Hidden — risk class only |
| Risk class | Public (Healthy / Watch / Danger / Liquidatable) |
| Overcollateralized | Public (Yes / No) |
| ZK proof hash | Public (verifiable on Midnight chain) |

### Pages

| URL | Description |
|---|---|
| `/privacy` | Your privacy dashboard — attestation status, commitment hashes, proof hash |
| `/privacy/attest` | Re-attest current position (POST, login required) |
| `/privacy/verify/<wallet>` | Public verifier — shows risk class and proof hash for any wallet |

### Modes

- **Midnight Testnet** — set `MIDNIGHT_RPC_URL` to your Midnight node endpoint. Attestations are pushed on-chain.
- **Local Demo** — leave `MIDNIGHT_RPC_URL` empty. Commitments are computed locally, attestations are derived in-memory. All privacy properties are demonstrated without a live Midnight node.

### Configuration

```env
MIDNIGHT_RPC_URL=                 # Midnight node RPC endpoint (empty = local demo mode)
MIDNIGHT_CONTRACT_ADDRESS=        # Deployed private_lending.compact address
```

### Compact contract

The Midnight smart contract is at [`contracts/midnight/private_lending.compact`](contracts/midnight/private_lending.compact). It defines:
- `private_positions` — private ledger (owner-only): commitment hashes per wallet
- `public_attestations` — public ledger: risk class and proof hash per wallet
- `attest_health` — ZK circuit that proves overcollateralization without revealing amounts
- `revoke_attestation` — clears private and public records when a position is closed

## Troubleshooting

| Symptom | Fix |
|---|---|
| `forge` not found | Install Foundry and ensure `~/.foundry/bin` is in `PATH` |
| `anvil` not found | Same as above |
| CSRF error on form submit | Clear cookies and re-sign in; check `SECRET_KEY` is set |
| Contract address not set | Run deploy script and copy addresses into `.env` |
| Celery tasks not running | Start `redis-server` and the Celery worker |
| Wallet signature fails | Make sure MetaMask chain matches `CHAIN_ID` in `.env` |
