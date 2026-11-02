#!/usr/bin/env python3
"""
Multi-Provider AI Client for UUM Circular Document Intelligence
Supports:
1. Google Gemini API (gemini-1.5-flash & text-embedding-004) - Primary
2. Groq Cloud API (llama-3.3-70b-versatile) - High-speed Fallback
3. OpenRouter API (deepseek / llama-3.3 free tier) - Secondary Fallback
"""

import os
import re
import time
import json
import logging
import requests

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s")
logger = logging.getLogger("AIProvider")

def find_root_dir():
    """Find repository root directory containing circular_forms or .git."""
    curr = os.path.dirname(os.path.abspath(__file__))
    while curr and curr != os.path.dirname(curr):
        if os.path.exists(os.path.join(curr, ".git")) or os.path.exists(os.path.join(curr, "circular_forms")):
            return curr
        curr = os.path.dirname(curr)
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def load_env(env_path=None):
    """Load key-value pairs from .env file without external dependencies."""
    if env_path is None:
        root_dir = find_root_dir()
        env_path = os.path.join(root_dir, ".env")
    
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, val = line.split("=", 1)
                    key = key.strip()
                    val = val.strip().strip("\"'")
                    if key not in os.environ:
                        os.environ[key] = val

load_env()

def is_english_query(text):
    """Detect if query is primarily in English."""
    common_en = {
        "what", "how", "when", "where", "who", "which", "can", "is", "are", 
        "the", "for", "and", "requirement", "requirements", "claim", "form", 
        "rules", "procedure", "rate", "speaker", "external", "appoint", "appointment",
        "assistant", "research", "grant", "allowance", "process", "apply", "eligible"
    }
    words = set(re.findall(r"\b[a-zA-Z]+\b", text.lower()))
    return len(words.intersection(common_en)) >= 2 or any(text.lower().startswith(w + " ") for w in ["what", "how", "can", "is", "where", "which", "who", "when"])

