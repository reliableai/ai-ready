"""
Smoke tests for Session 3 helpers.

These tests are deterministic and avoid live API calls.
They validate context handling logic for stateless/stateful memory code paths.
"""

from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path


def _load_module(path: Path, module_name: str):
    spec = spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module from {path}")
    module = module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_trim_to_window_keeps_recent_turns():
    root = Path(__file__).resolve().parents[1]
    mod_path = root / "02_standalone_agents" / "3_agent_with_memory.py"
    m = _load_module(mod_path, "session3_memory")

    conversation = [
        {"role": "user", "content": "u1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "u2"},
        {"role": "assistant", "content": "a2"},
        {"role": "user", "content": "u3"},
        {"role": "assistant", "content": "a3"},
    ]

    kept = m.trim_to_window(conversation, window_turns=2)

    assert kept == [
        {"role": "user", "content": "u2"},
        {"role": "assistant", "content": "a2"},
        {"role": "user", "content": "u3"},
        {"role": "assistant", "content": "a3"},
    ]


def test_build_messages_places_system_window_and_user():
    root = Path(__file__).resolve().parents[1]
    mod_path = root / "02_standalone_agents" / "3_agent_with_memory.py"
    m = _load_module(mod_path, "session3_memory_build")

    memory = "- User prefers concise answers"
    window = [
        {"role": "user", "content": "My name is Alice."},
        {"role": "assistant", "content": "Nice to meet you."},
    ]
    user_input = "What is my name?"

    messages = m.build_messages(memory, window, user_input)

    assert messages[0]["role"] == "system"
    assert memory in messages[0]["content"]
    assert messages[1:3] == window
    assert messages[-1] == {"role": "user", "content": user_input}


def test_long_term_memory_round_trip(tmp_path):
    root = Path(__file__).resolve().parents[1]
    mod_path = root / "02_standalone_agents" / "4_agent_with_long_term_memory.py"
    m = _load_module(mod_path, "session3_long_term")

    # Redirect persistence to temp file for test isolation.
    m.MEMORY_FILE = tmp_path / "user_memories.json"

    user_id = "Alice"
    memory = {"facts": ["Lives in Trento"], "preferences": ["Prefers bullet points"]}

    m.save_user_memory(user_id, memory)
    loaded = m.get_user_memory(user_id)

    assert loaded == memory
