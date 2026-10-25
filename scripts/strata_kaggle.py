"""Guided Kaggle helpers for running Strata-supported models safely."""
from __future__ import annotations

import concurrent.futures
import hashlib
import json
import os
import platform
import posixpath
import re
import shutil
import signal
import queue
import threading
import subprocess
import sys
import tarfile
import time
from pathlib import Path, PurePosixPath
from typing import Any

WORKING = Path("/kaggle/working")
INPUT_ROOT = Path("/kaggle/input/datasets")
STRATA_ROOT = Path("/root/.local/share/strata")
STRATA_BIN = Path("/root/.local/bin/strata")
CLOUDFLARED_BIN = Path("/root/.local/bin/cloudflared")


def log(message: str) -> None:
    print("[DevZoneX Strata] " + message, flush=True)


def redact(text: str) -> str:
    text = re.sub(r"sk-strata-[A-Za-z0-9._~-]+", "sk-strata-<redacted>", text)
    text = re.sub(r"(?i)(authorization\s*:\s*bearer\s+)\S+", r"\1<redacted>", text)
    text = re.sub(r"(?i)(KAGGLE_API_TOKEN\s*=\s*)\S+", r"\1<redacted>", text)
    return text


def run_command(command: list[str], *, check: bool = True, timeout: int | None = None,
                env: dict[str, str] | None = None, capture: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command, text=True, stdout=subprocess.PIPE if capture else None,
        stderr=subprocess.STDOUT if capture else None, env=env,
        timeout=timeout, check=False,
    )
    output = (result.stdout or "") if capture else ""
    safe_output = redact(output)
    if safe_output.strip():
        print(safe_output, end="" if safe_output.endswith("\n") else "\n", flush=True)
    if check and result.returncode != 0:
        raise RuntimeError("Command failed (" + str(result.returncode) + "): " +
                           " ".join(command) + "\n" + safe_output[-5000:])
    return result


def kaggle_env(username: str, secret_name: str = "KAGGLE_API_TOKEN") -> dict[str, str]:
    if not username or username.lower().startswith("your-"):
        raise ValueError("Set KAGGLE_USERNAME in the notebook configuration cell.")
    try:
        from kaggle_secrets import UserSecretsClient
        token = UserSecretsClient().get_secret(secret_name).strip()
    except Exception as exc:
        raise RuntimeError(
            "Kaggle Secret " + secret_name + " was not available. Add it in Add-ons > Secrets, "
            "enable notebook access, and rerun. Do not paste the token into notebook code."
        ) from exc
    if not token:
        raise RuntimeError("Kaggle Secret " + secret_name + " is empty.")
    # Keep credentials outside the saved notebook workspace and never print the token.
    home = Path("/tmp/devzonex-kaggle-home")
    config = home / ".kaggle"
    config.mkdir(parents=True, exist_ok=True)
    token_path = config / "access_token"
    token_path.write_text(token + "\n", encoding="utf-8")
    token_path.chmod(0o600)
    env = os.environ.copy()
    env.update({
        "HOME": str(home),
        "TMPDIR": "/kaggle/working/tmp",
        "XDG_CACHE_HOME": str(home / ".cache"),
        "KAGGLE_CONFIG_DIR": str(config),
        "KAGGLE_USERNAME": username,
    })
    Path(env["TMPDIR"]).mkdir(parents=True, exist_ok=True)
    Path(env["XDG_CACHE_HOME"]).mkdir(parents=True, exist_ok=True)
    os.environ["KAGGLE_CONFIG_DIR"] = str(config)
    os.environ["KAGGLE_USERNAME"] = username
    os.environ["TMPDIR"] = env["TMPDIR"]
    os.environ["XDG_CACHE_HOME"] = env["XDG_CACHE_HOME"]
    log("Kaggle Secret loaded into a temporary credential directory (value hidden).")
    return env


