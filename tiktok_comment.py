"""
tiktok_comment.py
─────────────────
Kirim komentar otomatis ke video TikTok via Chrome CDP (Playwright).
Komentar di-generate oleh Gemini AI (gemini_comment.py).

Fitur:
  - Pilih mood komentar (positive / negative / neutral / funny / flirty / hype)
  - Pilih akun (atau semua sekaligus)
  - Preview komentar sebelum dikirim
  - Jeda acak antar akun (anti-detect)
  - Simpan hasil ke comment_history.json

Cara pakai:
  python tiktok_comment.py
  python tiktok_comment.py --url "https://tiktok.com/@x/video/..." --mood positive --accounts akun1 akun2
"""

import time
import random
import json
import os
import argparse
from datetime import datetime
from playwright.sync_api import sync_playwright

from gemini_comment import generate_comment, init_gemini, list_moods, AI_MODEL

# ─────────────────────────────────────────────────────────────
# Konfigurasi CDP
# ─────────────────────────────────────────────────────────────

ACCOUNT_PORT_MAP = {
    "akun1": 9222,  # Fatur Ikhsanudin
    "akun2": 9223,  # Ridetes7
    "akun3": 9224,  # Ridonajrul
    "akun4": 9225,  # Usertestpkl
    "akun5": 9226,  # Gptridho
}

DISPLAY_NAMES = {
    "akun1": "Fatur Ikhsanudin",
    "akun2": "Ridetes7",
    "akun3": "Ridonajrul",
    "akun4": "Usertestpkl",
    "akun5": "Gptridho",
}

HOST_IP = "172.18.0.1"

# Delay antar akun (detik)
MIN_DELAY = 5
MAX_DELAY = 12

# File histori
HISTORY_FILE = "comment_history.json"

# ─────────────────────────────────────────────────────────────
# Selector komentar TikTok (coba urut dari paling reliable)
# ─────────────────────────────────────────────────────────────

COMMENT_INPUT_SELECTORS = [
    '[data-e2e="comment-input"]',
    'div[contenteditable="true"][data-e2e*="comment"]',
    'div[contenteditable="true"]',
    'textarea[placeholder*="komentar" i]',
    'textarea[placeholder*="comment" i]',
    'textarea[placeholder*="Add comment" i]',
]

SUBMIT_BUTTON_SELECTORS = [
    '[data-e2e="comment-post"]',
    'div[data-e2e="comment-submit"]',
    'button[data-e2e*="post"]',
    'span[data-e2e*="post"]',
]

# ─────────────────────────────────────────────────────────────
# Histori
# ─────────────────────────────────────────────────────────────

def load_history() -> list:
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return []


def save_history(entry: dict):
    history = load_history()
    history.insert(0, entry)
    history = history[:200]  # batasi 200 entry
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)


# ─────────────────────────────────────────────────────────────
# Core: kirim komentar via CDP
# ─────────────────────────────────────────────────────────────

