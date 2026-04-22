"""
Load Jinja2 prompt templates with system/user block separation.

Usage:
    from prompt_templates import render_prompt
    system, user = render_prompt("summarize_memory.j2", existing_memory="...", transcript="...")
"""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

_PROMPTS_DIR = Path(__file__).parent
_env = Environment(
    loader=FileSystemLoader(_PROMPTS_DIR),
    keep_trailing_newline=False,
    trim_blocks=True,
    lstrip_blocks=True,
)


def render_prompt(template_name: str, **kwargs) -> tuple[str, str]:
    """Render a .j2 template and return (system_message, user_message)."""
    tmpl = _env.get_template(template_name)

    ctx = tmpl.new_context(vars=kwargs)

    system = ""
    user = ""
    for name, block_fn in tmpl.blocks.items():
        rendered = "".join(block_fn(ctx)).strip()
        if name == "system":
            system = rendered
        elif name == "user":
            user = rendered

    return system, user
