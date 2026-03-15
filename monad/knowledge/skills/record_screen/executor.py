"""
record_screen skill — 后台录制屏幕为 mp4

用法：
    record_screen(action="start")                          # 开始录制
    record_screen(action="start", output_path="/tmp/demo.mp4")
    record_screen(action="stop")                           # 停止录制，返回文件路径
    record_screen(action="status")                         # 查询状态
"""

import json
import os
import shutil
import signal
import subprocess
import time
from datetime import datetime
from pathlib import Path

_CACHE_FILE = Path.home() / ".monad" / "cache" / "record_screen.json"
_DEFAULT_OUTPUT_DIR = Path.home() / ".monad" / "output"
_FFMPEG = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"


def _save_state(pid: int, output_path: str, start_time: float):
    _CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    _CACHE_FILE.write_text(json.dumps({
        "pid": pid,
        "output_path": output_path,
        "start_time": start_time,
    }))


def _load_state() -> dict | None:
    if not _CACHE_FILE.exists():
        return None
    try:
        return json.loads(_CACHE_FILE.read_text())
    except Exception:
        return None


def _clear_state():
    if _CACHE_FILE.exists():
        _CACHE_FILE.unlink()


def _is_running(pid: int) -> bool:
    try:
        os.kill(pid, 0)
        return True
    except (ProcessLookupError, PermissionError):
        return False


def run(action: str = "status", output_path: str = "") -> str:
    action = action.strip().lower()

    if action == "start":
        state = _load_state()
        if state and _is_running(state["pid"]):
            return (
                f'⚠️ 已有录制进行中 (pid={state["pid"]})，'
                f'输出: {state["output_path"]}。'
                f'请先调用 stop 停止当前录制。'
            )

        _DEFAULT_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        if not output_path:
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = str(_DEFAULT_OUTPUT_DIR / f"recording_{ts}.mp4")

        cmd = [
            _FFMPEG,
            "-f", "avfoundation",
            "-framerate", "30",
            "-i", "1:0",          # screen 0, system audio (index 0)
            "-vcodec", "libx264",
            "-preset", "ultrafast",
            "-crf", "28",
            "-acodec", "aac",
            "-y",
            output_path,
        ]

        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
        )
        time.sleep(1.0)

        if proc.poll() is not None:
            return (
                "❌ ffmpeg 启动失败，可能原因：\n"
                "1. 未授权屏幕录制权限（系统偏好设置 → 隐私与安全性 → 屏幕录制 → 勾选终端/Python）\n"
                "2. ffmpeg 未安装（brew install ffmpeg）"
            )

        _save_state(proc.pid, output_path, time.time())
        return (
            f"🎬 录制已开始 (pid={proc.pid})\n"
            f"输出文件: {output_path}\n"
            f"调用 record_screen(action='stop') 停止录制。"
        )

    elif action == "stop":
        state = _load_state()
        if not state:
            return "⚠️ 没有正在进行的录制。"

        pid = state["pid"]
        output_path = state["output_path"]

        if not _is_running(pid):
            _clear_state()
            if Path(output_path).exists():
                return f"录制进程已结束，文件已保存: {output_path}"
            return "⚠️ 录制进程已结束，但未找到输出文件。"

        try:
            os.kill(pid, signal.SIGTERM)
            for _ in range(30):
                time.sleep(0.5)
                if not _is_running(pid):
                    break
            else:
                os.kill(pid, signal.SIGKILL)
                time.sleep(1)
        except Exception as e:
            return f"❌ 停止录制失败: {e}"

        _clear_state()

        if Path(output_path).exists():
            size_mb = Path(output_path).stat().st_size / 1024 / 1024
            duration = int(time.time() - state["start_time"])
            return (
                f"✅ 录制已停止\n"
                f"文件: {output_path}\n"
                f"时长: {duration} 秒 | 大小: {size_mb:.1f} MB"
            )
        return f"⚠️ 录制已停止，但未找到输出文件: {output_path}"

    elif action == "status":
        state = _load_state()
        if not state:
            return "📹 当前没有正在进行的录制。"
        pid = state["pid"]
        if _is_running(pid):
            duration = int(time.time() - state["start_time"])
            return (
                f"🔴 正在录制中 (pid={pid})\n"
                f"已录制: {duration} 秒\n"
                f"输出文件: {state['output_path']}"
            )
        else:
            _clear_state()
            return f"📹 录制进程已结束，文件: {state['output_path']}"

    else:
        return f"❌ 未知操作: {action}。支持: start / stop / status"