def post_comment(account_name: str, url: str, comment: str) -> dict:
    """Post comment via Visual Click + Trik Spasi (Simpel)"""
    import time
    from playwright.sync_api import sync_playwright

    try:
        if account_name.lower().startswith("akun"):
            num = int(account_name.lower().replace("akun", ""))
        else:
            num = int(account_name)
        port = 9221 + num
    except Exception:
        return {"success": False, "error": f"Invalid account: {account_name}"}

    cdp_url = f"http://172.18.0.1:{port}"
    max_retries = 3

    def is_comment_panel_open(page):
        selectors = [
            'div[contenteditable="true"]',
            '[data-e2e="comment-input"]',
            'div[role="textbox"]',
            '[data-e2e="comment-list"]',
        ]
        for sel in selectors:
            try:
                if page.locator(sel).count() > 0:
                    return True
            except: continue
        return False

    def click_comment_icon(page):
        icon_selectors = [
            '[data-e2e="comment-icon"]',
            'div[data-e2e="comment-icon"]',
            'button[data-e2e="comment-icon"]',
        ]
        for selector in icon_selectors:
            try:
                locator = page.locator(selector).first
                locator.wait_for(state="visible", timeout=5000)
                box = locator.bounding_box()
                if not box: continue
                
                page.evaluate("""(sel) => {
                    const el = document.querySelector(sel);
                    if (el) el.scrollIntoView({block: 'center'});
                }""", selector)
                time.sleep(0.4)
                
                box = locator.bounding_box()
                if not box: continue
                
                cx = box["x"] + box["width"] / 2
                cy = box["y"] + box["height"] / 2
                page.mouse.click(cx, cy)
                time.sleep(1.2)
                return True
            except: continue
        return False

    try:
        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(cdp_url)
            if not browser.contexts:
                return {"success": False, "error": "No browser context"}
            
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else context.new_page()

            # 1. Buka URL
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            time.sleep(4)

            # 2. Buka Panel Komentar
            panel_opened = False
            for attempt in range(1, max_retries + 1):
                print(f"[Attempt {attempt}] Klik comment-icon...")
                if not click_comment_icon(page):
                    return {"success": False, "error": "Gagal menemukan comment-icon"}
                
                if is_comment_panel_open(page):
                    panel_opened = True
                    print("[+] Panel komentar terbuka.")
                    break
                else:
                    print("[!] Panel belum terbuka, coba lagi...")
                    time.sleep(1.0)

            if not panel_opened:
                return {"success": False, "error": "Panel gagal terbuka"}

            time.sleep(0.8)

            # 3. Cari Input & Ketik + Spasi (KODE GROK BARU)
            input_selectors = [
                'div[contenteditable="true"]',
                '[data-e2e="comment-input"]',
                'div[role="textbox"]',
            ]
            input_el = None
            for sel in input_selectors:
                try:
                    loc = page.locator(sel).first
                    if loc.count() > 0:
                        loc.wait_for(state="visible", timeout=5000)
                        input_el = loc
                        break
                except: continue

            if not input_el:
                return {"success": False, "error": "Kolom input tidak ditemukan"}

            input_el.click(force=True)
            time.sleep(0.3)
            
            # Ketik teks + SPASI (Jangan dihapus!)
            print("[*] Mengetik komentar + spasi...")
            full_text = comment + " "
            page.keyboard.type(full_text, delay=25)
            time.sleep(0.5) # Jeda biar tombol merah

            # 4. Klik Submit
            submit_selectors = [
                '[data-e2e="comment-post"]',
                'button[data-e2e="comment-post"]',
                'div[data-e2e="comment-post"]',
                '[data-e2e="comment-post-button"]',
            ]
            submitted = False
            for sel in submit_selectors:
                try:
                    btn = page.locator(sel).first
                    if btn.count() > 0:
                        box = btn.bounding_box()
                        if box:
                            cx = box["x"] + box["width"] / 2
                            cy = box["y"] + box["height"] / 2
                            page.mouse.click(cx, cy)
                            submitted = True
                            print(f"[+] Tombol submit diklik via {sel}")
                            break
                        else:
                            btn.click(force=True)
                            submitted = True
                            break
                except: continue

            if not submitted:
                try:
                    page.keyboard.press("Enter")
                    submitted = True
                except: pass

            if not submitted:
                return {"success": False, "error": "Tombol submit gagal diklik"}

            time.sleep(2.0)
            return {"success": True, "message": "Comment posted"}

    except Exception as e:
        return {"success": False, "error": f"Unexpected error: {e}"}

