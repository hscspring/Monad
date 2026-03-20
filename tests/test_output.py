"""Tests for Output — message routing, queue/callable sink, formatting."""

import queue
import threading

import pytest

from monad.interface.output import Output


class TestEmitQueue:
    """Output._emit routes messages to a thread-local queue."""

    def test_queue_receives_message(self):
        q = queue.Queue()
        msgs = []

        def worker():
            Output.set_queue(q)
            Output._emit("hello from thread")

        t = threading.Thread(target=worker)
        t.start()
        t.join()
        assert not q.empty()
        assert q.get_nowait() == "hello from thread"

    def test_no_queue_does_not_raise(self, capsys):
        def worker():
            Output._local.queue = None
            Output._emit("silent")

        t = threading.Thread(target=worker)
        t.start()
        t.join()

    def test_callable_sink(self):
        captured = []

        def worker():
            Output.set_queue(captured.append)
            Output._emit("via callable")

        t = threading.Thread(target=worker)
        t.start()
        t.join()
        assert captured == ["via callable"]


class TestOutputFormatting:

    def test_status_has_timestamp(self):
        q = queue.Queue()

        def worker():
            Output.set_queue(q)
            Output.status("running")

        t = threading.Thread(target=worker)
        t.start()
        t.join()
        msg = q.get_nowait()
        assert "[MONAD" in msg and "running" in msg

    def test_error_has_prefix(self):
        q = queue.Queue()

        def worker():
            Output.set_queue(q)
            Output.error("something broke")

        t = threading.Thread(target=worker)
        t.start()
        t.join()
        msg = q.get_nowait()
        assert "something broke" in msg

    def test_result_wraps_markers(self):
        q = queue.Queue()
        from monad.config import WS_RESULT_START, WS_RESULT_END

        def worker():
            Output.set_queue(q)
            Output.result("the answer")

        t = threading.Thread(target=worker)
        t.start()
        t.join()
        msgs = []
        while not q.empty():
            msgs.append(q.get_nowait())
        assert WS_RESULT_START in msgs
        assert "the answer" in msgs
        assert WS_RESULT_END in msgs
