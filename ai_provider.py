#!/usr/bin/env python3
"""
Backward-compatible wrapper for ai_provider.
The canonical multi-provider AI client is located at src/ai_provider.py.
"""

from src.ai_provider import AIProvider, load_env, find_root_dir

__all__ = ["AIProvider", "load_env", "find_root_dir"]

if __name__ == "__main__":
    ai = AIProvider()
    print("Testing AI Provider configuration...")
    print("Gemini API Key configured:", bool(ai.gemini_key))
    print("Groq API Key configured:", bool(ai.groq_key))
    print("OpenRouter Key configured:", bool(ai.openrouter_key))
    emb = ai.get_embedding("Pekeliling Bendahari UUM")
    print("Embedding generated. Dimensions:", len(emb))