def install_kaggle_cli(env: dict[str, str] | None = None) -> None:
    run_command([sys.executable, "-m", "pip", "install", "--quiet", "--upgrade", "kaggle"],
                timeout=900, env=env)
    run_command(["kaggle", "--version"], timeout=60, env=env)


def run_streaming(command: list[str], *, check: bool = True, timeout: int | None = None,
                  env: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    """Run a command while streaming stdout/stderr to the notebook, including CR progress bars."""
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
        bufsize=8192, start_new_session=True,
    )
    if process.stdout is None:
        raise RuntimeError("Could not capture process output.")
    output_queue: queue.Queue[bytes | None] = queue.Queue()
    captured: list[str] = []

    def pump() -> None:
        pending = bytearray()
        try:
            while True:
                chunk = process.stdout.read1(4096)
                if not chunk:
                    break
                pending.extend(chunk)
                while True:
                    split_at = next((i for i, byte in enumerate(pending) if byte in (10, 13)), None)
                    if split_at is None:
                        break
                    separator = pending[split_at]
                    piece = bytes(pending[:split_at + 1])
                    del pending[:split_at + 1]
                    # Combine CRLF into one newline event.
                    if separator == 13 and pending[:1] == b"\n":
                        piece += b"\n"
                        del pending[:1]
                    output_queue.put(piece)
            if pending:
                output_queue.put(bytes(pending))
        finally:
            output_queue.put(None)

    reader = threading.Thread(target=pump, daemon=True)
    reader.start()
    deadline = time.monotonic() + timeout if timeout is not None else None
    reached_eof = False
    try:
        while not reached_eof:
            if deadline is not None and time.monotonic() >= deadline and process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                raise TimeoutError(
                    f"Command timed out after {timeout}s: {' '.join(command)}. "
                    f"Recent output: {redact(''.join(captured)[-3000:])}"
                )
            try:
                item = output_queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if item is None:
                reached_eof = True
                continue
            text_piece = item.decode("utf-8", errors="replace")
            safe_piece = redact(text_piece)
            captured.append(text_piece)
            if text_piece.endswith("\r") and not text_piece.endswith("\r\n"):
                print("\r" + safe_piece.rstrip("\r"), end="", flush=True)
            else:
                print(safe_piece, end="" if safe_piece.endswith("\n") else "\\n", flush=True)
    finally:
        if process.poll() is None:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
        reader.join(timeout=2)
        process.stdout.close()

    output = redact("".join(captured))
    completed = subprocess.CompletedProcess(command, process.returncode, output, None)
    if check and completed.returncode != 0:
        raise RuntimeError(
            f"Command failed ({completed.returncode}): {' '.join(command)}\\n"
            + output[-5000:]
        )
    return completed


def _gpu_names() -> list[str]:
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=20, check=True,
        )
        return [line.strip() for line in result.stdout.splitlines() if line.strip()]
    except Exception:
        return []


def hardware_summary() -> dict[str, Any]:
    return {"platform": platform.platform(), "machine": platform.machine(), "gpu_names": _gpu_names()}


def default_gpu_list() -> str:
    names = _gpu_names()
    return ",".join(str(i) for i in range(len(names))) if names else "0"


def find_attached_dataset(owner: str, slug: str, marker: str | None = None) -> Path | None:
    exact = INPUT_ROOT / owner / slug
    if exact.is_dir() and (marker is None or (exact / marker).is_file()):
        return exact
    if not INPUT_ROOT.exists():
        return None
    marker_name = marker or "dataset-metadata.json"
    for candidate in INPUT_ROOT.rglob(marker_name):
        parent = candidate.parent
        if parent.name == slug and (parent.parent.name == owner or owner in parent.parts):
            return parent
    return None


