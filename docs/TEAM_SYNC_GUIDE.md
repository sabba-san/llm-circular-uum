# Teammate & Friend Sync Guide: Upgrading to LLM UUM (689 Documents & 3-Pane UI)

If your teammate or friend is seeing the old **"UUM Consensus"** single-page search screen with only **249 circulars/forms** (Image 1), follow this simple 1-click guide to upgrade their machine to the official **LLM UUM 3-Pane AI Copilot Platform** with **689 documents** and live PDF inspection (Image 2).

---

## 🔍 Why the Friend's Screen Was Different

| Problem on Friend's Laptop | Root Cause | Fix |
|---|---|---|
| Screen says `UUM Consensus` instead of `LLM UUM` | Friend is on an older git commit or branch | `git pull origin main` |
| Screen shows only `175 Circulars / 74 Forms` (249 total) | Local database `data/uum_knowledge.db` was created before college documents were added | `python3 ingest.py` updates to **689 documents** |
| Single-page search bar without 3-pane chat or PDF viewer | Old template loaded from browser cache or old container | Rebuild container with `--build` or restart `uvicorn` |

---

## 🚀 1-Click Upgrade Instructions

### Option A: Running via Docker Desktop (Recommended)

Run these 3 commands inside the project folder:

```bash
# 1. Fetch the latest code from GitHub
git pull origin main

# 2. Stop any existing containers
docker compose down

# 3. Rebuild and launch the updated container
docker compose up -d --build
```

> **Note:** The updated `docker-entrypoint.sh` automatically detects if the database is missing the college documents and runs ingestion automatically!

Open your browser to:
👉 **`http://localhost:8000`**

---

### Option B: Running via Native Python (Virtual Environment)

If running without Docker:

```bash
# 1. Fetch latest code
git pull origin main

# 2. Activate virtual environment
source venv/bin/activate       # On Linux/macOS
# or: venv\Scripts\activate   # On Windows PowerShell

# 3. Ingest the full 689-document catalog (takes ~5 seconds with cache)
python3 ingest.py

# 4. Launch the web server
python3 -m uvicorn web_app:app --host 0.0.0.0 --port 8000 --reload
```

Open your browser to:
👉 **`http://localhost:8000`**

---

## ✅ Post-Upgrade Verification Checklist

Once loaded, confirm the following indicators appear:

1. **Brand Title (Top Left):** `LLM UUM — Academic & Policy Intelligence`
2. **Document Library Badge (Sidebar):** Shows **`689`** documents (includes CAS, COB, COLGIS, HEA, and PTJs).
3. **Layout:** **3-Pane Copilot Interface** (Left Sidebar + Center AI Synthesis + Right PDF Reference Viewer).
4. **Interactive Features:** Click any reference citation (e.g. `[Source 3 - p.1]`) to verify the PDF Inspector opens directly to the exact cited page in the right pane.

