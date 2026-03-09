#!/usr/bin/env python3
"""
MONAD — Personal AGI Operating Core

A self-learning, rational execution system.
MONAD thinks like a rational person:
  Analyze → Self-check → Learn → Execute → Reflect

Usage:
    python main.py          # Interactive mode
    python main.py --test   # Run startup self-test
"""

import sys
import os

# Ensure project root is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from monad.interface.output import Output


def run_self_test():
    """Run a startup self-test to verify all modules load correctly."""
    Output.banner()
    Output.status("Running self-test...")

    errors = []

    # Test 1: Config
    try:
        from config import CONFIG
        assert CONFIG.llm.base_url, "LLM base_url is empty"
        assert CONFIG.llm.model, "LLM model is empty"
        Output.system("✅ Config loaded")
    except Exception as e:
        errors.append(f"Config: {e}")
        Output.error(f"Config: {e}")

    # Test 2: Knowledge Vault
    try:
        from knowledge.vault import KnowledgeVault
        vault = KnowledgeVault()
        axioms = vault.load_axioms()
        assert axioms, "Axioms not loaded"
        Output.system(f"✅ Knowledge Vault ({len(axioms)} chars of axioms)")
    except Exception as e:
        errors.append(f"Knowledge: {e}")
        Output.error(f"Knowledge: {e}")

    # Test 3: Executor (basic capabilities)
    try:
        from execution.executor import Executor
        executor = Executor()
        caps = executor.capability_names
        assert "python_exec" in caps, "python_exec not found"
        assert "shell" in caps, "shell not found"
        assert "web_fetch" in caps, "web_fetch not found"
        assert "ask_user" in caps, "ask_user not found"
        Output.system(f"✅ Basic capabilities: {', '.join(caps)}")
    except Exception as e:
        errors.append(f"Executor: {e}")
        Output.error(f"Executor: {e}")

    # Test 4: python_exec capability
    try:
        from execution.executor import Executor
        executor = Executor()
        result = executor.execute("python_exec", code="print('MONAD is alive')")
        assert "MONAD is alive" in result, f"Unexpected: {result}"
        Output.system(f"✅ python_exec works: {result.strip()}")
    except Exception as e:
        errors.append(f"python_exec: {e}")
        Output.error(f"python_exec: {e}")

    # Test 5: Reasoner
    try:
        from cognition.reasoner import Reasoner
        _ = Reasoner()
        Output.system("✅ Reasoner loaded")
    except Exception as e:
        errors.append(f"Reasoner: {e}")
        Output.error(f"Reasoner: {e}")

    # Test 6: Learning modules
    try:
        from learning.reflection import Reflection
        from learning.skill_builder import SkillBuilder
        _ = Reflection()
        _ = SkillBuilder()
        Output.system("✅ Learning modules loaded")
    except Exception as e:
        errors.append(f"Learning: {e}")
        Output.error(f"Learning: {e}")

    # Summary
    Output.divider()
    if errors:
        Output.error(f"Self-test completed with {len(errors)} error(s).")
        for e in errors:
            Output.error(f"  - {e}")
        return False
    else:
        Output.status("Self-test passed. All modules operational. ✅")
        Output.status("MONAD is a self-learning agent. No pre-built tools.")
        Output.status("Capabilities: python_exec → shell → web_fetch → ask_user")
        Output.status("Everything else, MONAD learns by itself.")
        return True


def main():
    """Main entry point."""
    if "--test" in sys.argv:
        success = run_self_test()
        sys.exit(0 if success else 1)
    else:
        from core.loop import MonadLoop
        monad = MonadLoop()
        monad.start()


if __name__ == "__main__":
    main()