def run_auto_comment(
    url: str,
    accounts: list[str],
    mood: str,
    context: str = "",
    per_account_comment: bool = True,
    preview: bool = True,
    custom_prompt: str = "",
) -> dict:
    """
    Jalankan auto comment untuk banyak akun.

    Args:
        url                 : URL video TikTok
        accounts            : List account id yang akan dipakai
        mood                : Mood komentar (positive/negative/dll)
        context             : Deskripsi singkat video untuk Gemini
        per_account_comment : True = generate komentar unik per akun,
                              False = semua akun pakai komentar yang sama
        preview             : True = tampilkan preview dan minta konfirmasi
        custom_prompt       : Arahan tambahan dari user untuk gaya/isi komentar

    Returns:
        dict berisi summary hasil
    """
    print(f"\n{'='*55}")
    print(f"  🤖 Auto Comment TikTok — {AI_MODEL}")
    print(f"{'='*55}")
    print(f"  URL    : {url}")
    print(f"  Mood   : {mood}")
    print(f"  Akun   : {', '.join(accounts)}")
    print(f"{'='*55}\n")

    # Init Gemini
    try:
        gemini_client = init_gemini()
        print(f"✅ Gemini API siap\n")
    except ValueError as e:
        print(e)
        return {"success": False, "error": str(e)}

    if not context:
        context = f"Video TikTok di URL: {url}"

    # Generate komentar
    if per_account_comment:
        # Komentar unik per akun
        print(f"⏳ Generating {len(accounts)} komentar unik (mood: {mood})...")
        try:
            comments_list = generate_comment(
                context,
                mood=mood,
                client=gemini_client,
                count=len(accounts),
                custom_prompt=custom_prompt,
            )
        except RuntimeError as e:
            print(f"\n❌ {e}")
            return {"success": False, "error": str(e)}

        # Pad jika kurang, maksimal 3 kali coba
        retry = 0
        while len(comments_list) < len(accounts) and retry < 3:
            retry += 1
            try:
                extra = generate_comment(context, mood=mood, client=gemini_client, count=1, custom_prompt=custom_prompt)
                comments_list.extend(extra)
            except RuntimeError as e:
                print(f"\n❌ {e}")
                return {"success": False, "error": str(e)}

        if len(comments_list) < len(accounts):
            print(f"⚠️  Hanya berhasil generate {len(comments_list)} komentar dari {len(accounts)} yang diminta.")
            accounts = accounts[:len(comments_list)]

        comments_list = comments_list[:len(accounts)]
    else:
        # Satu komentar sama untuk semua
        print(f"⏳ Generating 1 komentar untuk semua akun (mood: {mood})...")
        try:
            comments_list = generate_comment(context, mood=mood, client=gemini_client, count=1, custom_prompt=custom_prompt)
        except RuntimeError as e:
            print(f"\n❌ {e}")
            return {"success": False, "error": str(e)}

        if not comments_list:
            print("❌ Gagal generate komentar.")
            return {"success": False, "error": "Gagal generate komentar dari Gemini"}
        comments_list = [comments_list[0]] * len(accounts)

    # Preview
    print(f"\n{'─'*55}")
    print("📋 Preview komentar yang akan dikirim:")
    print(f"{'─'*55}")
    for acc, cmt in zip(accounts, comments_list):
        name = DISPLAY_NAMES.get(acc, acc)
        print(f"  [{acc}] {name}")
        print(f"        💬 \"{cmt}\"")
    print(f"{'─'*55}")

    if preview:
        confirm = input("\n▶️  Lanjutkan kirim komentar? [y/N]: ").strip().lower()
        if confirm != "y":
            print("❌ Dibatalkan.")
            return {"success": False, "error": "Dibatalkan oleh user"}

    # Eksekusi
    task_result = {
        "id": f"comment_{int(time.time())}",
        "url": url,
        "mood": mood,
        "context": context,
        "custom_prompt": custom_prompt,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "results": {"success": 0, "failed": 0},
        "details": [],
    }

    print(f"\n🚀 Mulai mengirim komentar...\n")

    for i, (account_id, comment) in enumerate(zip(accounts, comments_list)):
        result = post_comment(account_id, url, comment)
        task_result["details"].append(result)

        if result["success"]:
            task_result["results"]["success"] += 1
        else:
            task_result["results"]["failed"] += 1
            print(f"   ⚠️  Error: {result.get('error', 'Unknown')}")

        # Jeda antar akun (kecuali akun terakhir)
        if i < len(accounts) - 1:
            delay = random.randint(MIN_DELAY, MAX_DELAY)
            print(f"\n⏳ Jeda {delay} detik sebelum akun berikutnya...")
            time.sleep(delay)

    # Ringkasan
    s = task_result["results"]["success"]
    f = task_result["results"]["failed"]
    task_result["status"] = "success" if f == 0 else ("failed" if s == 0 else "partial")

    print(f"\n{'='*55}")
    print(f"🏁 SELESAI")
    print(f"   ✅ Berhasil : {s}")
    print(f"   ❌ Gagal    : {f}")
    print(f"{'='*55}")

    # Simpan histori
    save_history(task_result)
    print(f"💾 Hasil disimpan ke {HISTORY_FILE}")

    return task_result


# ─────────────────────────────────────────────────────────────
# CLI interaktif
# ─────────────────────────────────────────────────────────────

