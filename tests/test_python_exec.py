"""Tests for python_exec — code execution, injected globals, error handling."""

from monad.tools.python_exec import run
from monad.config import CONFIG

MONAD_OUTPUT_DIR = CONFIG.output_path


class TestBasicExecution:

    def test_simple_print(self):
        assert "hello" in run(code='print("hello")')

    def test_arithmetic(self):
        assert "5" in run(code='print(2 + 3)')

    def test_multiline(self):
        assert "30" in run(code="x = 10\ny = 20\nprint(x + y)")

    def test_no_output_succeeds(self):
        assert "executed successfully" in run(code='x = 42')


class TestInjectedGlobals:

    def test_os_available(self):
        result = run(code='print(os.path.sep)')
        assert result.strip() in ("/", "\\")

    def test_sys_available(self):
        assert "module" in run(code='print(type(sys).__name__)')

    def test_monad_output_dir(self):
        result = run(code='print(MONAD_OUTPUT_DIR)')
        assert ".monad" in result and "output" in result

    def test_web_fetch_callable(self):
        assert "True" in run(code='print(callable(web_fetch))')

    def test_shell_callable(self):
        assert "True" in run(code='print(callable(shell))')


class TestErrorHandling:

    def test_empty_code(self):
        assert "Error" in run(code='')

    def test_no_code(self):
        assert "Error" in run()

    def test_syntax_error(self):
        result = run(code='def foo(')
        assert "Error" in result or "SyntaxError" in result

    def test_runtime_error(self):
        assert "ZeroDivisionError" in run(code='1/0')

    def test_name_error(self):
        assert "NameError" in run(code='print(undefined_var_xyz)')

    def test_partial_output_on_error(self):
        result = run(code='print("before")\n1/0')
        assert "before" in result
        assert "ZeroDivisionError" in result


class TestStderr:

    def test_stderr_captured(self):
        assert "warn" in run(code='import sys; sys.stderr.write("warn\\n")')