def safe_extract_runtime(archive: Path, destination: Path) -> None:
    """Extract only known runtime paths and reject traversal or cross-tree links."""
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(archive, "r:") as tf:
        members = tf.getmembers()
        for member in members:
            name = PurePosixPath(member.name)
            if name.is_absolute() or ".." in name.parts:
                raise RuntimeError("Unsafe path in runtime archive: " + member.name)
            if not name.parts or name.parts[0] not in {"terminal", "components", "tools"}:
                raise RuntimeError("Unexpected runtime archive path: " + member.name)
            if member.issym() or member.islnk():
                link = PurePosixPath(member.linkname)
                if link.is_absolute():
                    raise RuntimeError("Unsafe absolute link in runtime archive: " + member.name)
                if member.issym():
                    resolved = PurePosixPath(posixpath.normpath(str(name.parent / link)))
                else:
                    resolved = PurePosixPath(posixpath.normpath(str(link)))
                if (not resolved.parts or resolved.parts[0] != name.parts[0]
                        or ".." in resolved.parts):
                    raise RuntimeError("Unsafe cross-tree link in runtime archive: " + member.name)
        tf.extractall(destination, members=members)


def restore_runtime_cache(owner: str, slug: str) -> bool:
    ds = find_attached_dataset(owner, slug, "strata-runtime-cache.bin")
    if not ds:
        log("Runtime cache not attached; Strata will be installed if needed.")
        return False
    archive = ds / "strata-runtime-cache.bin"
    if not archive.is_file():
        log("Runtime archive missing; skipping runtime restore.")
        return False
    checksum = ds / "strata-runtime-cache.bin.sha256"
    if checksum.is_file():
        expected = checksum.read_text(encoding="utf-8").strip().split()[0]
        if _sha256(archive) != expected:
            raise RuntimeError("Runtime cache checksum mismatch; refusing extraction.")
    manifest = ds / "runtime-manifest.json"
    if manifest.is_file():
        meta = json.loads(manifest.read_text(encoding="utf-8"))
        if meta.get("machine") and meta["machine"] != platform.machine():
            log("Runtime machine differs from cached build; skipping cache restore.")
            return False
        saved_gpus = meta.get("gpu_names") or []
        current_gpus = _gpu_names()
        if saved_gpus and current_gpus and saved_gpus != current_gpus:
            log("GPU differs from cache; restoring terminal but Strata may need a compatible engine.")
    log("Restoring Strata terminal and engine cache…")
    safe_extract_runtime(archive, STRATA_ROOT)
    STRATA_BIN.parent.mkdir(parents=True, exist_ok=True)
    target = STRATA_ROOT / "terminal" / "current" / "bin" / "strata"
    if not target.exists():
        matches = sorted((STRATA_ROOT / "terminal").glob("*/bin/strata"))
        if not matches:
            raise RuntimeError("No strata executable found in runtime archive.")
        target = matches[-1]
    STRATA_BIN.unlink(missing_ok=True)
    STRATA_BIN.symlink_to(target)
    os.environ["PATH"] = "/root/.local/bin:" + os.environ.get("PATH", "")
    run_command([str(STRATA_BIN), "--version"], timeout=60)
    saved_cloudflared = STRATA_ROOT / "tools" / "cloudflared"
    if saved_cloudflared.is_file() and not CLOUDFLARED_BIN.exists():
        CLOUDFLARED_BIN.parent.mkdir(parents=True, exist_ok=True)
        saved_cloudflared.chmod(0o755)
        CLOUDFLARED_BIN.symlink_to(saved_cloudflared)
    return True


def install_strata_if_missing() -> None:
    os.environ["PATH"] = "/root/.local/bin:" + os.environ.get("PATH", "")
    if shutil.which("strata"):
        run_command(["strata", "--version"], timeout=60)
        return
    installer = Path("/tmp/strata-install.sh")
    run_command(["curl", "-fsSL",
                 "https://github.com/Niko1221/Strata/releases/latest/download/install.sh",
                 "-o", str(installer)], timeout=180)
    run_command(["sh", str(installer)], timeout=900)
    os.environ["PATH"] = "/root/.local/bin:" + os.environ.get("PATH", "")
    if not shutil.which("strata"):
        raise RuntimeError("Strata installer completed but the command is not on PATH.")
    run_command(["strata", "--version"], timeout=60)


