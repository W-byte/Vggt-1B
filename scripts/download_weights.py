"""Resumable parallel download of the public VGGT-1B safetensors checkpoint."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import hashlib
import json
import os
import time
import requests

import argparse
parser=argparse.ArgumentParser()
parser.add_argument('--endpoint', default='https://huggingface.co', help='Use https://hf-mirror.com only when needed')
parser.add_argument('--workers',type=int,default=8)
args=parser.parse_args()
if args.workers<1 or args.workers>32: parser.error('--workers must be 1..32')
ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "models/VGGT-1B"
DEST.mkdir(parents=True, exist_ok=True)
SIZE = 5026367224
SHA256 = "f164acf60724910d8fe1578bb499d800850c7bb0948db7555c413f9fbe60467e"
URL = args.endpoint.rstrip("/") + "/facebook/VGGT-1B/resolve/860abec7937da0a4c03c41d3c269c366e82abdf9/model.safetensors"
CHUNK = 32 * 1024 * 1024
PARTS = DEST / "parts"
PARTS.mkdir(exist_ok=True)
head = requests.head(URL, allow_redirects=False, timeout=30)
head.raise_for_status()
direct = head.headers.get("Location", URL)

def fetch(i):
    start, end = i * CHUNK, min((i + 1) * CHUNK, SIZE) - 1
    path = PARTS / f"{i:04d}.part"
    expected = end - start + 1
    if path.exists() and path.stat().st_size == expected:
        return expected
    for attempt in range(5):
        try:
            offset = path.stat().st_size if path.exists() else 0
            if offset == expected: return expected
            if offset > expected:
                raise RuntimeError("Oversized chunk")
            resume = start + offset
            with requests.get(direct, headers={"Range": f"bytes={resume}-{end}"},
                              stream=True, timeout=(20, 90)) as r:
                r.raise_for_status()
                if r.status_code != 206 or not r.headers.get("Content-Range", "").startswith(f"bytes {resume}-{end}/"):
                    raise RuntimeError("Server did not honor requested byte range")
                with path.open("ab") as f:
                    began = time.monotonic()
                    for block in r.iter_content(64 * 1024):
                        f.write(block)
                        if time.monotonic() - began > 90:
                            raise TimeoutError("Renewing slow transfer using saved byte offset")
            if path.stat().st_size != expected:
                raise RuntimeError("Incomplete chunk")
            return expected
        except Exception:
            if attempt == 4:
                raise
            time.sleep(2 + attempt)

started = time.monotonic()
done = 0
with ThreadPoolExecutor(max_workers=args.workers) as pool:
    pending = [pool.submit(fetch, i) for i in range((SIZE + CHUNK - 1) // CHUNK)]
    for job in as_completed(pending):
        done += job.result()
        print(f"{done / SIZE:.1%} complete; {done / 1e6:.0f} MB; {done / 1e6 / max(1, time.monotonic()-started):.2f} MB/s", flush=True)
target = DEST / "model.safetensors.verified-download"
digest = hashlib.sha256()
with target.open("wb") as output:
    for i in range((SIZE + CHUNK - 1) // CHUNK):
        part = PARTS / f'{i:04d}.part'
        with part.open("rb") as source:
            while block := source.read(8 * 1024 * 1024):
                digest.update(block)
                output.write(block)
if digest.hexdigest() != SHA256:
    raise RuntimeError("Checkpoint SHA256 mismatch")
os.replace(target, DEST / "model.safetensors")
(DEST / "download_info.json").write_text(json.dumps({"repo": "facebook/VGGT-1B", "revision": "860abec7937da0a4c03c41d3c269c366e82abdf9", "bytes": SIZE, "sha256": SHA256}, indent=2))
print("Verified checkpoint:", DEST / "model.safetensors", flush=True)
