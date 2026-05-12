"""LLM helpers for the DSO Institute Day 2 Afternoon session.

Follows the same conventions used in ``semantic_bridge``:

- ``openai`` is an optional import (raises a clear RuntimeError if missing).
- LLM calls take explicit ``model``, ``api_key``, ``base_url`` arguments.
- The OpenAI client is constructed inside the call, not cached at module load.

Prompts are exposed as module-level variables so they can be edited in place or
overridden per call through :class:`LLMConfig`. The default user template is
structured around three variables: ``context``, ``task``, and ``format``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - optional dependency at runtime
    OpenAI = None


DEFAULT_MODEL = "Llama-4-Maverick-17B-128E-Instruct"

SYSTEM_PROMPT = (
    "You are a helpful assistant supporting researchers in the DSO Institute. "
    "Answer concisely and cite uncertainty when it exists."
)

USER_PROMPT_TEMPLATE = (
    "<context>\n{context}\n</context>\n\n"
    "<task>\n{task}\n</task>\n\n"
    "<format>\n{format}\n</format>"
)


@dataclass
class LLMConfig:
    model: str = DEFAULT_MODEL
    api_key: str | None = None
    base_url: str | None = None
    system_prompt: str = SYSTEM_PROMPT
    user_prompt_template: str = USER_PROMPT_TEMPLATE
    temperature: float = 0.2
    max_tokens: int = 800
    extra: dict[str, Any] = field(default_factory=dict)


def render_prompt(template: str, **variables: Any) -> str:
    return template.format(**variables)


def run_llm(
    config: LLMConfig | None = None,
    *,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    **prompt_variables: Any,
) -> str:
    if OpenAI is None:
        raise RuntimeError("openai is not installed in this environment")

    config = config or LLMConfig()
    resolved_model = model or config.model
    resolved_api_key = api_key or config.api_key or os.environ.get("OPENAI_API_KEY")
    resolved_base_url = base_url or config.base_url

    if not resolved_api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Export it in your shell or pass api_key= to run_llm or LLMConfig."
        )

    client = OpenAI(api_key=resolved_api_key, base_url=resolved_base_url or None)
    user_message = render_prompt(config.user_prompt_template, **prompt_variables)

    response = client.chat.completions.create(
        model=resolved_model,
        messages=[
            {"role": "system", "content": config.system_prompt},
            {"role": "user", "content": user_message},
        ],
        temperature=config.temperature,
        max_tokens=config.max_tokens,
        **config.extra,
    )
    return response.choices[0].message.content or ""


def load_context(source: str | Path, *, max_chars: int | None = None) -> str:
    path = Path(source)
    if not path.exists():
        raise FileNotFoundError(f"Context file not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".pdf":
        text = _read_pdf(path)
    elif suffix in {".txt", ".md", ""}:
        text = path.read_text(encoding="utf-8")
    else:
        raise ValueError(f"Unsupported context file type: {suffix}. Use .txt or .pdf.")

    text = text.strip()
    if max_chars is not None and len(text) > max_chars:
        text = text[:max_chars].rstrip() + "\n...[truncated]"
    return text


def _read_pdf(path: Path) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:
        raise ImportError(
            "Reading PDF context requires the 'pypdf' package. Install it with `pip install pypdf`."
        ) from exc

    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n\n".join(pages)


if __name__ == "__main__":
    config = LLMConfig()
    answer = run_llm(
        config,
        context="The Semantic Bridge maps document topics to scientific variables.",
        task="Explain what the Semantic Bridge workflow is used for.",
        format="Two short sentences in plain prose.",
    )
    print(answer)
