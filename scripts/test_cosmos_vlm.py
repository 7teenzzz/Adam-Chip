#!/usr/bin/env python3
"""Quick smoke-test for Cosmos Reason2-2B as a VLM replacement.

Usage:
    python3 scripts/test_cosmos_vlm.py                    # capture from camera
    python3 scripts/test_cosmos_vlm.py --image path.jpg   # use existing image
    python3 scripts/test_cosmos_vlm.py --compare           # side-by-side with VILA
"""
import argparse
import base64
import json
import sys
import urllib.request

COSMOS_URL = "http://127.0.0.1:8051"
VILA_URL   = "http://127.0.0.1:8050"

PROMPT = (
    "You are a fixed camera sensor in an interactive art installation. "
    "Look at the image and write ONE short English sentence describing what you actually see, "
    "using this structure:\n"
    "Scene: <people count and position>. "
    "Engagement: <one of: none, watching, approaching, leaving, interacting>.\n\n"
    "Output only the final sentence. English only."
)


def capture_camera_jpeg() -> bytes:
    import subprocess
    result = subprocess.run(
        ["ffmpeg", "-f", "v4l2", "-i", "/dev/video0",
         "-vframes", "1", "-f", "image2", "-vcodec", "mjpeg", "pipe:1"],
        capture_output=True, timeout=5,
    )
    if result.returncode != 0 or not result.stdout:
        raise RuntimeError(f"ffmpeg failed: {result.stderr.decode()[:200]}")
    return result.stdout


def ask_vlm(base_url: str, image_b64: str, max_tokens: int = 80) -> str:
    payload = json.dumps({
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
            ],
        }],
        "max_tokens": max_tokens,
        "stream": False,
    }).encode()
    req = urllib.request.Request(
        base_url.rstrip("/") + "/v1/chat/completions",
        data=payload,
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = json.loads(resp.read())
    choices = raw.get("choices", [])
    if not choices:
        return f"[no choices] raw={json.dumps(raw)[:200]}"
    return choices[0].get("message", {}).get("content", "").strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--image", help="Path to JPEG file (skip camera capture)")
    parser.add_argument("--compare", action="store_true", help="Also query VILA on :8050")
    args = parser.parse_args()

    if args.image:
        with open(args.image, "rb") as f:
            jpeg = f.read()
        print(f"Image: {args.image} ({len(jpeg)//1024} KB)")
    else:
        print("Capturing frame from /dev/video0 ...", end=" ", flush=True)
        jpeg = capture_camera_jpeg()
        print(f"ok ({len(jpeg)//1024} KB)")

    image_b64 = base64.b64encode(jpeg).decode("ascii")

    print(f"\n--- Cosmos Reason2-2B ({COSMOS_URL}) ---")
    try:
        reply = ask_vlm(COSMOS_URL, image_b64)
        print(reply)
    except Exception as e:
        print(f"ERROR: {e}")

    if args.compare:
        print(f"\n--- VILA 1.5-3b ({VILA_URL}) ---")
        try:
            reply = ask_vlm(VILA_URL, image_b64)
            print(reply)
        except Exception as e:
            print(f"ERROR: {e}")


if __name__ == "__main__":
    main()
