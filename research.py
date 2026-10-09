"""research.py - STUDENT IMPLEMENTS.  The main script.   Guide: GUIDE.md, part 3.

Usage:  python research.py "survey about world model"
Result: reports/<slug>.md   reports/<slug>.sources.json   reports/<slug>.meta.json
"""
import json
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path

from agents import FINALIZER_PATH, REPORT_PATH, SOURCES_PATH, VALIDATOR_PATH, WORKDIR, build_lead_agent
from model import _env, make_model
from sandbox import download, open_sandbox, upload

ROOT = Path(__file__).parent
REPORTS = ROOT / "reports"
VALIDATOR_SOURCE = ROOT / "check_citations.py"
FINALIZER_SOURCE = ROOT / "finalize_citations.py"   # provided: uploaded next to your validator


def slugify(topic):
    """Turn a topic into a safe file name: lower case, runs of non-word characters become one "-", max 60 chars,
    never empty (fall back to "topic"). The topic is user input: "../../x" must not escape reports/."""
    topic = (topic or "").strip().lower()
    slug = re.sub(r"[^\w]+", "-", topic, flags=re.UNICODE).strip("-")
    slug = slug[:60].rstrip("-")
    return slug or "topic"


def build_prompt(topic):
    """The user message sent to the lead agent."""
    return f"""Please conduct a comprehensive, multi-source literature survey on the topic: "{topic}".

Follow the required workflow:
1. Use `write_todos` to plan and split this topic into at least 3 independent sub-questions.
2. Delegate each sub-question in parallel to the `researcher` subagent using the `task` tool, providing full context and destination notes path.
3. Review researcher findings, ensure at least 3 source families (among arxiv, hf-daily, hf-search, web) are represented, and merge notes into {SOURCES_PATH}.
4. Draft the scientific survey report body in {REPORT_PATH} following REPORT_TEMPLATE.md (do NOT write ## References).
5. Run {FINALIZER_PATH} via `execute` tool to automatically format references and citations.
6. Run {VALIDATOR_PATH} via `execute` tool and ensure it passes with OK.
7. Delegate 2-3 sample claims to `citation-checker` for verification.
"""


def summarize(messages, elapsed, model_name):
    """Return {"model", "elapsed_s", "subagent_calls", "tool_calls": {name: count}, "tokens": {"input", "output"}}."""
    tool_counter = Counter()
    input_tokens = 0
    output_tokens = 0

    for msg in messages:
        # Count tool calls
        tcalls = []
        if hasattr(msg, "tool_calls") and isinstance(msg.tool_calls, list):
            tcalls = msg.tool_calls
        elif isinstance(msg, dict) and "tool_calls" in msg and isinstance(msg["tool_calls"], list):
            tcalls = msg["tool_calls"]

        for tc in tcalls:
            name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
            if name:
                tool_counter[name] += 1

        # Count tokens from usage metadata
        um = None
        if hasattr(msg, "usage_metadata") and msg.usage_metadata:
            um = msg.usage_metadata
        elif hasattr(msg, "response_metadata") and isinstance(msg.response_metadata, dict):
            um = msg.response_metadata.get("token_usage")
        elif isinstance(msg, dict):
            um = msg.get("usage_metadata") or msg.get("response_metadata", {}).get("token_usage")

        if isinstance(um, dict):
            input_tokens += int(um.get("input_tokens") or um.get("prompt_tokens") or 0)
            output_tokens += int(um.get("output_tokens") or um.get("completion_tokens") or 0)

    subagent_calls = tool_counter.get("task", 0)
    elapsed_s = round(float(elapsed), 1)

    return {
        "model": model_name,
        "elapsed_s": elapsed_s,
        "subagent_calls": subagent_calls,
        "tool_calls": dict(tool_counter),
        "tokens": {"input": input_tokens, "output": output_tokens},
    }


def save_outputs(backend, topic, messages, elapsed, model_name, reports_dir=REPORTS):
    """Download the report from the sandbox and write the three files into reports_dir. Return the report path."""
    reports_dir = Path(reports_dir)
    reports_dir.mkdir(parents=True, exist_ok=True)

    files = download(backend, [REPORT_PATH, SOURCES_PATH])
    report_bytes = files.get(REPORT_PATH)
    sources_bytes = files.get(SOURCES_PATH)

    if not report_bytes or not report_bytes.strip():
        raise RuntimeError(f"Report is missing or empty in sandbox at {REPORT_PATH}")

    if not sources_bytes or not sources_bytes.strip():
        raise RuntimeError(f"Sources file is missing or empty in sandbox at {SOURCES_PATH}")

    try:
        sources_data = json.loads(sources_bytes.decode("utf-8"))
        if not isinstance(sources_data, list):
            raise ValueError("sources.json must be a JSON array")
    except Exception as exc:
        raise RuntimeError(f"sources.json is invalid JSON: {exc}")

    slug = slugify(topic)
    md_path = reports_dir / f"{slug}.md"
    sources_path = reports_dir / f"{slug}.sources.json"
    meta_path = reports_dir / f"{slug}.meta.json"

    # Write files atomically/cleanly
    md_path.write_bytes(report_bytes)
    sources_path.write_bytes(sources_bytes)

    source_families = sorted(list(set(
        s.get("source") for s in sources_data if isinstance(s, dict) and s.get("source")
    )))
    summary_data = summarize(messages, elapsed, model_name)
    meta = {
        "topic": topic,
        **summary_data,
        "n_sources": len(sources_data),
        "source_families": source_families,
    }
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    return md_path


def main(topic):
    """Return the process exit code (0 ok, 1 failed run, 2 no topic)."""
    if not topic or not topic.strip():
        print("Usage: python research.py \"<topic>\"", file=sys.stderr)
        return 2

    topic = topic.strip()
    model = make_model()
    model_name = _env("LAB_MODEL", "OPENAI_DEPLOYMENT_MODEL") or getattr(model, "model_name", None) or getattr(model, "model", None) or "model"
    start = time.monotonic()

    try:
        with open_sandbox() as backend:
            backend.execute(f"mkdir -p {WORKDIR}/research/notes {WORKDIR}/report")
            upload(backend, {
                VALIDATOR_PATH: VALIDATOR_SOURCE.read_bytes(),
                FINALIZER_PATH: FINALIZER_SOURCE.read_bytes(),
            })
            agent = build_lead_agent(backend, model)
            prompt = build_prompt(topic)
            result = agent.invoke(
                {"messages": [{"role": "user", "content": prompt}]},
                config={"recursion_limit": 1000},
            )
            elapsed = time.monotonic() - start
            messages = result.get("messages", []) if isinstance(result, dict) else []
            saved_path = save_outputs(backend, topic, messages, elapsed, model_name)
            print(f"Report saved to: {saved_path}")
            return 0
    except Exception as exc:
        print(f"FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main(" ".join(sys.argv[1:])))