def _copy_verified(src: Path, dst: Path) -> tuple[int, bool]:
    expected = src.stat().st_size
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_file() and dst.stat().st_size == expected:
        return expected, False
    temp = dst.with_name(dst.name + ".part")
    temp.unlink(missing_ok=True)
    with src.open("rb") as inp, temp.open("wb") as out:
        shutil.copyfileobj(inp, out, length=8 * 1024 * 1024)
        out.flush()
        os.fsync(out.fileno())
    if temp.stat().st_size != expected:
        temp.unlink(missing_ok=True)
        raise RuntimeError("Size verification failed: " + src.name)
    temp.replace(dst)
    return expected, True


def restore_model_cache(owner: str, slug: str, data_dir: Path, workers: int = 8,
                        family: str | None = None, variant: str | None = None) -> bool:
    ds = find_attached_dataset(owner, slug, "manifest.json")
    if not ds:
        log("Model cache not attached; Strata will download the selected model on first launch.")
        return False
    try:
        manifest = json.loads((ds / "manifest.json").read_text(encoding="utf-8"))
    except Exception as exc:
        raise RuntimeError("Cannot read model-cache manifest.") from exc
    if manifest.get("format") != "devzonex.strata-model-cache.v1":
        log("Unrecognized model cache manifest; not restoring it.")
        return False
    saved = manifest.get("model", {})
    if family and saved.get("family") != family:
        raise RuntimeError("Attached model cache family does not match the selected family.")
    if variant and saved.get("variant") != variant:
        raise RuntimeError("Attached model cache variant does not match the selected variant.")
    entries = manifest.get("files", [])
    if not entries:
        raise RuntimeError("Model cache manifest is empty.")
    total = sum(int(e["size"]) for e in entries)
    log("Restoring " + str(len(entries)) + " model files (" + f"{total / (1024**3):.2f} GiB" + ").")
    data_dir.mkdir(parents=True, exist_ok=True)
    futures = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for item in entries:
            rel = PurePosixPath(item["relative_path"])
            if rel.is_absolute() or ".." in rel.parts:
                raise RuntimeError("Unsafe path in model manifest: " + str(rel))
            src, dst = ds / item["dataset_name"], data_dir.joinpath(*rel.parts)
            if not src.is_file() or src.stat().st_size != int(item["size"]):
                raise RuntimeError("Model cache file missing or size mismatch: " + item["dataset_name"])
            futures[pool.submit(_copy_verified, src, dst)] = item
        done = 0
        for future in concurrent.futures.as_completed(futures):
            future.result()
            done += 1
            if done == len(futures) or done % 3 == 0:
                log("Model restore progress: " + str(done) + "/" + str(len(futures)) + " files.")
    log("Model cache restored and size-verified.")
    return True


def _cached_model_path(data_dir: Path, family: str, variant: str) -> Path | None:
    """Find a compatible-looking local GGUF to prevent Strata redownloading restored models."""
    models_dir = data_dir / "models"
    if not models_dir.is_dir():
        return None
    files = [p for p in models_dir.rglob("*.gguf") if p.is_file() and not p.name.endswith(".part")]
    if not files:
        return None
    expected_folder = (family + "-" + variant).lower().replace("_", "-")
    matching = [p for p in files if expected_folder in p.parent.as_posix().lower().replace("_", "-")]
    if matching:
        return max(matching, key=lambda p: p.stat().st_size).parent
    parent_dirs = {p.parent for p in files}
    if len(parent_dirs) == 1:
        return next(iter(parent_dirs))
    raise RuntimeError(
        "Multiple cached GGUF model folders were found under " + str(models_dir) +
        ". Keep one selected model in this cache or choose a dedicated MODEL_DATA_DIR."
    )


