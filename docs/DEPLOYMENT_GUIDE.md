# QuantOS — Online Deployment & 24/7 Hosting Guide

This guide provides complete, production-tested instructions for deploying **QuantOS** online, with special focus on **100% free**, **no-credit-card**, and **24/7 continuous operation** options.

---

## 📑 Table of Contents

1. [System Architecture & Deployment Footprint](#1-system-architecture--deployment-footprint)
2. [Comparison Matrix of Free 24/7 Options](#2-comparison-matrix-of-free-247-options)
3. [Option A: Hugging Face Spaces (Top Free Cloud — 16 GB RAM)](#3-option-a-hugging-face-spaces-top-free-cloud--16-gb-ram)
4. [Option B: Local PC + Cloudflare Tunnel (Top Free Storage & Privacy)](#4-option-b-local-pc--cloudflare-tunnel-top-free-storage--privacy)
5. [Option C: Oracle Cloud Always Free VPS (Top Dedicated Cloud Server)](#5-option-c-oracle-cloud-always-free-vps-top-dedicated-cloud-server)
6. [Option D: Render & Railway PaaS](#6-option-d-render--railway-paas)
7. [Option E: Headless Scheduled Automation (GitHub Actions)](#7-option-e-headless-scheduled-automation-github-actions)
8. [Understanding Ephemeral Storage & How to Persist Data](#8-understanding-ephemeral-storage--how-to-persist-data)
9. [Environment Variables & Security](#9-environment-variables--security)

---

## 1. System Architecture & Deployment Footprint

QuantOS is designed as a modular Python service containing:
* **FastAPI Backend & Interactive UI**: Serves REST endpoints (`/api/*`) and static web assets at [`src/quant_system/server/`](file:///d:/quant_system/src/quant_system/server/).
* **In-Memory Analytical Engine**: Event-driven backtesting, Black-Scholes Greeks, Monte Carlo simulators, Markowitz/Risk-Parity optimization.
* **Storage Invariants**: Double-entry Decimal ledger and content-addressed evidence store. No heavy external SQL/NoSQL database server is mandatory for basic operations.

---

## 2. Comparison Matrix of Free 24/7 Options

| Platform | Cost | Credit Card Needed? | Compute Specs | Ephemeral Disk? | 24/7 Strategy | Best Use Case |
|---|:---:|:---:|---|:---:|---|---|
| **Hugging Face Spaces** | **$0** | ❌ **No** | **2 vCPU, 16 GB RAM** | ⚠️ Yes (Resets on rebuild) | **UptimeRobot ping every 5 min** | Heavy backtesting, ML models, public/private Web UI |
| **Local PC + Cloudflare Tunnel** | **$0** | ❌ **No** | **Unlimited (Your PC)** | ❌ No (Persistent local SSD) | **Keep PC powered on** | Permanent historical datasets, absolute privacy |
| **Oracle Cloud Always Free** | **$0** | ⚠️ Yes (Identity check) | **4 ARM vCPU, 24 GB RAM, 200 GB SSD** | ❌ No (Dedicated VPS Disk) | **Native 24/7/365 VPS** | Complete 24/7 automated quant operations + Cron |
| **Render Free Tier** | **$0** | ❌ **No** | 0.1 vCPU, 512 MB RAM | ⚠️ Yes | UptimeRobot ping (max 750 free hrs/mo) | Simple web demo / lightweight API |
| **GitHub Actions** | **$0** | ❌ **No** | 2-core Azure VM | ⚠️ Ephemeral runners | Scheduled Cron (`00:00` & `10:30 UTC`) | Daily data sync, model retraining, tearsheets |

---

## 3. Option A: Hugging Face Spaces (Top Free Cloud — 16 GB RAM)

**Why choose this:** Highest free RAM tier (16 GB), zero credit card requirement, Docker support, and automatic HTTPS.

### Step 1: Create a Space
1. Sign up at [huggingface.co](https://huggingface.co/).
2. Create a **New Space**:
   * **Space SDK**: `Docker` $\rightarrow$ `Blank`
   * **Space Hardware**: `CPU basic • 2 vCPU • 16 GB RAM • Free`
   * **Visibility**: `Public` or `Private` (both free)

### Step 2: Use the Root `Dockerfile`
QuantOS includes a deployment-ready [`Dockerfile`](file:///d:/quant_system/Dockerfile) in the repository root:
```dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY src/ ./src/

RUN pip install --no-cache-dir -e .

EXPOSE 7860

CMD ["uvicorn", "quant_system.server.app:app", "--host", "0.0.0.0", "--port", "7860"]
```

### Step 3: Deploy via Git
```bash
git remote add hf https://huggingface.co/spaces/<YOUR_USERNAME>/quant-system
git push hf main
```

### Step 4: Configure 24/7 Keepalive Ping
To prevent Hugging Face from pausing after 48 hours of idle time:
1. Open [UptimeRobot.com](https://uptimerobot.com) (Free, no credit card).
2. Add an **HTTP(s) Monitor**:
   * **URL**: `https://<YOUR_USERNAME>-quant-system.hf.space/api/version`
   * **Interval**: `5 minutes`
3. Save monitor. The space will remain awake 24/7/365.

---

## 4. Option B: Local PC + Cloudflare Tunnel (Top Free Storage & Privacy)

**Why choose this:** Uses your computer's full CPU/RAM and NVMe SSD. All historical market data, logs, and backtest files are saved locally and permanently with zero data loss.

### Step 1: Run QuantOS Locally
```powershell
uv run python -m uvicorn quant_system.server.app:app --host 127.0.0.1 --port 8000
```

### Step 2: Install Cloudflare Tunnel Client
Download [`cloudflared.exe`](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) and place it in your system PATH or working folder.

### Step 3: Launch Instant Public HTTPS Tunnel
```powershell
cloudflared tunnel --url http://127.0.0.1:8000
```
Cloudflare will output a secure public URL (e.g. `https://random-subdomain.trycloudflare.com`) giving instant global access to your local QuantOS dashboard.

---

## 5. Option C: Oracle Cloud Always Free VPS (Top Dedicated Cloud Server)

**Why choose this:** Provides a dedicated Ubuntu Linux cloud server with 24 GB RAM, 4 CPU cores, and 200 GB SSD storage running 24/7 without idle timeouts.

### Step 1: Provision Instance
1. Register at [oracle.com/cloud/free](https://www.oracle.com/cloud/free/).
2. Create an **Ampere A1 (ARM64)** or **AMD (x86)** Compute Instance running **Ubuntu 24.04 LTS**.

### Step 2: Configure System Service
Connect via SSH and install dependencies:
```bash
sudo apt update && sudo apt install -y python3-pip python3-venv git
git clone https://github.com/uninestindia-crypto/quant-system.git /opt/quant-system
cd /opt/quant-system
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Create a systemd unit `/etc/systemd/system/quantos.service`:
```ini
[Unit]
Description=QuantOS Institutional Server
After=network.target

[Service]
User=ubuntu
WorkingDirectory=/opt/quant-system
ExecStart=/opt/quant-system/.venv/bin/uvicorn quant_system.server.app:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now quantos
```

---

## 6. Option D: Render & Railway PaaS

### Render Free Web Service
* **Build Command**: `pip install -e .`
* **Start Command**: `uvicorn quant_system.server.app:app --host 0.0.0.0 --port $PORT`
* **Keepalive**: Ping `/api/version` via UptimeRobot every 5 minutes (max 750 free hours/month).

---

## 7. Option E: Headless Scheduled Automation (GitHub Actions)

If you only need automated daily quant workflows (data sync, feature engineering, model training, paper backtests, and tearsheet generation):

Create `.github/workflows/daily_pipeline.yml`:
```yaml
name: Daily QuantOS Pipeline & Training

on:
  schedule:
    - cron: '30 10 * * 1-5' # 16:00 IST (Post-market close Mon-Fri)
  workflow_dispatch:

jobs:
  run-pipeline:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout Code
        uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v3
        with:
          version: "latest"

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: uv sync --frozen --extra dev

      - name: Execute Daily Pipeline
        run: |
          uv run python scripts/daily_pipeline.py --days 252 --universe INFY TCS RELIANCE HDFCBANK ICICIBANK

      - name: Upload Daily Tearsheets & Artifacts
        uses: actions/upload-artifact@v4
        with:
          name: daily-quantos-reports-${{ github.sha }}
          path: |
            reports/
            logs/
```

---

## 8. Understanding Ephemeral Storage & How to Persist Data

### The Container Ephemerality Lifecycle
On container platforms (Hugging Face Spaces, Render), restarting or redeploying the container restores the disk to its initial built state.

```
[ Git Push / Deploy ] ──► [ Build Container Image ]
                                 │
                                 ▼
                         [ Active Runtime ] (Generates temp files in data/ logs/)
                                 │
                         (Restart / Redeploy)
                                 │
                                 ▼
                         [ Fresh Container ] (Runtime-generated temp files wiped)
```

### Persistence Strategies:

1. **Commit Historical Baselines to Git**:
   Place standard price history CSVs in [`data/`](file:///d:/quant_system/data). Since they are tracked in Git, they are baked into the container build and survive every restart.
2. **Cloudflare R2 Object Storage (10 GB Free Forever, $0 Egress)**:
   Sync pipeline artifacts and datasets to an S3-compatible R2 bucket at the end of each daily pipeline execution.
3. **Local Deployment**:
   Use Local PC + Cloudflare Tunnel to store everything directly on your NVMe SSD.

---

## 9. Environment Variables & Security

When connecting to external APIs (e.g. Upstox V3 Market Data), configure variables in your hosting dashboard:

```bash
# Upstox API V3 Authentication
UPSTOX_ACCESS_TOKEN="your_token_here"
UPSTOX_API_KEY="your_api_key"

# Environment Mode
QUANTOS_ENV="production"
PORT="7860" # Default for Hugging Face Spaces (or 8000 for standard)
```

> [!WARNING]
> Never commit `.env` files or API secrets to public Git repositories or Spaces. Use the platform's native Secret / Environment Variable settings.