class AIProvider:
    def __init__(self):
        self.gemini_key = os.environ.get("GEMINI_API_KEY", "").strip()
        self.groq_key = os.environ.get("GROQ_API_KEY", "").strip()
        self.openrouter_key = os.environ.get("OPENROUTER_API_KEY", "").strip()

    def get_embedding(self, text):
        """Generate 768-dimensional vector embedding using Google Gemini or fallback."""
        text = text.strip()
        if not text:
            return [0.0] * 768

        # 1. Try Gemini embedding models
        if self.gemini_key:
            for model in ["gemini-embedding-001", "text-embedding-004"]:
                try:
                    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:embedContent?key={self.gemini_key}"
                    payload = {
                        "model": f"models/{model}",
                        "outputDimensionality": 768,
                        "content": {"parts": [{"text": text[:2048]}]}
                    }
                    res = requests.post(url, json=payload, timeout=10)
                    if res.status_code == 200:
                        data = res.json()
                        values = data.get("embedding", {}).get("values", [])
                        if values:
                            return values
                except Exception as e:
                    logger.debug(f"Gemini embedding model {model} failed: {e}")

        # Fallback: Deterministic semantic pseudo-vector for local offline development
        return self._generate_fallback_vector(text, dim=768)

    def batch_get_embeddings(self, texts, batch_size=50, delay=4.2):
        """Batch generate 768-dimensional vector embeddings using Google Gemini with rate-limiting."""
        if not texts:
            return []

        if not self.gemini_key:
            return [self._generate_fallback_vector(t, dim=768) for t in texts]

        all_embeddings = []
        total_batches = (len(texts) + batch_size - 1) // batch_size

        for b_idx in range(total_batches):
            start = b_idx * batch_size
            batch = texts[start:start + batch_size]
            batch_reqs = []
            for t in batch:
                batch_reqs.append({
                    "model": "models/gemini-embedding-001",
                    "outputDimensionality": 768,
                    "content": {"parts": [{"text": t[:2048] if t.strip() else "UUM Pekeliling"}]}
                })

            payload = {"requests": batch_reqs}
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-embedding-001:batchEmbedContents?key={self.gemini_key}"

            max_retries = 4
            success = False
            for attempt in range(max_retries):
                try:
                    res = requests.post(url, json=payload, timeout=40)
                    if res.status_code == 200:
                        embs = res.json().get("embeddings", [])
                        for e in embs:
                            all_embeddings.append(e.get("values", []))
                        success = True
                        break
                    elif res.status_code == 429:
                        wait_time = 8 * (attempt + 1)
                        logger.warning(f"Rate limited (429) on batch {b_idx + 1}/{total_batches}. Waiting {wait_time}s before retry...")
                        time.sleep(wait_time)
                    else:
                        logger.warning(f"Batch embedding error {res.status_code}: {res.text[:120]}")
                        break
                except Exception as e:
                    logger.warning(f"Batch embedding attempt {attempt + 1} failed: {e}")
                    time.sleep(3)

            if not success:
                logger.warning(f"Using fallback vectors for batch {b_idx + 1}")
                for t in batch:
                    all_embeddings.append(self._generate_fallback_vector(t, dim=768))

            if delay > 0 and b_idx + 1 < total_batches:
                time.sleep(delay)

        return all_embeddings

    def _generate_fallback_vector(self, text, dim=768):
        """Creates a normalized pseudo-hash vector for offline development when no API key is present."""
        import hashlib
        import math
        vec = []
        for i in range(dim):
            h = hashlib.sha256(f"{text}_{i}".encode("utf-8")).hexdigest()
            val = (int(h[:6], 16) / 0xFFFFFF) * 2 - 1
            vec.append(val)
        norm = math.sqrt(sum(x * x for x in vec)) or 1.0
        return [x / norm for x in vec]

    def generate_chat_response(self, user_query, retrieved_chunks, system_prompt=None):
        """Generate response with primary provider and automatic failover."""
        is_en = is_english_query(user_query)

        context_blocks = []
        for idx, chk in enumerate(retrieved_chunks, 1):
            ref = chk.get("circular_ref_no", "UUM Circular")
            dept = chk.get("department", "UUM")
            page = chk.get("page_number", "N/A")
            heading = chk.get("section_heading", "Clause")
            body = chk.get("chunk_text", "")
            forms = chk.get("required_forms", "-")
            context_blocks.append(
                f"[Source {idx}]: {ref} ({dept}) | Section: {heading} | Page: {page}\n"
                f"Required Forms: {forms}\n"
                f"Excerpt: {body}\n"
            )
        context_str = "\n".join(context_blocks)

        if is_en:
            default_system = (
                "You are the official UUM Circular & Project Document Intelligence Assistant (Universiti Utara Malaysia).\n"
                "Your role is to assist UUM staff, faculty members, and researchers with administrative, financial, research, and legal regulations.\n"
                "CRITICAL MANDATORY INSTRUCTIONS:\n"
                "1. LANGUAGE REQUIREMENT: The user has asked their question in ENGLISH. You MUST provide your entire response in 100% fluent, professional ENGLISH.\n"
                "   Translate procedures, eligibility criteria, and rules accurately into English, while preserving official Malaysian circular titles, reference numbers, and form codes in their official names (e.g., 'Pekeliling Bendahari Bil. 8/2025', 'Borang RMC 008', 'KEW.PA-1').\n"
                "2. PROCEDURAL WORKFLOW: Provide a clear Step-by-Step Procedure Workflow.\n"
                "3. MANDATORY FORMS CHECKLIST: Explicitly list all required official forms and templates.\n"
                "4. EXACT CITATIONS: You MUST cite the Circular Reference Number, issuing department (PTJ), and exact page number/section for every rule mentioned.\n"
                "5. FACTUAL INTEGRITY: Base your answer strictly on the provided official sources. If information is not covered, state clearly that no specific circular was found in the database and recommend contacting the responsible PTJ."
            )
            context_header = "=== OFFICIAL UUM CIRCULAR SOURCES ==="
            query_header = "=== USER QUESTION ==="
            response_header = "=== COMPREHENSIVE ANSWER & CHECKLIST ==="
        else:
            default_system = (
                "Anda ialah Pembantu Pintar Pekeliling dan Dokumen Projek Universiti Utara Malaysia (UUM Circular Intelligence Assistant).\n"
                "Tugas anda adalah membantu staf, pensyarah, dan penyelidik UUM memahami peraturan pentadbiran, kewangan, penyelidikan, dan perundangan.\n"
                "ARAHAN KETAT:\n"
                "1. KEPERLUAN BAHASA: Pengguna telah bertanya dalam BAHASA MELAYU. Anda WAJIB menjawab keseluruhan respon dalam Bahasa Melayu yang rasmi dan tepat.\n"
                "2. Jawab soalan secara terperinci berdasarkan Sumber Rujukan yang diberikan.\n"
                "3. Nyatakan Senarai Semak Prosedur (Step-by-step workflow) dan Senarai Borang Wajib yang diperlukan secara jelas.\n"
                "4. WAJIB sertakan petikan tepat (Citations) merangkumi: Nombor Rujukan Pekeliling, Pusat Tanggungjawab (PTJ), dan nombor muka surat/seksyen.\n"
                "5. Jika tiada pekeliling yang berkaitan dalam sumber, nyatakan secara jujur bahawa tiada pekeliling rasmi ditemui dan sarankan pegawai PTJ berkenaan untuk dihubungi."
            )
            context_header = "=== SUMBER RUJUKAN RASMI UUM ==="
            query_header = "=== SOALAN PENGGUNA ==="
            response_header = "=== JAWAPAN & SENARAI SEMAK LENGKAP ==="

        sys_instruction = system_prompt or default_system

        full_prompt = (
            f"{sys_instruction}\n\n"
            f"{context_header}\n"
            f"{context_str}\n\n"
            f"{query_header}\n"
            f"{user_query}\n\n"
            f"{response_header}"
        )

        # 1. Try Gemini
        if self.gemini_key:
            res_text = self._call_gemini(full_prompt)
            if res_text:
                return res_text, "Google Gemini Flash"

        # 2. Try Groq (Llama 3.3 70B)
        if self.groq_key:
            res_text = self._call_groq(sys_instruction, full_prompt)
            if res_text:
                return res_text, "Groq Cloud (llama-3.3-70b-versatile)"

        # 3. Try OpenRouter
        if self.openrouter_key:
            res_text = self._call_openrouter(sys_instruction, full_prompt)
            if res_text:
                return res_text, "OpenRouter (meta-llama/llama-3.3-70b)"

        # 4. Fallback Extractive Synthesizer (when no API key configured yet)
        return self._extractive_fallback(user_query, retrieved_chunks)

    def _call_gemini(self, prompt):
        models = [
            "gemini-2.5-flash",
            "gemini-1.5-flash",
            "gemini-3.5-flash-lite",
            "gemini-3.5-flash",
            "gemini-3.8-flash",
            "gemini-flash-latest",
        ]
        for model in models:
            try:
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={self.gemini_key}"
                payload = {
                    "contents": [{"parts": [{"text": prompt}]}],
                    "generationConfig": {"temperature": 0.2, "maxOutputTokens": 2048}
                }
                res = requests.post(url, json=payload, timeout=30)
                if res.status_code == 200:
                    data = res.json()
                    candidates = data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("content", {}).get("parts", [])
                        if parts:
                            return parts[0].get("text", "")
                elif res.status_code == 404:
                    continue  # Try next model in sequence
                else:
                    logger.warning(f"Gemini API ({model}) status {res.status_code}: {res.text[:120]}")
            except Exception as e:
                logger.warning(f"Gemini call to {model} failed: {e}")
        return None

    def _call_groq(self, system_prompt, user_content):
        try:
            url = "https://api.groq.com/openai/v1/chat/completions"
            headers = {"Authorization": f"Bearer {self.groq_key}", "Content-Type": "application/json"}
            payload = {
                "model": "llama-3.3-70b-versatile",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                "temperature": 0.2,
                "max_tokens": 2048
            }
            res = requests.post(url, json=payload, headers=headers, timeout=25)
            if res.status_code == 200:
                data = res.json()
                return data["choices"][0]["message"]["content"]
            else:
                logger.warning(f"Groq API returned status {res.status_code}: {res.text[:120]}")
        except Exception as e:
            logger.warning(f"Groq call failed: {e}")
        return None

    def _call_openrouter(self, system_prompt, user_content):
        try:
            url = "https://openrouter.ai/api/v1/chat/completions"
            headers = {"Authorization": f"Bearer {self.openrouter_key}", "Content-Type": "application/json"}
            payload = {
                "model": "google/gemini-2.0-flash-exp:free",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content}
                ],
                "temperature": 0.2
            }
            res = requests.post(url, json=payload, headers=headers, timeout=25)
            if res.status_code == 200:
                data = res.json()
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            logger.warning(f"OpenRouter call failed: {e}")
        return None

    def _extractive_fallback(self, query, chunks):
        """Structured extractive answer when no external AI API key is configured in .env."""
        is_en = is_english_query(query)
        if is_en:
            lines = [
                "### 📋 UUM Circular & Form Summary (Extractive Index Mode)",
                "",
                "> **Note**: For full automatic AI answer synthesis, please ensure your `GEMINI_API_KEY` or `GROQ_API_KEY` is configured in `.env`.",
                "",
                "Based on the UUM Circular & Form database, here are the most relevant references for your query:",
                ""
            ]
            for idx, chk in enumerate(chunks, 1):
                ref = chk.get("circular_ref_no", "UUM Circular")
                dept = chk.get("department", "UUM")
                heading = chk.get("section_heading", "Clause")
                page = chk.get("page_number", "1")
                text = chk.get("chunk_text", "").strip()
                forms = chk.get("required_forms", "-")

                lines.append(f"#### {idx}. {ref} ({dept})")
                lines.append(f"- **Section / Title**: {heading}")
                lines.append(f"- **Page Number**: {page}")
                if forms and forms != "-":
                    lines.append(f"- **Related Forms**: `{forms}`")
                lines.append(f"- **Circular Excerpt**: *\"{text[:250]}...\"*")
                lines.append("")
        else:
            lines = [
                "### 📋 Ringkasan Maklumat Pekeliling & Borang UUM (Extractive Index Mode)",
                "",
                "> **Perhatian**: Untuk sintesis jawapan automatik penuh menggunakan LLM, sila masukkan `GEMINI_API_KEY` atau `GROQ_API_KEY` ke dalam fail `.env` anda.",
                "",
                "Berdasarkan pangkalan data Pekeliling dan Borang UUM, berikut ialah rujukan yang paling relevan bagi carian anda:",
                ""
            ]
            for idx, chk in enumerate(chunks, 1):
                ref = chk.get("circular_ref_no", "UUM Circular")
                dept = chk.get("department", "UUM")
                heading = chk.get("section_heading", "Clause")
                page = chk.get("page_number", "1")
                text = chk.get("chunk_text", "").strip()
                forms = chk.get("required_forms", "-")

                lines.append(f"#### {idx}. {ref} ({dept})")
                lines.append(f"- **Seksyen/Tajuk**: {heading}")
                lines.append(f"- **Muka Surat**: {page}")
                if forms and forms != "-":
                    lines.append(f"- **Borang Berkaitan**: `{forms}`")
                lines.append(f"- **Petikan Pekeliling**: *\"{text[:250]}...\"*")
                lines.append("")

        return "\n".join(lines), "Offline Extractive Engine"

