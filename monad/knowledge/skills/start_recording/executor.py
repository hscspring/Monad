"""
start_recording skill — 后台启动屏幕录制（MKV 格式）

MKV 容器天生支持强制终止后仍可播放，无需 moov atom 优雅写入。
录制状态持久化到 ~/.monad/cache/recording_state.json，供 stop_recording 跨进程使用。

用法：
    start_recording()
    start_recording(output_path="/tmp/demo.mkv")
"""

import json
import os
import shutil
import subprocess
import time
from datetime import datetime
from pathlib import Path

_STATE_FILE = Path.home() / ".monad" / "cache" / "recording_state.json"
_DEFAULT_OUTPUT_DIR = Path.home() / ".monad" / "output"
_FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def run(output_path: str = "") -> str:
    # Check for existing recording
    if _STATE_FILE.exists():
        try:
            state = json.loads(_STATE_FILE.read_text())
            if _is_running(state["pid"]):
                return (
                    f'⚠️ 已有录制进行中 (pid={state["pid"]})，'
                    f'输出: {state["mkv_path"]}。\n'
                    f'请先调用 stop_recording 停止当前录制。'
                )
        except Exception:
            pass

    _DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    if not output_path:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(_DEFAULT_OUTPUT_DIR / f"recording_{ts}.mkv")
    elif not output_path.endswith(".mkv"):
        output_path = output_path.rsplit(".", 1)[0] + ".mkv"

    cmd = [
        _FFMPEG,
        "-f", "avfoundation",
        "-framerate", "30",
        "-i", "1:0",           # Capture screen 0 + system audio 0
        "-vcodec", "libx264",
        "-preset", "ultrafast",
        "-crf", "28",
        "-acodec", "aac",
        # MKV: no moov atom needed — safe to SIGKILL at any time
        "-y",
        output_path,
    ]

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
    )
    time.sleep(1.5)

    if proc.poll() is not None:
        return (
            "❌ ffmpeg 启动失败，可能原因：\n"
            "1. 未授权屏幕录制权限（系统偏好设置 → 隐私与安全性 → 屏幕录制 → 勾选终端/Python）\n"
            "2. ffmpeg 未安装（brew install ffmpeg）"
        )

    _STATE_FILE.write_text(json.dumps({
        "pid": proc.pid,
        "mkv_path": output_path,
        "start_time": time.time(),
    }))

    return (
        f"🎬 录制已开始 (pid={proc.pid})\n"
        f"临时文件: {output_path}\n"
        f"调用 stop_recording() 停止录制并生成 MP4。"
    )
