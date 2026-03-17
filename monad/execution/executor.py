"""
MONAD Execution: Executor
Executes basic capabilities (python_exec, shell, web_fetch, ask_user) and learned skills.
"""

import importlib
import subprocess
import sys
from pathlib import Path

import yaml

from monad.config import CONFIG
from monad.interface.output import Output
from monad.tools.python_exec import run as python_exec_run
from monad.tools.shell import run as shell_run
from monad.tools.web_fetch import run as web_fetch_run
from monad.tools.ask_user import run as ask_user_run
from monad.tools.desktop_control import run as desktop_control_run


class Executor:
    """Executes MONAD's basic capabilities and learned skills."""

    def __init__(self):
        self._capabilities = {
            "python_exec": python_exec_run,
            "shell": shell_run,
            "web_fetch": web_fetch_run,
            "ask_user": ask_user_run,
            "desktop_control": desktop_control_run,
        }

    def execute(self, capability: str, **params) -> str:
        """Execute a capability or learned skill.

        Args:
            capability: Name of the capability or skill
            **params: Parameters for the capability

        Returns:
            Result string
        """
        before = self._snapshot_output_dir()

        # Check basic capabilities first
        if capability in self._capabilities:
            try:
                result = self._capabilities[capability](**params)
            except Exception as e:
                result = f"Error executing {capability}: {str(e)}"
        else:
            # Check learned skills
            skill_result = self._try_skill(capability, **params)
            if skill_result is not None:
                result = skill_result
            else:
                result = (
                    f"Unknown capability: '{capability}'. "
                    f"Available: {', '.join(self._capabilities.keys())}. "
                    f"Consider using python_exec to accomplish this."
                )

        self._announce_new_files(before)
        return result

    def _try_skill(self, skill_name: str, **params) -> str | None:
        """Try to execute a learned skill.

        Searches both the bundled package skills and the user's
        ~/.monad/knowledge/skills/ directory. MONAD's basic tool
        functions are injected into the skill module so that skill
        code can call web_fetch(), shell(), python_exec() directly.

        If skill.yaml declares dependencies, they are auto-installed
        before execution.
        """
        skill_dir = CONFIG.skills_path / skill_name
        executor_path = skill_dir / "executor.py"
        if not executor_path.exists():
            return None

        self._ensure_skill_deps(skill_dir)

        try:
            spec = importlib.util.spec_from_file_location(f"skill_{skill_name}", executor_path)
            module = importlib.util.module_from_spec(spec)

            # Inject MONAD's tools so skills can call them directly
            module.web_fetch = web_fetch_run
            module.shell = shell_run
            module.python_exec = python_exec_run
            module.ask_user = ask_user_run

            output_dir = CONFIG.root_dir / "output"
            output_dir.mkdir(parents=True, exist_ok=True)
            module.MONAD_OUTPUT_DIR = str(output_dir)

            spec.loader.exec_module(module)

            if hasattr(module, "run"):
                return module.run(**params)
            else:
                return f"Skill '{skill_name}' has no run() function."
        except Exception as e:
            return f"Error running skill '{skill_name}': {str(e)}"

    @staticmethod
    def _ensure_skill_deps(skill_dir: Path) -> None:
        """Auto-install Python dependencies declared in skill.yaml.

        dependencies.python entries use pip package names (e.g. beautifulsoup4,
        not bs4).  We check installation status via importlib.metadata which
        works with pip names directly.
        """
        yaml_path = skill_dir / "skill.yaml"
        if not yaml_path.exists():
            return

        try:
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        except Exception:
            return

        deps = data.get("dependencies", {})
        py_deps = deps.get("python", [])
        if not py_deps:
            return

        from importlib.metadata import distribution, PackageNotFoundError

        missing = []
        for dep in py_deps:
            pkg_name = dep.split(">=")[0].split("==")[0].split("<")[0].split("[")[0].strip()
            try:
                distribution(pkg_name)
            except PackageNotFoundError:
                missing.append(dep)

        if missing:
            Output.system(f"正在安装 skill 依赖: {', '.join(missing)}")
            subprocess.run(
                [sys.executable, "-m", "pip", "install", "-q", *missing],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=120,
            )

    _OUTPUT_DIR = CONFIG.root_dir / "output"

    def _snapshot_output_dir(self) -> set[Path]:
        d = self._OUTPUT_DIR
        return set(d.iterdir()) if d.exists() else set()

    def _announce_new_files(self, before: set[Path]) -> None:
        """Emit file_link for any new files created in output dir."""
        after = self._snapshot_output_dir()
        for f in sorted(after - before):
            url = f"/output/{f.name}"
            Output.file_link(str(f), url)

    @property
    def capability_names(self) -> list:
        return list(self._capabilities.keys())
