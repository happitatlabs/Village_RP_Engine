from __future__ import annotations

import os
import threading


_SERVER_LOCK = threading.Lock()
_SERVER_STARTED = False


def configure_and_start_server(files_dir: str, cache_dir: str, port: int = 8000) -> str:
    global _SERVER_STARTED
    with _SERVER_LOCK:
        os.environ.setdefault("HOME", files_dir)
        os.environ.setdefault("TMPDIR", cache_dir)
        os.environ["VRE_SAVE_DIR"] = os.path.join(files_dir, "saves")
        os.makedirs(os.environ["VRE_SAVE_DIR"], exist_ok=True)

        if _SERVER_STARTED:
            return f"http://127.0.0.1:{port}"

        from web_ui import run_server

        thread = threading.Thread(
            target=run_server,
            kwargs={"host": "127.0.0.1", "port": port},
            daemon=True,
            name="village-rp-embedded-web-ui",
        )
        thread.start()
        _SERVER_STARTED = True
        return f"http://127.0.0.1:{port}"