def _model_source_args(data_dir: Path, family: str, variant: str) -> list[str]:
    cached = _cached_model_path(data_dir, family, variant)
    if cached:
        log("Using local model files at " + str(cached) + " (avoiding a new model download).")
        return ["--model-path", str(cached)]
    return ["--data-dir", str(data_dir)]


def run_plan(family: str, variant: str, context: str, vision: str,
             gpu_list: str, data_dir: Path) -> str:
    cmd = ["strata", "launch", "--plan", "--family", family, "--model", variant,
           *_model_source_args(data_dir, family, variant), "--context", context, "--vision", vision,
           "--mtp", "off", "--tune", "skip", "--access", "cloudflare",
           "--port", "8080", "--gpu", gpu_list]
    result = run_streaming(cmd, timeout=300, check=False)
    output = result.stdout or ""
    if result.returncode:
        raise RuntimeError("Strata plan failed. Choose a supported family/model variant.")
    return output


def launch_strata(family: str, variant: str, context: str, vision: str,
                  gpu_list: str, data_dir: Path) -> str:
    cmd = ["strata", "launch", "--family", family, "--model", variant,
           *_model_source_args(data_dir, family, variant), "--context", context, "--vision", vision,
           "--mtp", "off", "--tune", "skip", "--access", "cloudflare",
           "--port", "8080", "--gpu", gpu_list, "--yes", "--no-tui"]
    log("Launching Strata. First-time model/engine downloads may take a while.")
    result = run_streaming(cmd, timeout=3600, check=False)
    output = result.stdout or ""
    if result.returncode:
        raise RuntimeError("Strata launch failed. Inspect the redacted output above.")
    return output


def install_cloudflared_if_missing() -> None:
    os.environ["PATH"] = "/root/.local/bin:" + os.environ.get("PATH", "")
    if shutil.which("cloudflared"):
        return
    cached = STRATA_ROOT / "tools" / "cloudflared"
    CLOUDFLARED_BIN.parent.mkdir(parents=True, exist_ok=True)
    if cached.is_file():
        cached.chmod(0o755)
        CLOUDFLARED_BIN.unlink(missing_ok=True)
        CLOUDFLARED_BIN.symlink_to(cached)
        return
    machine = platform.machine().lower()
    asset = {"x86_64": "cloudflared-linux-amd64", "amd64": "cloudflared-linux-amd64",
             "aarch64": "cloudflared-linux-arm64", "arm64": "cloudflared-linux-arm64"}.get(machine)
    if not asset:
        raise RuntimeError("Unsupported cloudflared architecture: " + machine)
    run_command(["curl", "-fL", "--retry", "3",
                 "https://github.com/cloudflare/cloudflared/releases/latest/download/" + asset,
                 "-o", str(CLOUDFLARED_BIN)], timeout=600)
    CLOUDFLARED_BIN.chmod(0o755)
    run_command([str(CLOUDFLARED_BIN), "--version"], timeout=60)


def _read_key() -> str:
    result = subprocess.run(["strata", "launch", "--show-key"], text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=60, check=True)
    match = re.search(r"sk-strata-[A-Za-z0-9._~-]+", result.stdout or "")
    if not match:
        raise RuntimeError("Could not safely identify the Strata API key.")
    return match.group(0)


def wait_health(timeout_seconds: int = 900) -> dict[str, Any]:
    import requests
    deadline, last = time.time() + timeout_seconds, "no response"
    while time.time() < deadline:
        try:
            response = requests.get("http://127.0.0.1:8080/health", timeout=5)
            if response.ok:
                body = response.json()
                if body.get("loaded") is True:
                    if not body.get("api_key"):
                        raise RuntimeError("Strata has no API-key protection; refusing a public tunnel.")
                    log("Strata health is OK; model=" + str(body.get("model")))
                    return body
                last = "model not loaded yet"
            else:
                last = "HTTP " + str(response.status_code)
        except RuntimeError:
            raise
        except Exception as exc:
            last = str(exc)
        time.sleep(5)
    raise TimeoutError("Strata did not become healthy; last result: " + last)


