"""Tests for web interface: filename sanitization, upload limits."""

import pytest

from monad.interface.web import _sanitize_upload_filename


class TestSanitizeUploadFilename:

    def test_normal_filename(self):
        assert _sanitize_upload_filename("report.pdf") == "report.pdf"

    def test_none_returns_default(self):
        assert _sanitize_upload_filename(None) == "upload.bin"

    def test_empty_string_returns_default(self):
        assert _sanitize_upload_filename("") == "upload.bin"

    def test_whitespace_only_returns_default(self):
        assert _sanitize_upload_filename("   ") == "upload.bin"

    def test_dot_dot_traversal_stripped(self):
        result = _sanitize_upload_filename("../../etc/passwd")
        assert ".." not in result
        assert result == "passwd"

    def test_path_separator_stripped(self):
        result = _sanitize_upload_filename("foo/bar/baz.txt")
        assert "/" not in result
        assert result == "baz.txt"

    def test_null_byte_stripped(self):
        result = _sanitize_upload_filename("file\x00name.txt")
        assert "\x00" not in result

    def test_dot_returns_default(self):
        assert _sanitize_upload_filename(".") == "upload.bin"

    def test_dotdot_returns_default(self):
        assert _sanitize_upload_filename("..") == "upload.bin"

    def test_very_long_name_truncated(self):
        long_name = "a" * 300 + ".txt"
        result = _sanitize_upload_filename(long_name, max_component_len=50)
        assert len(result) <= 50

    def test_unicode_filename(self):
        assert _sanitize_upload_filename("文件.pdf") == "文件.pdf"


class TestUploadEndpoint:
    """Smoke tests for upload endpoint logic (via test client)."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from monad.interface.web import app
        return TestClient(app)

    def test_upload_small_file(self, client, tmp_path, monkeypatch):
        from monad.config import CONFIG
        monkeypatch.setattr(CONFIG, "root_dir", tmp_path)
        (tmp_path / "input").mkdir(parents=True, exist_ok=True)
        data = b"hello world"
        resp = client.post("/upload", files={"file": ("test.txt", data)})
        assert resp.status_code == 200
        body = resp.json()
        assert body["filename"] == "test.txt"
        assert body["size"] == len(data)

    def test_upload_traversal_blocked(self, client, tmp_path, monkeypatch):
        from monad.config import CONFIG
        monkeypatch.setattr(CONFIG, "root_dir", tmp_path)
        (tmp_path / "input").mkdir(parents=True, exist_ok=True)
        resp = client.post("/upload", files={"file": ("../../etc/passwd", b"x")})
        assert resp.status_code == 200
        body = resp.json()
        assert ".." not in body["filename"]
