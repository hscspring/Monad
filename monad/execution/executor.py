"""
MONAD Execution: Executor
Executes basic capabilities (python_exec, shell, web_fetch, ask_user) and learned skills.
"""

import importlib
from pathlib import Path

from monad.config import CONFIG
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
        # Check basic capabilities first
        if capability in self._capabilities:
            try:
                return self._capabilities[capability](**params)
            except Exception as e:
                return f"Error executing {capability}: {str(e)}"

        # Check learned skills
        skill_result = self._try_skill(capability, **params)
        if skill_result is not None:
            return skill_result

        return (
            f"Unknown capability: '{capability}'. "
            f"Available: {', '.join(self._capabilities.keys())}. "
            f"Consider using python_exec to accomplish this."
        )

    def _try_skill(self, skill_name: str, **params) -> str | None:
        """Try to execute a learned skill.

        Searches both the bundled package skills and the user's
        ~/.monad/knowledge/skills/ directory. MONAD's basic tool
        functions are injected into the skill module so that skill
        code can call web_fetch(), shell(), python_exec() directly.
        """
        executor_path = CONFIG.skills_path / skill_name / "executor.py"
        if not executor_path.exists():
            return None

        try:
            spec = importlib.util.spec_from_file_location(f"skill_{skill_name}", executor_path)
            module = importlib.util.module_from_spec(spec)

            # Inject MONAD's tools so skills can call them directly
            module.web_fetch = web_fetch_run
            module.shell = shell_run
            module.python_exec = python_exec_run
            module.ask_user = ask_user_run

            spec.loader.exec_module(module)

            if hasattr(module, "run"):
                return module.run(**params)
            else:
                return f"Skill '{skill_name}' has no run() function."
        except Exception as e:
            return f"Error running skill '{skill_name}': {str(e)}"

    @property
    def capability_names(self) -> list:
        return list(self._capabilities.keys())