def _extract_tunnel_url(text: str) -> str | None:
    match = re.search(r"https://[A-Za-z0-9-]+\.trycloudflare\.com", text)
    return match.group(0) if match else None


def start_quick_tunnel(existing_url: str | None = None, log_path: Path | None = None) -> str:
    if existing_url:
        log("Using HTTPS URL printed by Strata.")
        return existing_url
    install_cloudflared_if_missing()
    log_path = log_path or (WORKING / "cloudflared.log")
    if log_path.exists():
        previous = _extract_tunnel_url(log_path.read_text(encoding="utf-8", errors="replace"))
        try:
            import requests
            if previous and requests.get(previous + "/health", timeout=8).status_code in (200, 401, 403):
                log("Reusing URL from the existing Cloudflare log.")
                return previous
        except Exception:
            pass
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w", encoding="utf-8") as output:
        process = subprocess.Popen(
            [str(CLOUDFLARED_BIN), "tunnel", "--no-autoupdate",
             "--url", "http://127.0.0.1:8080"],
            stdout=output, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
            start_new_session=True, text=True,
        )
    for _ in range(60):
        time.sleep(2)
        if process.poll() is not None:
            raise RuntimeError("cloudflared exited early; inspect " + str(log_path))
        url = _extract_tunnel_url(log_path.read_text(encoding="utf-8", errors="replace"))
        if url:
            log("Cloudflare Quick Tunnel started. URL: " + url)
            return url
    raise RuntimeError("No trycloudflare.com URL appeared. Inspect " + str(log_path))


def verify_public_endpoint(public_url: str, expected_model: str | None = None) -> dict[str, Any]:
    import requests
    base, key = public_url.rstrip("/"), _read_key()
    unauth = requests.get(base + "/v1/models", timeout=20)
    if unauth.status_code not in (401, 403):
        raise RuntimeError("Unauthenticated /v1/models returned HTTP " + str(unauth.status_code) +
                           "; expected 401/403. Stop the tunnel and secure the server.")
    headers = {"Authorization": "Bearer " + key}
    response = requests.get(base + "/v1/models", headers=headers, timeout=30)
    if not response.ok:
        raise RuntimeError("Authenticated /v1/models failed: HTTP " + str(response.status_code) +
                           ": " + redact(response.text[:1000]))
    rows = response.json().get("data", [])
    available = [x.get("id") for x in rows if isinstance(x, dict) and x.get("id")]
    model_id = expected_model if expected_model in available else (available[0] if available else expected_model)
    if not model_id:
        raise RuntimeError("Strata did not advertise a model ID from /v1/models.")
    log("Unauthenticated request rejected with HTTP " + str(unauth.status_code) + ".")
    log("Sending short authenticated generation test…")
    chat = requests.post(
        base + "/v1/chat/completions", headers={**headers, "Content-Type": "application/json"},
        json={"model": model_id, "messages": [{"role": "user", "content": "Reply with exactly: Strata connection working."}],
              "max_tokens": 32, "reasoning_effort": "none", "stream": False},
        timeout=240,
    )
    if not chat.ok:
        raise RuntimeError("Authenticated chat test failed: HTTP " + str(chat.status_code) + ": " + redact(chat.text[:1500]))
    body = chat.json()
    choices = body.get("choices", [])
    answer = choices[0].get("message", {}).get("content", "") if choices else ""
    if isinstance(answer, list):
        answer = "".join(part.get("text", "") for part in answer if isinstance(part, dict))
    print("Authenticated test response: " + str(answer))
    print("OpenCode base URL: " + base + "/v1")
    print("API key was not printed. Retrieve it privately using: strata launch --show-key")
    return {"model_id": model_id, "url": base, "unauthenticated_status": unauth.status_code,
            "authenticated_status": chat.status_code}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_dataset_metadata(stage: Path, username: str, slug: str, title: str, description: str) -> None:
    metadata = {"title": title, "id": username + "/" + slug,
                "licenses": [{"name": "other"}],
                "description": description + " Components/model files retain upstream terms. Private by default."}
    (stage / "dataset-metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")


