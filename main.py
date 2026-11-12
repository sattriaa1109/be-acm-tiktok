from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import os
import traceback

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class CommentRequest(BaseModel):
    url: str
    accounts: list[str] = ["akun1"]
    mood: str = "positive"
    context: str = ""
    per_account_comment: bool = True

@app.post("/comment")
async def api_comment(req: CommentRequest):
    loop = asyncio.get_event_loop()
    
    def process_sync():
        try:
            import tiktok_comment
            print(f"[*] Memulai proses untuk {req.accounts}...", flush=True)
            # PENTING: preview=False biar gak nanya input()
            result = tiktok_comment.run_auto_comment(
                req.url,
                req.accounts,
                req.mood,
                context=req.context,
                per_account_comment=req.per_account_comment,
                preview=False,  # <--- INI KUNCINYA
            )
            print(f"[*] Selesai: {result}", flush=True)
        except Exception as e:
            print(f"[!] ERROR: {e}", flush=True)
            traceback.print_exc()

    loop.run_in_executor(None, process_sync)
    return {"success": True, "message": "Diproses di background. Cek log Docker!"}

@app.get("/status")
def get_status():
    return {"status": "ok"}
