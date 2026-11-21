#!/usr/bin/env python3
"""Dedicated Colab G4 Launcher for Wan2.2-Animate (Motion/Expression Transfer from Dual-DB MP4s) + DWPose.

Hardened with 20s apt-get timeout + bulletproof parallel curl fallback + Drive v3 NVMe staging.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

if os.path.isdir("/content/drive/My Drive") and not os.path.exists("/content/drive/MyDrive"):
    os.symlink("/content/drive/My Drive", "/content/drive/MyDrive")

DRIVE_MODELS = Path("/content/drive/MyDrive/AI_Workstation/ComfyUI/models")
FAST_MODELS = Path("/content/fast_wan_animate_models")
LOCAL_COMFY = Path("/content/ComfyUI")

# Repackaged Wan2.2-Animate + shared Wan2.1 VAE / UMT5 / CLIPVision / LightX2V weights
MODELS = [
    (
        "diffusion_models",
        "Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors",
        "https://huggingface.co/Kijai/WanVideo_comfy_fp8_scaled/resolve/main/Wan22Animate/Wan2_2-Animate-14B_fp8_e4m3fn_scaled_KJ.safetensors",
    ),
    (
        "loras",
        "lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors",
        "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/Lightx2v/lightx2v_I2V_14B_480p_cfg_step_distill_rank64_bf16.safetensors",
    ),
    (
        "text_encoders",
        "umt5-xxl-enc-fp8_e4m3fn.safetensors",
        "https://huggingface.co/Kijai/WanVideo_comfy/resolve/main/umt5-xxl-enc-fp8_e4m3fn.safetensors",
    ),
    (
        "vae",
        "wan_2.1_vae.safetensors",
        "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/vae/wan_2.1_vae.safetensors",
    ),
    (
        "clip_vision",
        "clip_vision_h.safetensors",
        "https://huggingface.co/Comfy-Org/Wan_2.1_ComfyUI_repackaged/resolve/main/split_files/clip_vision/clip_vision_h.safetensors",
    ),
]


def sh(cmd: str) -> str:
    return subprocess.run(cmd, shell=True, text=True, capture_output=True).stdout


def get_drive_token() -> str | None:
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:8012/computeMetadata/v1/instance/service-accounts/default/token",
            headers={"Metadata-Flavor": "Google"},
        )
        return json.loads(urllib.request.urlopen(req, timeout=3).read().decode())["access_token"]
    except Exception:
        return None


def main() -> None:
    t0 = time.time()
    print("=== [1/3] Wan2.2-Animate Dual-DB Motion Transfer G4 Boot ===", flush=True)
    print(sh("nvidia-smi --query-gpu=name,memory.total --format=csv,noheader").strip(), flush=True)
    if not shutil.which("aria2c"):
        sh("timeout 20 bash -c 'apt-get update -qq -o Acquire::http::Timeout=6 -o Acquire::https::Timeout=6 || true; DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends aria2 || true'")

    tok = get_drive_token()
    fmap: dict = {}
    if tok:
        try:
            q = urllib.parse.urlencode({"q": 'trashed = false and name contains ".safetensors"', "fields": "files(id,name,size)", "pageSize": 200})
            req = urllib.request.Request(f"https://www.googleapis.com/drive/v3/files?{q}", headers={"Authorization": f"Bearer {tok}"})
            fmap = {f["name"]: f for f in json.loads(urllib.request.urlopen(req, timeout=10).read().decode()).get("files", [])}
        except Exception as exc:
            print(f"Drive API fallback to HF: {exc}", flush=True)

    jobs: list[tuple[str, Path, bool, Path]] = []
    for sub, fn, hf_url in MODELS:
        nv = FAST_MODELS / sub / fn
        dr = DRIVE_MODELS / sub / fn
        nv.parent.mkdir(parents=True, exist_ok=True)
        dr.parent.mkdir(parents=True, exist_ok=True)
        meta = fmap.get(fn)
        if meta and tok:
            if not (nv.exists() and nv.stat().st_size == int(meta.get("size", 0))):
                jobs.append((f"https://www.googleapis.com/drive/v3/files/{meta['id']}?alt=media", nv, True, dr))
        else:
            if not (nv.exists() and nv.stat().st_size > 10_000_000):
                jobs.append((hf_url, nv, False, dr))

    dl_err: list[Exception] = []

    def _stage() -> None:
        try:
            def _one(j: tuple[str, Path, bool, Path]) -> None:
                u, dst, auth, _dr = j
                cmd = ["curl", "-fsSL", "--retry", "5", "--retry-delay", "2", "-C", "-", "-o", str(dst)]
                if auth and tok:
                    cmd += ["-H", f"Authorization: Bearer {tok}"]
                cmd.append(u)
                subprocess.run(cmd, check=True)
                print(f"  [STAGED] {dst.name} ({dst.stat().st_size / 1e9:.2f} GB)", flush=True)

            with ThreadPoolExecutor(max_workers=4) as ex:
                list(ex.map(_one, jobs))
        except Exception as exc:
            dl_err.append(exc)

    t_dl = threading.Thread(target=_stage, daemon=True)
    t_dl.start()

    print("=== [2/3] Installing ComfyUI + WanVideoWrapper + ControlNetAux (DWPose) ===", flush=True)
    if not (LOCAL_COMFY / "main.py").exists():
        subprocess.run(f"git clone --depth 1 -q https://github.com/comfyanonymous/ComfyUI.git {LOCAL_COMFY}", shell=True, check=True)
    cn = LOCAL_COMFY / "custom_nodes"
    cn.mkdir(parents=True, exist_ok=True)
    for name, repo in [
        ("ComfyUI-WanVideoWrapper", "https://github.com/kijai/ComfyUI-WanVideoWrapper.git"),
        ("ComfyUI-KJNodes", "https://github.com/kijai/ComfyUI-KJNodes.git"),
        ("ComfyUI-VideoHelperSuite", "https://github.com/Kosinkadink/ComfyUI-VideoHelperSuite.git"),
        ("comfyui_controlnet_aux", "https://github.com/Fannovel16/comfyui_controlnet_aux.git"),
    ]:
        if not (cn / name).exists():
            subprocess.run(f"git clone --depth 1 -q {repo} {cn / name}", shell=True, check=True)

    subprocess.run(
        f"uv pip install --system -q -r {LOCAL_COMFY}/requirements.txt -r {cn}/ComfyUI-WanVideoWrapper/requirements.txt "
        "accelerate einops ftfy diffusers>=0.33.0 peft>=0.17.0 onnxruntime-gpu opencv-python-headless scipy imageio-ffmpeg color-matcher",
        shell=True,
        check=True,
    )
    if not os.path.exists("/usr/local/bin/cloudflared"):
        subprocess.run(
            "wget -q https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -O /usr/local/bin/cloudflared && chmod +x /usr/local/bin/cloudflared",
            shell=True,
            check=True,
        )

    t_dl.join()
    if dl_err:
        raise dl_err[0]

    # Symlink models into ComfyUI
    mroot = LOCAL_COMFY / "models"
    for sub, fn, _ in MODELS:
        (mroot / sub).mkdir(parents=True, exist_ok=True)
        link = mroot / sub / fn
        if link.exists() or link.is_symlink():
            link.unlink()
        link.symlink_to(FAST_MODELS / sub / fn)

    # Cache newly downloaded HF weights back to Drive asynchronously
    def _cache_back() -> None:
        for _u, nv, auth, dr in jobs:
            if not auth and nv.exists() and not dr.exists():
                try:
                    shutil.copy2(nv, dr)
                except Exception:
                    pass
    threading.Thread(target=_cache_back, daemon=True).start()

    print("=== [3/3] Starting Wan2.2-Animate ComfyUI + HTTP/2 Cloudflare Tunnel ===", flush=True)
    subprocess.Popen(
        ["python3", str(LOCAL_COMFY / "main.py"), "--listen", "127.0.0.1", "--port", "8188", "--highvram", "--disable-mmap"],
        stdout=open("/tmp/comfy_animate.log", "w"),
        stderr=subprocess.STDOUT,
    )
    for _ in range(90):
        time.sleep(2)
        try:
            urllib.request.urlopen("http://127.0.0.1:8188/system_stats", timeout=2)
            break
        except Exception:
            pass

    subprocess.Popen(
        ["/usr/local/bin/cloudflared", "tunnel", "--protocol", "http2", "--url", "http://127.0.0.1:8188"],
        stdout=open("/tmp/cf_animate.log", "w"),
        stderr=subprocess.STDOUT,
    )
    for _ in range(30):
        time.sleep(2)
        txt = Path("/tmp/cf_animate.log").read_text(errors="ignore")
        m = re.search(r"(https://[a-z0-9-]+\.trycloudflare\.com)", txt)
        if m:
            print(f"WAN_ANIMATE_READY={m.group(1)} (total={time.time()-t0:.1f}s)", flush=True)
            return
    raise RuntimeError("Cloudflare tunnel failed to start")


if __name__ == "__main__":
    main()