def _upload_create_or_version(stage: Path, username: str, slug: str,
                              env: dict[str, str], message: str) -> None:
    cmd = ["kaggle", "datasets", "create", "-p", str(stage), "--dir-mode", "skip"]
    result = subprocess.run(cmd, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            timeout=7200, env=env, check=False)
    output = redact(result.stdout or "")
    print(output, end="" if output.endswith("\n") else "\n")
    if result.returncode == 0:
        log("Upload submitted for " + username + "/" + slug + ". Check Kaggle's processing status.")
        return
    lower = output.lower()
    exists = any(x in lower for x in ("already exists", "dataset already", "duplicate slug",
                                       "409 client error", "slug is already taken"))
    if not exists:
        raise RuntimeError("Kaggle dataset creation failed: " + output[-4000:])
    version = subprocess.run(
        ["kaggle", "datasets", "version", "-p", str(stage), "-m", message, "--dir-mode", "skip"],
        text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=7200, env=env, check=False,
    )
    version_output = redact(version.stdout or "")
    print(version_output, end="" if version_output.endswith("\n") else "\n")
    if version.returncode:
        raise RuntimeError("Kaggle dataset version failed: " + version_output[-4000:])
    log("New private dataset version submitted. Wait for Kaggle processing to finish.")


def _clean_stage(stage: Path) -> None:
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True, exist_ok=True)


