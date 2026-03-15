"""
Unit tests for start_recording and stop_recording skills.
All ffmpeg calls are mocked — no actual screen capture.
"""
import importlib.util
import json
import os
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


def load_skill(name, base="/Users/Yam/Yam/Monad/monad/knowledge/skills"):
    path = f"{base}/{name}/executor.py"
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


# ---------------------------------------------------------------------------
# start_recording
# ---------------------------------------------------------------------------

class TestStartRecording:
    def setup_method(self):
        self.start = load_skill("start_recording")

    def test_start_success(self, tmp_path, monkeypatch):
        state_file = tmp_path / "recording_state.json"
        monkeypatch.setattr(self.start, "_STATE_FILE", state_file)
        monkeypatch.setattr(self.start, "_DEFAULT_OUTPUT_DIR", tmp_path)

        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None

        with patch("subprocess.Popen", return_value=mock_proc), patch("time.sleep"):
            result = self.start.run(output_path=str(tmp_path / "out.mkv"))

        assert "录制已开始" in result
        assert "12345" in result
        assert state_file.exists()
        state = json.loads(state_file.read_text())
        assert state["pid"] == 12345
        assert state["mkv_path"].endswith(".mkv")

    def test_start_forces_mkv_extension(self, tmp_path, monkeypatch):
        state_file = tmp_path / "recording_state.json"
        monkeypatch.setattr(self.start, "_STATE_FILE", state_file)
        monkeypatch.setattr(self.start, "_DEFAULT_OUTPUT_DIR", tmp_path)

        mock_proc = MagicMock()
        mock_proc.pid = 99
        mock_proc.poll.return_value = None

        with patch("subprocess.Popen", return_value=mock_proc), patch("time.sleep"):
            result = self.start.run(output_path=str(tmp_path / "demo.mp4"))

        state = json.loads(state_file.read_text())
        assert state["mkv_path"].endswith(".mkv")

    def test_start_ffmpeg_fails(self, tmp_path, monkeypatch):
        state_file = tmp_path / "recording_state.json"
        monkeypatch.setattr(self.start, "_STATE_FILE", state_file)
        monkeypatch.setattr(self.start, "_DEFAULT_OUTPUT_DIR", tmp_path)

        mock_proc = MagicMock()
        mock_proc.pid = 0
        mock_proc.poll.return_value = 1  # exited immediately

        with patch("subprocess.Popen", return_value=mock_proc), patch("time.sleep"):
            result = self.start.run(output_path=str(tmp_path / "out.mkv"))

        assert "失败" in result or "failed" in result.lower()
        assert not state_file.exists()

    def test_start_when_already_recording(self, tmp_path, monkeypatch):
        state_file = tmp_path / "recording_state.json"
        monkeypatch.setattr(self.start, "_STATE_FILE", state_file)
        state_file.write_text(json.dumps({
            "pid": 99999, "mkv_path": "/tmp/x.mkv", "start_time": time.time()
        }))
        with patch.object(self.start, "_is_running", return_value=True):
            result = self.start.run()
        assert "已有录制" in result


# ---------------------------------------------------------------------------
# stop_recording
# ---------------------------------------------------------------------------

class TestStopRecording:
    def setup_method(self):
        self.stop = load_skill("stop_recording")

    def test_stop_no_recording(self, tmp_path, monkeypatch):
        monkeypatch.setattr(self.stop, "_STATE_FILE", tmp_path / "recording_state.json")
        result = self.stop.run()
        assert "没有" in result

    def test_stop_success(self, tmp_path, monkeypatch):
        state_file = tmp_path / "recording_state.json"
        monkeypatch.setattr(self.stop, "_STATE_FILE", state_file)
        monkeypatch.setattr(self.stop, "_DEFAULT_OUTPUT_DIR", tmp_path)

        mkv = tmp_path / "out.mkv"
        mkv.write_bytes(b"fake mkv data" * 100)
        mp4 = tmp_path / "out.mp4"

        state_file.write_text(json.dumps({
            "pid": 99999,
            "mkv_path": str(mkv),
            "start_time": time.time() - 10,
        }))

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch.object(self.stop, "_is_running", return_value=True), \
             patch("os.kill"), patch("time.sleep"), \
             patch("subprocess.run", return_value=mock_result):
            # Simulate ffmpeg creating the mp4
            mp4.write_bytes(b"fake mp4 data" * 200)
            result = self.stop.run()

        assert "录制已停止" in result
        assert str(mp4) in result
        assert "下载链接" in result
        assert not state_file.exists()

    def test_stop_corrupt_state(self, tmp_path, monkeypatch):
        state_file = tmp_path / "recording_state.json"
        monkeypatch.setattr(self.stop, "_STATE_FILE", state_file)
        state_file.write_text("not valid json{{{")
        result = self.stop.run()
        assert "损坏" in result or "error" in result.lower()
        assert not state_file.exists()

    def test_stop_transcode_fails(self, tmp_path, monkeypatch):
        state_file = tmp_path / "recording_state.json"
        monkeypatch.setattr(self.stop, "_STATE_FILE", state_file)
        monkeypatch.setattr(self.stop, "_DEFAULT_OUTPUT_DIR", tmp_path)

        mkv = tmp_path / "out.mkv"
        mkv.write_bytes(b"fake data")

        state_file.write_text(json.dumps({
            "pid": 99999,
            "mkv_path": str(mkv),
            "start_time": time.time() - 5,
        }))

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = b"some ffmpeg error"

        with patch.object(self.stop, "_is_running", return_value=True), \
             patch("os.kill"), patch("time.sleep"), \
             patch("subprocess.run", return_value=mock_result):
            result = self.stop.run()

        assert "转码失败" in result or "failed" in result.lower()

    def test_stop_process_already_dead(self, tmp_path, monkeypatch):
        state_file = tmp_path / "recording_state.json"
        monkeypatch.setattr(self.stop, "_STATE_FILE", state_file)
        monkeypatch.setattr(self.stop, "_DEFAULT_OUTPUT_DIR", tmp_path)

        mkv = tmp_path / "out.mkv"
        mkv.write_bytes(b"data")
        mp4 = tmp_path / "out.mp4"
        mp4.write_bytes(b"mp4 data" * 100)

        state_file.write_text(json.dumps({
            "pid": 99999,
            "mkv_path": str(mkv),
            "start_time": time.time() - 8,
        }))

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch.object(self.stop, "_is_running", return_value=False), \
             patch("subprocess.run", return_value=mock_result), \
             patch("time.sleep"):
            result = self.stop.run()

        assert "录制已停止" in result or str(mp4) in result

    def test_file_url_inside_output_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(self.stop, "_DEFAULT_OUTPUT_DIR", tmp_path)
        mp4 = str(tmp_path / "recording_20260315.mp4")
        url = self.stop._file_url(mp4)
        assert url.startswith("http://localhost:")
        assert "recording_20260315.mp4" in url

    def test_file_url_outside_output_dir(self, tmp_path, monkeypatch):
        monkeypatch.setattr(self.stop, "_DEFAULT_OUTPUT_DIR", tmp_path)
        url = self.stop._file_url("/tmp/other.mp4")
        assert url.startswith("file://")
