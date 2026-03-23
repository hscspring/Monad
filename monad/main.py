#!/usr/bin/env python3
"""
MONAD — Personal AGI Operating Core

A self-learning, rational execution system.

Usage:
    monad              # Web UI (default)
    monad --cli        # Interactive CLI mode
    monad --feishu     # Feishu (Lark) bot mode
    monad --test       # Run startup self-test
"""

import sys

import monad.config as config_module
from monad.config import VERSION, init_workspace
from monad.interface.output import Output


# ── Self Test ────────────────────────────────────────────────────

def _test_config():
    from monad.config import CONFIG
    assert CONFIG.llm.base_url, "LLM base_url is empty"
    assert CONFIG.llm.model, "LLM model is empty"
    Output.system("✅ Config loaded")


def _test_knowledge():
    from monad.knowledge.vault import KnowledgeVault
    vault = KnowledgeVault()
    axioms = vault.load_axioms()
    assert axioms, "Axioms not loaded"
    Output.system(f"✅ Knowledge Vault ({len(axioms)} chars of axioms)")


def _test_executor():
    from monad.execution.executor import Executor
    executor = Executor()
    caps = executor.capability_names
    for required in ("python_exec", "shell", "web_fetch", "ask_user"):
        assert required in caps, f"{required} not found"
    Output.system(f"✅ Basic capabilities: {', '.join(caps)}")

    result = executor.execute("python_exec", code="print('MONAD is alive')")
    assert "MONAD is alive" in result, f"Unexpected: {result}"
    Output.system(f"✅ python_exec works: {result.strip()}")


def _test_reasoner():
    from monad.cognition.reasoner import Reasoner
    _ = Reasoner()
    Output.system("✅ Reasoner loaded")


def _test_learning():
    from monad.learning.reflection import Reflection
    from monad.learning.skill_builder import SkillBuilder
    _ = Reflection()
    _ = SkillBuilder()
    Output.system("✅ Learning modules loaded")


def run_self_test() -> bool:
    """Run a startup self-test to verify all modules load correctly."""
    Output.banner()
    Output.status("Running self-test...")

    errors = []
    tests = [
        ("Config", _test_config),
        ("Knowledge", _test_knowledge),
        ("Executor", _test_executor),
        ("Reasoner", _test_reasoner),
        ("Learning", _test_learning),
    ]

    for name, test_fn in tests:
        try:
            test_fn()
        except Exception as e:
            errors.append(f"{name}: {e}")
            Output.error(f"{name}: {e}")

    Output.divider()
    if errors:
        Output.error(f"Self-test completed with {len(errors)} error(s).")
        for e in errors:
            Output.error(f"  - {e}")
        return False

    Output.status("Self-test passed. All modules operational. ✅")
    Output.status(f"MONAD v{VERSION} — Personal AGI Operating Core")
    Output.status("Capabilities: python_exec → shell → web_fetch → ask_user")
    Output.status("Everything else, MONAD learns by itself.")
    return True


# ── First Run Setup ──────────────────────────────────────────────

def _prompt_api_config():
    """Prompt user for API config and return (base_url, api_key, model_id) or None."""
    from monad.config import CONFIG

    base_url = input(f"API Base URL [{CONFIG.llm.base_url}]: ").strip()
    api_key = input("API Key (Required for usage): ").strip()
    model_id = input(f"Model ID [{CONFIG.llm.model}]: ").strip()

    if not api_key:
        print("\n[!] Skipped config setup. MONAD may not function correctly without an API Key.")
        return None

    return (
        base_url or CONFIG.llm.base_url,
        api_key,
        model_id or CONFIG.llm.model,
    )


def _validate_api(base_url: str, api_key: str, model_id: str) -> bool:
    """Validate API credentials by making a test call."""
    print("\n[.] 正在验证 API 配置 (Testing API connection)...")
    try:
        from openai import OpenAI
        import httpx
        test_client = OpenAI(
            base_url=base_url, api_key=api_key,
            timeout=httpx.Timeout(10.0),
        )
        test_client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": "Hi"}],
            max_tokens=1,
        )
        print("[✔] 验证成功！(Verification passed!)")
        return True
    except Exception as e:
        print(f"[!] 验证失败 (Connection failed): {e}")
        print("请检查填写的链接、凭证和模型ID是否正确，然后再试一次。(Please try again)\n")
        return False


def _save_env(base_url: str, api_key: str, model_id: str):
    """Save validated API config to .env and update runtime config."""
    from monad.config import CONFIG

    env_path = CONFIG.root_dir / ".env"
    content = (
        "# MONAD Configuration\n"
        f"MONAD_BASE_URL={base_url}\n"
        f"MONAD_API_KEY={api_key}\n"
        f"MODEL_ID={model_id}\n"
    )
    env_path.write_text(content, encoding="utf-8")

    CONFIG.llm.base_url = base_url
    CONFIG.llm.api_key = api_key
    CONFIG.llm.model = model_id

    print("\n[✔] Configuration successfully saved!")


def check_first_run_setup():
    """Check if the API key is missing and prompt the user for it."""
    from monad.config import CONFIG
    if CONFIG.llm.api_key:
        return

    print("\n" + "=" * 50)
    print(" Welcome to MONAD — First Run Setup")
    print("=" * 50)
    print("Please configure your LLM provider settings.")
    print("Press Enter to accept the default values shown in brackets.")
    print(f"Your configuration will be saved to: {CONFIG.root_dir / '.env'}\n")

    while True:
        result = _prompt_api_config()
        if result is None:
            break

        base_url, api_key, model_id = result
        if _validate_api(base_url, api_key, model_id):
            _save_env(base_url, api_key, model_id)
            break

    print("=" * 50 + "\n")


# ── Entry Point ──────────────────────────────────────────────────

def main():
    """Main entry point."""
    init_workspace()
    if "--test" in sys.argv:
        success = run_self_test()
        sys.exit(0 if success else 1)

    check_first_run_setup()

    if "--cli" in sys.argv:
        config_module.LAUNCH_MODE = "cli"
        from monad.core.loop import MonadLoop
        agent = MonadLoop()
        agent.start()
    elif "--feishu" in sys.argv:
        config_module.LAUNCH_MODE = "feishu"
        from monad.interface.feishu import start_feishu
        start_feishu()
    else:
        config_module.LAUNCH_MODE = "web"
        from monad.interface.web import start_web
        start_web()


if __name__ == "__main__":
    main()
