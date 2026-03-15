"""
stop_recording skill — 停止录制并将 MKV 转码为可播放的 MP4

MKV 无 moov atom 问题，SIGTERM/SIGKILL 后仍可读取。
转码步骤保证最终 MP4 的 moov atom 完整，在任何播放器和浏览器中都可播放。

用法：
    stop_recording()
"""

import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

_STATE_FILE = Path.home() / ".monad" / "cache" / "recording_state.json"
_DEFAULT_OUTPUT_DIR = Path.home() / ".monad" / "output"
_FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
_WEB_PORT = int(os.environ.get("MONAD_WEB_PORT", "8000"))


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def _file_url(mp4_path: str) -> str:
    try:
        rel = Path(mp4_path).relative_to(_DEFAULT_OUTPUT_DIR)
        return f"http://localhost:{_WEB_PORT}/output/{rel}"
    except ValueError:
        return f"file://{mp4_path}"


def run() -> str:
    if not _STATE_FILE.exists():
        return "⚠️ 没有正在进行的录制。请先调用 start_recording()。"

    try:
        state = json.loads(_STATE_FILE.read_text())
    except Exception:
        _STATE_FILE.unlink(missing_ok=True)
        return "⚠️ 录制状态文件损坏，已清理。"

    pid = state["pid"]
    mkv_path = state["mkv_path"]
    start_time = state["start_time"]

    # --- Step 1: Stop the ffmpeg process ---
    if _is_running(pid):
        try:
            os.kill(pid, signal.SIGTERM)
            for _ in range(20):
                time.sleep(0.5)
                if not _is_running(pid):
                    break
            else:
                # Still running after 10s — force kill (MKV is still recoverable)
                os.kill(pid, signal.SIGKILL)
                time.sleep(1)
        except Exception as e:
            _STATE_FILE.unlink(missing_ok=True)
            return f"❌ 停止录制失败: {e}"

    # Clean state immediately after stopping
    _STATE_FILE.unlink(missing_ok=True)
    time.sleep(0.5)

    if not Path(mkv_path).exists():
        return f"⚠️ 未找到录制文件: {mkv_path}"

    # --- Step 2: Transcode MKV → MP4 (guarantees valid moov atom) ---
    mp4_path = mkv_path.replace(".mkv", ".mp4")
    transcode_cmd = [
        _FFMPEG,
        "-i", mkv_path,
        "-vcodec", "copy",     # stream copy — fast, no re-encoding
        "-acodec", "copy",
        "-movflags", "+faststart",  # moov atom at file start for streaming
        "-y",
        mp4_path,
    ]

    try:
        result = subprocess.run(
            transcode_cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=120,
        )
        if result.returncode != 0:
            err = result.stderr.decode(errors="ignore")[-300:]
            return f"❌ 转码失败 (ffmpeg exit {result.returncode}):\n{err}"
    except subprocess.TimeoutExpired:
        return "❌ 转码超时（120s），请手动转码：ffmpeg -i {mkv_path} -c copy {mp4_path}"
    except Exception as e:
        return f"❌ 转码异常: {e}"

    # --- Step 3: Clean up MKV, return MP4 info ---
    try:
        Path(mkv_path).unlink()
    except Exception:
        pass

    if not Path(mp4_path).exists():
        return f"⚠️ 转码完成但未找到 MP4 文件: {mp4_path}"

    size_mb = Path(mp4_path).stat().st_size / 1024 / 1024
    duration = int(time.time() - start_time)
    url = _file_url(mp4_path)

    return (
        f"✅ 录制已停止，MP4 已生成\n"
        f"文件: {mp4_path}\n"
        f"时长: {duration} 秒 | 大小: {size_mb:.1f} MB\n"
        f"下载链接: {url}"
    )
