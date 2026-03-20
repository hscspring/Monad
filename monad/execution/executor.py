"""
MONAD Execution: Executor
Executes basic capabilities (python_exec, shell, web_fetch, ask_user) and learned skills.
"""

import importlib
import importlib.util
import subprocess
import sys
from pathlib import Path

import yaml
from loguru import logger

from monad.config import CONFIG, TIMEOUT_PIP_INSTALL
from monad.interface.output import Output
from monad.types import ToolFn
from monad.tools.python_exec import run as python_exec_run
from monad.tools.shell import run as shell_run
from monad.tools.web_fetch import run as web_fetch_run
from monad.tools.ask_user import run as ask_user_run
from monad.tools.desktop_control import run as desktop_control_run


class Executor:
    """Executes MONAD's basic capabilities and learned skills."""

    def __init__(self):
        self._capabilities: dict[str, ToolFn] = {
            "python_exec": python_exec_run,
            "shell": shell_run,
            "web_fetch": web_fetch_run,
            "ask_user": ask_user_run,
            "desktop_control": desktop_control_run,
        }

    def execute(self, capability: str, task_state=None, **params) -> str:
        """Execute a capability or learned skill.

        Args:
            capability: Name of the capability or skill
            task_state: Optional TaskState dict shared across the task
            **params: Parameters for the capability

        Returns:
            Result string
        """
        before = self._snapshot_output_dir()

        if capability in self._capabilities:
            try:
                if capability == "python_exec" and task_state is not None:
                    params["_task_state"] = task_state
                result = self._capabilities[capability](**params)
            except Exception as e:
                logger.exception(f"Error executing {capability}")
                result = f"Error executing {capability}: {str(e)}"
        else:
            skill_result = self._try_skill(capability, task_state=task_state, **params)
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

    def _try_skill(self, skill_name: str, task_state=None, **params) -> str | None:
        """Try to execute a learned skill.

        Loads from CONFIG.skills_path. MONAD's basic tool functions are
        injected into the skill module so that skill code can call
        web_fetch(), shell(), python_exec() directly.

        If skill.yaml defines ``composition.sequence`` (list of sub-skill names),
        runs those in order with the same kwargs (v0.5 composite skills).
        """
        skill_dir = CONFIG.skill_dir(skill_name)
        yaml_path = skill_dir / "skill.yaml"
        data: dict = {}
        if yaml_path.exists():
            try:
                loaded = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
            except Exception:
                pass

        comp = data.get("composition") if isinstance(data.get("composition"), dict) else {}
        seq = comp.get("sequence")
        if isinstance(seq, list) and seq:
            parts: list[str] = []
            for sub in seq[:16]:
                if not isinstance(sub, str) or not sub.strip():
                    continue
                name = sub.strip()
                parts.append(f"--- composition: {skill_name} → {name} ---")
                parts.append(self.execute(name, task_state=task_state, **params))
            return "\n".join(parts)

        executor_path = skill_dir / "executor.py"
        if not executor_path.exists():
            return None

        self._ensure_skill_deps(skill_dir)
        return self._load_and_run_skill(skill_name, executor_path, params,
                                        task_state=task_state)

    def _load_and_run_skill(self, skill_name: str, executor_path: Path,
                            params: dict, task_state=None) -> str:
        """Load a skill module, inject tools, and execute its run() function."""
        try:
            spec = importlib.util.spec_from_file_location(
                f"skill_{skill_name}", executor_path)
            module = importlib.util.module_from_spec(spec)

            module.web_fetch = web_fetch_run
            module.shell = shell_run
            module.python_exec = python_exec_run
            module.ask_user = ask_user_run
            module.MONAD_OUTPUT_DIR = str(CONFIG.output_path)
            if task_state is not None:
                module.task_state = task_state

            spec.loader.exec_module(module)

            if hasattr(module, "run"):
                return module.run(**params)
            else:
                return f"Skill '{skill_name}' has no run() function."
        except Exception as e:
            logger.exception(f"Error running skill '{skill_name}'")
            return f"Error running skill '{skill_name}': {str(e)}"

    @staticmethod
    def _ensure_skill_deps(skill_dir: Path) -> None:
        """Auto-install Python dependencies declared in skill.yaml."""
        yaml_path = skill_dir / "skill.yaml"
        if not yaml_path.exists():
            return

        try:
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
        except Exception:
            return

        py_deps = data.get("dependencies", {}).get("python", [])
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
                timeout=TIMEOUT_PIP_INSTALL,
            )

    @staticmethod
    def get_skill_teardown(skill_name: str) -> str | None:
        """Return the teardown skill name if declared in skill.yaml, else None."""
        yaml_path = CONFIG.skill_dir(skill_name) / "skill.yaml"
        if not yaml_path.exists():
            return None
        try:
            data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
            return data.get("teardown")
        except Exception:
            return None

    def _snapshot_output_dir(self) -> set[Path]:
        d = CONFIG.output_path
        return set(d.iterdir()) if d.exists() else set()

    def _announce_new_files(self, before: set[Path]) -> None:
        """Emit file_link for any new files created in output dir."""
        after = self._snapshot_output_dir()
        for f in sorted(after - before):
            Output.file_link(str(f), f"/output/{f.name}")

    @property
    def capability_names(self) -> list:
        return list(self._capabilities.keys())
