from __future__ import annotations

import os
import sys
import json
import httpx

OLLAMA_BASE_URL = os.getenv(
    "OLLAMA_BASE_URL", "http://host.docker.internal:11434"
).rstrip("/")
MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")

PROMPT = "Tôi có đẹp trai ko ? "


async def main() -> int:
    print(f"[*] OLLAMA_BASE_URL = {OLLAMA_BASE_URL}")
    print(f"[*] MODEL          = {MODEL}")

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            # 1) ping version
            ver = await client.get(f"{OLLAMA_BASE_URL}/api/version")
            ver.raise_for_status()
            print("[+] /api/version:", ver.json())

            # 2) list models
            tags = await client.get(f"{OLLAMA_BASE_URL}/api/tags")
            tags.raise_for_status()
            models = [m.get("name") for m in tags.json().get("models", [])]
            print(
                "[+] /api/tags models:",
                models[:10],
                ("..." if len(models) > 10 else ""),
            )

            # 3) generate
            res = await client.post(
                f"{OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": MODEL,
                    "prompt": PROMPT,
                    "stream": False,
                    "options": {"temperature": 0},
                },
            )
            res.raise_for_status()
            data = res.json()
            print(
                "[+] /api/generate response:",
                json.dumps(data, indent=2, ensure_ascii=False)[:2000],
            )

            out = (data.get("response") or "").strip()
            print("[+] parsed output:", repr(out))

    except Exception as e:
        print("[!] ERROR:", repr(e))
        return 1

    return 0


if __name__ == "__main__":
    import anyio
    raise SystemExit(anyio.run(main))