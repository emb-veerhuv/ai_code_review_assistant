from __future__ import annotations

import json
import os
from typing import Any

from openai import OpenAI


SYSTEM_PROMPT = """
You are a senior embedded C/C++ software reviewer.

The YAML coding standard is authoritative. Review the complete supplied
source code against those rules. Also inspect for defects, unsafe patterns,
undefined behaviour, performance risks, maintainability problems and naming
problems.

Important:
- Use only evidence visible in the supplied code.
- Do not invent compiler errors or missing dependencies.
- Do not report a style preference that conflicts with the YAML rules.
- Use exact file names and exact line numbers.
- If a finding covers one line, start_line and end_line must be identical.
- If a safe automatic change cannot be determined, explain the required
  design decision instead of inventing a patch.
- Suggested patches are only examples. Never assume they can be applied
  without compilation and testing.

Return valid JSON only:

{
  "findings": [
    {
      "rule_id": "AI-001",
      "category": "defect",
      "severity": "High",
      "file": "src/example.cpp",
      "start_line": 10,
      "end_line": 10,
      "title": "Short issue title",
      "evidence": "Exact code evidence",
      "why_it_matters": "Technical impact",
      "remediation": "General fix",
      "suggested_change": "Specific developer action",
      "before_code": "Current affected code",
      "after_code": "Suggested replacement",
      "verification": "How to confirm the fix",
      "confidence": 0.90
    }
  ]
}
"""


def number_source(path: str, source: str) -> str:
    lines = []

    for number, line in enumerate(
        source.splitlines(),
        start=1,
    ):
        lines.append(f"{number:5}: {line}")

    return (
        f"FILE: {path}\n"
        + "\n".join(lines)
    )


def normalize_line(value: Any) -> int:
    try:
        number = int(value)
        return max(number, 1)
    except Exception:
        return 1


def analyze_with_llm(state: dict[str, Any]) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return {
            "llm_enabled": False,
            "llm_status": "LLM disabled because OPENAI_API_KEY is missing.",
            "llm_findings": [],
        }

    client = OpenAI(api_key=api_key)
    model = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")

    source_text = "\n\n".join(
        number_source(path, text)
        for path, text in state.get("files", {}).items()
    )
    rules_text = json.dumps(state.get("rules", {}), indent=2)
    deterministic_findings = json.dumps(state.get("findings", []), indent=2)

    response = client.chat.completions.create(
        model=model,
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "CUSTOM CODING RULES:\n"
                    f"{rules_text[:40000]}\n\n"
                    "NUMBERED SOURCE CODE:\n"
                    f"{source_text[:120000]}\n\n"
                    "DETERMINISTIC FINDINGS (for context, do not duplicate):\n"
                    f"{deterministic_findings[:20000]}"
                ),
            },
        ],
    )

    try:
        payload = json.loads(response.choices[0].message.content or "{}")
    except json.JSONDecodeError:
        return {
            "llm_enabled": True,
            "llm_status": "OpenAI returned invalid JSON.",
            "llm_findings": [],
        }

    findings = []
    counter = 1  # start incrementing rule IDs

    for item in payload.get("findings", []):
        if not isinstance(item, dict):
            continue

        rule_id = f"TEAM-{counter:03d}"  # TEAM-001, TEAM-002, etc.
        counter += 1

        finding = {
            "rule_id": rule_id,
            "category": item.get("category", "AI review"),
            "severity": str(item.get("severity", "Medium")).capitalize(),
            "file": item.get("file", ""),
            "start_line": normalize_line(item.get("start_line")),
            "end_line": normalize_line(item.get("end_line")),
            "title": item.get("title", "AI review finding"),
            "evidence": item.get("evidence", ""),
            "why_it_matters": item.get("why_it_matters", ""),
            "remediation": item.get("remediation", ""),
            "suggested_change": item.get("suggested_change", ""),
            "before_code": item.get("before_code", ""),
            "after_code": item.get("after_code", ""),
            "verification": item.get("verification", "Build the project and run relevant tests."),
            "confidence": float(item.get("confidence", 0.5)),
            "source": "OpenAI",
        }
        findings.append(finding)

    return {
        "llm_enabled": True,
        "llm_status": f"OpenAI completed review. {len(findings)} AI findings returned.",
        "llm_findings": findings,
    }
