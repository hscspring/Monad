"""
Unit tests for record_screen skill.
Tests run without actually launching ffmpeg (mocked).
"""
import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "monad" / "knowledge" / "skills" / "record_screen"))
import executor as skill


class TestRecordScreenStatus:
    def test_status_no_recording(self, tmp_path, monkeypatch):
        monkeypatch.setattr(skill, "_CACHE_FILE", tmp_path / "record_screen.json")
        result = skill.run(action="status")
        assert "没有" in result or "no" in result.lower()

    def test_status_running(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "record_screen.json"
        monkeypatch.setattr(skill, "_CACHE_FILE", cache_file)
        cache_file.write_text(json.dumps({
            "pid": 99999,
            "output_path": "/tmp/test.mp4",
            "start_time": time.time() - 5,
        }))
        with patch("executor._is_running", return_value=True):
            result = skill.run(action="status")
        assert "正在录制" in result
        assert "pid=99999" in result

    def test_status_pid_dead_clears_cache(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "record_screen.json"
        monkeypatch.setattr(skill, "_CACHE_FILE", cache_file)
        cache_file.write_text(json.dumps({
            "pid": 99999,
            "output_path": "/tmp/test.mp4",
            "start_time": time.time() - 10,
        }))
        with patch("executor._is_running", return_value=False):
            result = skill.run(action="status")
        assert not cache_file.exists()


class TestRecordScreenStart:
    def test_start_success(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "record_screen.json"
        monkeypatch.setattr(skill, "_CACHE_FILE", cache_file)
        monkeypatch.setattr(skill, "_DEFAULT_OUTPUT_DIR", tmp_path)

        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_proc.poll.return_value = None  # still running

        with patch("subprocess.Popen", return_value=mock_proc), \
             patch("time.sleep"):
            result = skill.run(action="start", output_path=str(tmp_path / "out.mp4"))

        assert "录制已开始" in result
        assert "12345" in result
        assert cache_file.exists()
        state = json.loads(cache_file.read_text())
        assert state["pid"] == 12345

    def test_start_ffmpeg_fails(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "record_screen.json"
        monkeypatch.setattr(skill, "_CACHE_FILE", cache_file)
        monkeypatch.setattr(skill, "_DEFAULT_OUTPUT_DIR", tmp_path)

        mock_proc = MagicMock()
        mock_proc.pid = 0
        mock_proc.poll.return_value = 1  # process exited immediately

        with patch("subprocess.Popen", return_value=mock_proc), \
             patch("time.sleep"):
            result = skill.run(action="start", output_path=str(tmp_path / "out.mp4"))

        assert "失败" in result or "failed" in result.lower()

    def test_start_when_already_recording(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "record_screen.json"
        monkeypatch.setattr(skill, "_CACHE_FILE", cache_file)
        cache_file.write_text(json.dumps({
            "pid": 99999,
            "output_path": "/tmp/existing.mp4",
            "start_time": time.time(),
        }))
        with patch("executor._is_running", return_value=True):
            result = skill.run(action="start")
        assert "已有录制" in result or "stop" in result.lower()


class TestRecordScreenStop:
    def test_stop_no_recording(self, tmp_path, monkeypatch):
        monkeypatch.setattr(skill, "_CACHE_FILE", tmp_path / "record_screen.json")
        result = skill.run(action="stop")
        assert "没有" in result or "no" in result.lower()

    def test_stop_success(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "record_screen.json"
        monkeypatch.setattr(skill, "_CACHE_FILE", cache_file)

        output_file = tmp_path / "out.mp4"
        output_file.write_bytes(b"x" * 1024 * 512)  # 0.5 MB fake file

        cache_file.write_text(json.dumps({
            "pid": 99999,
            "output_path": str(output_file),
            "start_time": time.time() - 10,
        }))

        with patch("executor._is_running", side_effect=[True, False]), \
             patch("os.kill"), \
             patch("time.sleep"):
            result = skill.run(action="stop")

        assert "录制已停止" in result
        assert str(output_file) in result
        assert not cache_file.exists()

    def test_stop_process_already_dead(self, tmp_path, monkeypatch):
        cache_file = tmp_path / "record_screen.json"
        monkeypatch.setattr(skill, "_CACHE_FILE", cache_file)

        output_file = tmp_path / "out.mp4"
        output_file.write_bytes(b"data")

        cache_file.write_text(json.dumps({
            "pid": 99999,
            "output_path": str(output_file),
            "start_time": time.time() - 5,
        }))

        with patch("executor._is_running", return_value=False):
            result = skill.run(action="stop")

        assert "已结束" in result or "saved" in result.lower() or str(output_file) in result


class TestRecordScreenUnknownAction:
    def test_unknown_action(self, tmp_path, monkeypatch):
        monkeypatch.setattr(skill, "_CACHE_FILE", tmp_path / "record_screen.json")
        result = skill.run(action="foobar")
        assert "未知" in result or "unknown" in result.lower()