def interactive_mode():
    """Mode interaktif step-by-step."""
    print("=" * 55)
    print("  💬 Auto Comment TikTok — Powered by Gemini AI")
    print("=" * 55)

    # 1. URL
    url = input("\n📎 Masukkan URL video TikTok: ").strip()
    if not url or "tiktok.com" not in url:
        print("❌ URL tidak valid.")
        return

    # 2. Konteks video (opsional)
    print("\n📝 Deskripsi singkat isi video (opsional, tekan Enter untuk skip):")
    print("   Contoh: 'Dance video lagu viral', 'Tutorial masak mie', 'Video kucing lucu'")
    context = input("Konteks: ").strip()

    # 3. Mood
    moods = list_moods()
    print("\n📌 Pilih mood komentar:")
    mood_keys = list(moods.keys())
    for i, (key, desc) in enumerate(moods.items(), 1):
        print(f"  [{i}] {desc}")

    while True:
        try:
            choice = int(input("\nMasukkan nomor [1/2]: "))
            if 1 <= choice <= len(mood_keys):
                selected_mood = mood_keys[choice - 1]
                break
            print("   ⚠️  Masukkan 1 atau 2.")
        except ValueError:
            print("   ⚠️  Masukkan angka.")

    print(f"✅ Mood: {moods[selected_mood]}")

    # 4. Pilih akun
    print("\n👥 Pilih akun:")
    acc_keys = list(ACCOUNT_PORT_MAP.keys())
    print(f"  [0] Semua akun ({len(acc_keys)} akun)")
    for i, acc_id in enumerate(acc_keys, 1):
        name = DISPLAY_NAMES.get(acc_id, acc_id)
        print(f"  [{i}] {acc_id} — {name} (Port {ACCOUNT_PORT_MAP[acc_id]})")

    while True:
        raw = input("\nMasukkan nomor akun (pisah koma, 0=semua): ").strip()
        if raw == "0":
            selected_accounts = acc_keys
            break
        try:
            choices = [int(x.strip()) for x in raw.split(",")]
            selected_accounts = []
            valid = True
            for c in choices:
                if 1 <= c <= len(acc_keys):
                    selected_accounts.append(acc_keys[c - 1])
                else:
                    print(f"   ⚠️  Nomor {c} tidak valid.")
                    valid = False
                    break
            if valid and selected_accounts:
                break
        except ValueError:
            print("   ⚠️  Format tidak valid. Contoh: 1,3,5")

    print(f"✅ Akun dipilih: {', '.join(selected_accounts)}")

    # 5. Mode komentar (unik / sama)
    print("\n🔀 Mode komentar:")
    print("  [1] Komentar unik per akun (lebih natural)")
    print("  [2] Komentar sama untuk semua akun")
    while True:
        try:
            mode_choice = int(input("Pilih [1/2]: ") or "1")
            if mode_choice in (1, 2):
                per_account = mode_choice == 1
                break
        except ValueError:
            pass
        print("   ⚠️  Masukkan 1 atau 2.")

    # 6. Jalankan
    run_auto_comment(
        url=url,
        accounts=selected_accounts,
        mood=selected_mood,
        context=context,
        per_account_comment=per_account,
        preview=True,
    )


def cli_mode():
    """Mode CLI via argumen."""
    parser = argparse.ArgumentParser(
        description="Auto Comment TikTok dengan Gemini AI"
    )
    parser.add_argument("--url", required=True, help="URL video TikTok")
    parser.add_argument(
        "--mood",
        default="positive",
        choices=list(list_moods().keys()),
        help="Mood komentar",
    )
    parser.add_argument(
        "--accounts",
        nargs="+",
        default=list(ACCOUNT_PORT_MAP.keys()),
        help="Akun yang dipakai (misal: akun1 akun2)",
    )
    parser.add_argument("--context", default="", help="Deskripsi singkat video")
    parser.add_argument(
        "--prompt",
        default="",
        help="Arahan tambahan untuk AI (contoh: komentar singkat, lucu, pakai emoji)",
    )
    parser.add_argument(
        "--same-comment",
        action="store_true",
        help="Pakai komentar yang sama untuk semua akun",
    )
    parser.add_argument(
        "--no-preview",
        action="store_true",
        help="Langsung kirim tanpa preview konfirmasi",
    )
    args = parser.parse_args()

    run_auto_comment(
        url=args.url,
        accounts=args.accounts,
        mood=args.mood,
        context=args.context,
        per_account_comment=not args.same_comment,
        preview=not args.no_preview,
        custom_prompt=args.prompt,
    )


# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys

    # Jika ada argumen CLI, pakai mode CLI
    if len(sys.argv) > 1:
        cli_mode()
    else:
        # Tidak ada argumen → mode interaktif
        interactive_mode()
