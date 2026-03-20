"""Tests for TaskState — shared state dict for a single task execution."""

from monad.execution.context import TaskState


class TestStore:

    def test_first_store_creates_step_1(self):
        ts = TaskState()
        key = ts.store("web_fetch", "page content")
        assert key == "step_1_web_fetch"
        assert ts[key] == "page content"

    def test_counter_increments(self):
        ts = TaskState()
        k1 = ts.store("web_fetch", "a")
        k2 = ts.store("python_exec", "b")
        k3 = ts.store("web_fetch", "c")
        assert k1 == "step_1_web_fetch"
        assert k2 == "step_2_python_exec"
        assert k3 == "step_3_web_fetch"

    def test_stores_full_content(self):
        ts = TaskState()
        big = "x" * 100_000
        ts.store("web_fetch", big)
        assert len(ts["step_1_web_fetch"]) == 100_000


class TestLatest:

    def test_latest_returns_most_recent(self):
        ts = TaskState()
        ts.store("web_fetch", "first")
        ts.store("python_exec", "second")
        assert ts.latest() == "second"

    def test_latest_filtered_by_capability(self):
        ts = TaskState()
        ts.store("web_fetch", "page1")
        ts.store("python_exec", "code")
        ts.store("web_fetch", "page2")
        assert ts.latest("web_fetch") == "page2"

    def test_latest_no_match_returns_none(self):
        ts = TaskState()
        ts.store("web_fetch", "data")
        assert ts.latest("shell") is None

    def test_latest_empty_returns_none(self):
        ts = TaskState()
        assert ts.latest() is None


class TestSummary:

    def test_empty_returns_empty_string(self):
        ts = TaskState()
        assert ts.summary() == ""

    def test_lists_keys_with_sizes(self):
        ts = TaskState()
        ts.store("web_fetch", "hello world")
        ts.store("python_exec", "x" * 50)
        s = ts.summary()
        assert "step_1_web_fetch" in s
        assert "11 chars" in s
        assert "step_2_python_exec" in s
        assert "50 chars" in s

    def test_includes_header(self):
        ts = TaskState()
        ts.store("shell", "ok")
        assert "task_state" in ts.summary()


class TestDictBehavior:

    def test_custom_keys(self):
        ts = TaskState()
        ts["my_data"] = "custom"
        assert ts["my_data"] == "custom"

    def test_get_with_default(self):
        ts = TaskState()
        assert ts.get("missing", "default") == "default"

    def test_len(self):
        ts = TaskState()
        ts.store("a", "1")
        ts.store("b", "2")
        ts["custom"] = "3"
        assert len(ts) == 3

    def test_iteration(self):
        ts = TaskState()
        ts.store("web_fetch", "data")
        ts["extra"] = "val"
        keys = list(ts.keys())
        assert "step_1_web_fetch" in keys
        assert "extra" in keys

    def test_in_operator(self):
        ts = TaskState()
        ts.store("shell", "ok")
        assert "step_1_shell" in ts
        assert "step_2_shell" not in ts
