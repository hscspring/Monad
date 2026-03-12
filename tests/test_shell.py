"""Tests for shell tool — basic commands, timeout, error handling."""

import inspect
from monad.tools.shell import run


class TestBasicCommands:

    def test_echo(self):
        assert "hello" in run(command='echo hello')

    def test_pwd(self):
        assert "/" in run(command='pwd')

    def test_multi_command(self):
        result = run(command='echo a && echo b')
        assert "a" in result and "b" in result

    def test_exit_code_reported(self):
        assert "exit code" in run(command='exit 1')


class TestErrorHandling:

    def test_empty_command(self):
        assert "Error" in run(command='')

    def test_no_command(self):
        assert "Error" in run()

    def test_timeout(self):
        assert "timed out" in run(command='sleep 10', timeout=1).lower()

    def test_bad_command_stderr(self):
        result = run(command='ls /nonexistent_dir_xyz_123')
        assert "No such file" in result or "exit code" in result


class TestDefaultTimeout:

    def test_default_timeout_is_120(self):
        assert inspect.signature(run).parameters["timeout"].default == 120
