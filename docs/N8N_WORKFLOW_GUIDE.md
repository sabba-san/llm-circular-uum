# Phase 5: n8n Chat Webhook Workflow Guide

This guide explains how to launch, import, activate, and test the **UUM Document Intelligence — Hybrid RAG Chat Webhook** in `n8n` (Proposal Phase 5).

---

## Step 1: Start Both Containers (`llm-uum` + `n8n`)
From your WSL2 terminal inside `/home/abbas/llm_uum`:
```bash
docker compose up -d
```
- **LLM UUM Web App**: `http://localhost:8000`
- **n8n Visual Workflow UI**: `http://localhost:5678`

---

## Step 2: Import the Workflow
### Option A — 1-Command CLI Import & Publish (Fastest)
```bash
docker exec llm_uum_n8n n8n import:workflow --input=/home/node/workflows/llm_uum_chat_webhook_workflow.json
docker exec llm_uum_n8n n8n publish:workflow --id=RlW9NCFZLsGQYvtd
docker restart llm_uum_n8n
```

### Option B — Import via n8n Web UI
1. Open `http://localhost:5678` in your browser (complete the local owner setup once if prompted).
2. Click **Create Workflow** (or **Workflows** → **Add Workflow**).
3. Click the **`...`** menu (top-right) → **Import from File...**
4. Select `n8n/llm_uum_chat_webhook_workflow.json`.

---

## Step 3: Activate & Test the Workflow
1. Open **UUM Document Intelligence — Hybrid RAG Chat Webhook** in the n8n canvas.
2. Toggle the **Active** switch (top-right) to **ON** (green) so the production webhook `/webhook/uum-chat` listens continuously.
3. Run a test request from your terminal:
```bash
curl -s -X POST http://localhost:5678/webhook/uum-chat \
  -H "Content-Type: application/json" \
  -d '{"query":"Apakah syarat lantikan GRA di bawah geran penyelidikan?","scope":"RMC","filter_active":true}' | python3 -m json.tool
```

Or test interactively in the n8n editor:
- Click **Test workflow** (listen on `/webhook-test/uum-chat`) and send a `POST` to `http://localhost:5678/webhook-test/uum-chat` — all 5 nodes will turn green and display the JSON output.

---

## Step 4: Screenshots for Your Phase 5 Final Report
Capture these 3 screenshots for your Industrial Training Report:
1. **Visual Workflow Canvas** (`http://localhost:5678`): Showing the 5 connected nodes (`Webhook` → `Prepare RAG Payload` → `Query LLM UUM RAG` → `Format Citations & Forms` → `Respond to Webhook`) in green executed state.
2. **Execution Log / Output JSON**: Showing the grounded answer, `citations` with PDF preview URLs, `linked_forms`, and `follow_up_questions`.
3. **Terminal IR Evaluation Table**: Output from `./venv/bin/python3 eval/run_ir_eval.py` showing `MRR@5 = 0.9120` and the `40:60` ablation sweep.
