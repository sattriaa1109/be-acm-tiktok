"""
ai_comment.py (alias: gemini_comment.py)
─────────────────────────────────────────
Generate komentar TikTok menggunakan AI — support Gemini & Grok.
"""
import os
from dotenv import load_dotenv

load_dotenv()

AI_PROVIDER    = os.getenv("AI_PROVIDER", "gemini").lower()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GROK_API_KEY   = os.getenv("GROK_API_KEY", "")

GEMINI_MODEL = "gemini-3.8-flash"
GROK_MODEL = "openai/gpt-oss-120b"

PROMPT_TEMPLATES = {
    "positive": """
Kamu adalah pengguna TikTok yang sangat positif dan supportif.
Buat 1 komentar singkat dalam Bahasa Indonesia untuk video TikTok berikut.

Ketentuan:
- Komentar harus positif, mendukung, dan tulus
- Panjang: 1-2 kalimat (maksimal 100 karakter)
- Gunakan bahasa gaul TikTok yang natural (boleh pakai emoji secukupnya)
- JANGAN pakai hashtag
- Output HANYA komentar saja, tanpa penjelasan apapun

Konteks video: {context}
""",
    "negative": """
Kamu adalah pengguna TikTok yang kritis dan suka memberikan kritik pedas.
Buat 1 komentar singkat dalam Bahasa Indonesia untuk video TikTok berikut.

Ketentuan:
- Komentar harus kritis, sinis, atau meremehkan (tapi BUKAN hate speech atau SARA)
- Panjang: 1-2 kalimat (maksimal 100 karakter)
- Gunakan bahasa gaul TikTok yang natural (boleh pakai emoji secukupnya)
- JANGAN pakai hashtag
- Output HANYA komentar saja, tanpa penjelasan apapun

Konteks video: {context}
""",
}

FATAL_CODES = ["400", "401", "403", "404", "429", "permission_denied", "unauthenticated", "not found", "billing", "not supported", "invalid api key", "unauthorized"]

def _init_gemini():
    if not GEMINI_API_KEY: raise ValueError("❌ GEMINI_API_KEY belum diset di .env")
    from google import genai
    return genai.Client(api_key=GEMINI_API_KEY)

def _generate_gemini(client, prompt: str) -> str:
    from google import genai
    from google.genai import types
    response = client.models.generate_content(
        model=GEMINI_MODEL, contents=prompt,
        config=types.GenerateContentConfig(temperature=0.9, max_output_tokens=150),
    )
    return response.text.strip().strip('"').strip("'")

def _init_grok():
    if not GROK_API_KEY: raise ValueError("❌ GROK_API_KEY belum diset di .env")
    from openai import OpenAI
    return OpenAI(api_key=GROK_API_KEY, base_url="https://api.groq.com/openai/v1")

def _generate_grok(client, prompt: str) -> str:
    try:
        response = client.chat.completions.create(
            model=GROK_MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            max_tokens=1000,  # <--- Naikin biar gak kosong
            extra_body={"reasoning_effort": "low"}  # <--- Biar cepet & gak abis token
        )
        content = response.choices[0].message.content
        if not content:
            raise Exception("Groq balikin content kosong")
        return content.strip().strip('"').strip("'")
    except Exception as e:
        raise Exception(f"Groq gagal: {e}")

def init_gemini():
    if AI_PROVIDER == "grok":
        client = _init_grok()
        print(f"🤖 Provider: Grok ({GROK_MODEL})")
    else:
        client = _init_gemini()
        print(f"🤖 Provider: Gemini ({GEMINI_MODEL})")
    return client

def generate_comment(context: str, mood: str = "positive", client=None, count: int = 1, custom_prompt: str = "") -> list[str]:
    if mood not in PROMPT_TEMPLATES:
        raise ValueError(f"Mood '{mood}' tidak valid. Pilihan: {list(PROMPT_TEMPLATES.keys())}")
    if client is None: client = init_gemini()

    prompt = PROMPT_TEMPLATES[mood].format(context=context)
    if custom_prompt.strip():
        prompt += (
            "\nArahan tambahan dari pengguna (WAJIB DIIKUTI):\n"
            f"{custom_prompt.strip()}\n"
        )
    comments = []
    for i in range(count):
        try:
            if AI_PROVIDER == "grok": comment = _generate_grok(client, prompt)
            else: comment = _generate_gemini(client, prompt)
            comments.append(comment)
        except Exception as e:
            err_str = str(e).lower()
            print(f"[!] Error generate komentar #{i+1}: {e}")
            if any(code in err_str for code in FATAL_CODES):
                hints = ""
                if "not found" in err_str: hints = "\n   Model tidak ditemukan."
                elif "billing" in err_str or "403" in err_str: hints = "\n   Billing belum aktif."
                elif "429" in err_str: hints = "\n   Rate limit / quota habis."
                elif "invalid api key" in err_str or "unauthorized" in err_str: hints = "\n   API key salah."
                raise RuntimeError(f"AI API fatal error ({AI_PROVIDER}): {e}{hints}")
            comments.append(None)
    return [c for c in comments if c]

AI_MODEL = GROK_MODEL if AI_PROVIDER == "grok" else GEMINI_MODEL

def list_moods() -> dict:
    """Fungsi buat nampilin pilihan mood (dipanggil tiktok_comment.py)."""
    return {
        "positive": "😊 Positif — pujian & dukungan",
        "negative": "😒 Negatif — kritik & sinis",
    }
