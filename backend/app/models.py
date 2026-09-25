from typing import Annotated, Any, TypedDict
import operator


class Finding(TypedDict, total=False):
    rule_id: str
    category: str
    severity: str
    file: str

    start_line: int
    end_line: int

    title: str
    evidence: str
    why_it_matters: str
    remediation: str

    suggested_change: str
    before_code: str
    after_code: str
    verification: str

    confidence: float
    source: str


class ReviewState(TypedDict):
    files: dict[str, str]
    rules: dict[str, Any]

    findings: Annotated[list[Finding], operator.add]
    llm_findings: Annotated[list[Finding], operator.add]
    patches: Annotated[list[dict[str, Any]], operator.add]

    llm_enabled: bool
    llm_status: str
    summary: dict[str, Any]