def upload_model_cache(data_dir: Path, username: str, slug: str, family: str, variant: str,
                       env: dict[str, str], license_confirmed: bool, force: bool = False) -> bool:
    if not license_confirmed:
        log("Skipped model upload. Confirm the model terms and enable the explicit license flag first.")
        return False
    allowed_roots = {"models", "packs", "mtp"}
    files = sorted(
        p for p in data_dir.rglob("*")
        if p.is_file() and not p.is_symlink() and not p.name.endswith(".part")
        and p.relative_to(data_dir).parts and p.relative_to(data_dir).parts[0] in allowed_roots
    )
    if not files:
        raise RuntimeError("No model/packs/mtp files found under " + str(data_dir) + ".")
    attached = find_attached_dataset(username, slug, "manifest.json")
    sizes = {p.relative_to(data_dir).as_posix(): p.stat().st_size for p in files}
    if attached and not force:
        try:
            old = json.loads((attached / "manifest.json").read_text(encoding="utf-8"))
            old_sizes = {x["relative_path"]: int(x["size"]) for x in old.get("files", [])}
            if old_sizes == sizes and old.get("model") == {"family": family, "variant": variant}:
                log("Private model dataset already matches local files; skipping upload.")
                return False
        except Exception:
            pass
    stage = WORKING / "strata-model-dataset-stage"
    _clean_stage(stage)
    entries = []
    for number, path in enumerate(files, 1):
        relative = path.relative_to(data_dir).as_posix()
        name = f"{number:04d}__" + re.sub(r"[^A-Za-z0-9._-]+", "__", relative.replace("/", "__"))
        (stage / name).symlink_to(path)
        entries.append({"dataset_name": name, "relative_path": relative, "size": path.stat().st_size})
    manifest = {"format": "devzonex.strata-model-cache.v1",
                "model": {"family": family, "variant": variant}, "files": entries}
    (stage / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    _write_dataset_metadata(stage, username, slug, "DevZoneX Strata Model Cache",
                            f"Personal private cache for Strata-supported {family}/{variant} model data.")
    total = sum(item["size"] for item in entries)
    log(f"Preparing {len(entries)} model files ({total / (1024**3):.2f} GiB) for private upload.")
    _upload_create_or_version(stage, username, slug, env, f"Update Strata model cache: {family}/{variant}")
    return True


def upload_runtime_cache(username: str, slug: str, env: dict[str, str], force: bool = False) -> bool:
    if not (STRATA_ROOT / "terminal").exists() or not (STRATA_ROOT / "components").exists():
        log("Runtime upload skipped: terminal/components directory missing.")
        return False
    attached = find_attached_dataset(username, slug, "strata-runtime-cache.bin")
    version = subprocess.run(["strata", "--version"], text=True, stdout=subprocess.PIPE,
                             stderr=subprocess.STDOUT, timeout=60, check=False).stdout.strip()
    hw = hardware_summary()
    engine_dirs = sorted(p.name for p in (STRATA_ROOT / "components" / "engine").glob("*") if p.is_dir())
    cloudflared_cmd = shutil.which("cloudflared")
    cloudflared_version = None
    if cloudflared_cmd:
        v = subprocess.run([cloudflared_cmd, "--version"], text=True, stdout=subprocess.PIPE,
                           stderr=subprocess.STDOUT, timeout=60, check=False)
        cloudflared_version = (v.stdout or "").strip()
    if attached and not force:
        try:
            old = json.loads((attached / "runtime-manifest.json").read_text(encoding="utf-8"))
            if (old.get("strata_version") == version and old.get("machine") == hw["machine"]
                    and old.get("gpu_names") == hw["gpu_names"] and old.get("engine_dirs", []) == engine_dirs
                    and old.get("cloudflared_version") == cloudflared_version):
                log("Runtime dataset matches installed terminal/engine; skipping upload.")
                return False
        except Exception:
            pass
    stage = WORKING / "strata-runtime-dataset-stage"
    _clean_stage(stage)
    archive = stage / "strata-runtime-cache.bin"
    log("Packaging Strata terminal and engine cache (model data remains separate)…")
    with tarfile.open(archive, "w:") as tf:
        tf.add(STRATA_ROOT / "terminal", arcname="terminal", recursive=True)
        tf.add(STRATA_ROOT / "components", arcname="components", recursive=True)
        if cloudflared_cmd:
            tf.add(Path(cloudflared_cmd).resolve(), arcname="tools/cloudflared", recursive=False)
    (stage / "strata-runtime-cache.bin.sha256").write_text(
        _sha256(archive) + "  strata-runtime-cache.bin\n", encoding="utf-8")
    meta = {"format": "devzonex.strata-runtime-cache.v1", "strata_version": version,
            **hw, "engine_dirs": engine_dirs, "cloudflared_version": cloudflared_version,
            "contents": ["terminal", "components", "tools/cloudflared (if present)"]}
    (stage / "runtime-manifest.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    _write_dataset_metadata(stage, username, slug, "DevZoneX Strata Runtime Cache",
                            "Private runtime cache for Strata terminal and engine components.")
    log(f"Runtime archive size: {archive.stat().st_size / (1024**3):.2f} GiB.")
    _upload_create_or_version(stage, username, slug, env, "Update Strata terminal and engine cache")
    return True


def opencode_config_snippet(public_url: str, model_id: str,
                            provider_package: str = "@opencode/ai/providers/openai-compatible") -> str:
    provider = {
        "name": "Strata Kaggle", "package": provider_package,
        "settings": {"baseURL": public_url.rstrip("/") + "/v1",
                     "apiKey": "{file:~/.config/opencode/strata-key.txt}",
                     "encoding": "none", "timeout": 600000, "headerTimeout": 120000,
                     "chunkTimeout": 300000},
        "models": {model_id: {"name": model_id, "modelID": model_id,
                              "capabilities": {"tools": True, "input": ["text"], "output": ["text"]},
                              "limit": {"context": 32768, "output": 8192}}},
    }
    return json.dumps({"strata": provider}, indent=2)
