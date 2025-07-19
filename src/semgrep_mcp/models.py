from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, HttpUrl


class LocalCodeFile(BaseModel):
    path: str = Field(description="Absolute path to be scanned locally by Semgrep.")


class CodeFile(BaseModel):
    filename: str = Field(description="Relative path to the code file")
    content: str = Field(description="Content of the code file")


class CodeWithLanguage(BaseModel):
    content: str = Field(description="Content of the code file")
    language: str = Field(description="Programing language of the code file", default="python")


class SemgrepScanResult(BaseModel):
    version: str = Field(description="Version of Semgrep used for the scan")
    results: list[dict[str, Any]] = Field(description="List of semgrep scan results")
    errors: list[dict[str, Any]] = Field(
        description="List of errors encountered during scan", default_factory=list
    )
    paths: dict[str, Any] = Field(description="Paths of the scanned files")
    skipped_rules: list[str] = Field(
        description="List of rules that were skipped during scan", default_factory=list
    )


class ExternalTicket(BaseModel):
    external_slug: str
    url: HttpUrl
    id: int
    linked_issue_ids: list[int]


class ReviewComment(BaseModel):
    external_discussion_id: str
    external_note_id: int | None = None


class Repository(BaseModel):
    name: str
    url: HttpUrl


class Location(BaseModel):
    file_path: str
    line: int
    column: int
    end_line: int
    end_column: int


class SourcingPolicy(BaseModel):
    id: int
    name: str
    slug: str


class Rule(BaseModel):
    name: str
    message: str
    confidence: str
    category: str
    subcategories: list[str]
    vulnerability_classes: list[str]
    cwe_names: list[str]
    owasp_names: list[str]


class Autofix(BaseModel):
    fix_code: str
    explanation: str


class Guidance(BaseModel):
    summary: str
    instructions: str


class Autotriage(BaseModel):
    verdict: str
    reason: str


class Component(BaseModel):
    tag: str
    risk: str


class Assistant(BaseModel):
    autofix: Autofix | None = None
    guidance: Guidance | None = None
    autotriage: Autotriage | None = None
    component: Component | None = None


class Finding(BaseModel):
    id: int
    ref: str
    first_seen_scan_id: int
    syntactic_id: str
    match_based_id: str
    external_ticket: ExternalTicket | None = None
    review_comments: list[ReviewComment]
    repository: Repository
    line_of_code_url: HttpUrl
    triage_state: str
    state: str
    status: str
    severity: str
    confidence: str
    categories: list[str]
    created_at: datetime
    relevant_since: datetime
    rule_name: str
    rule_message: str
    location: Location
    sourcing_policy: SourcingPolicy | None = None
    triaged_at: datetime | None = None
    triage_comment: str | None = None
    triage_reason: str | None = None
    state_updated_at: datetime
    rule: Rule
    assistant: Assistant | None = None
