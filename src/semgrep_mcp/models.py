from pydantic import BaseModel, HttpUrl, Field
from typing import List, Optional, Any
from datetime import datetime


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
    linked_issue_ids: List[int]


class ReviewComment(BaseModel):
    external_discussion_id: str
    external_note_id: int


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
    subcategories: List[str]
    vulnerability_classes: List[str]
    cwe_names: List[str]
    owasp_names: List[str]


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
    autofix: Autofix
    guidance: Guidance
    autotriage: Autotriage
    component: Component


class Finding(BaseModel):
    id: int
    ref: str
    first_seen_scan_id: int
    syntactic_id: str
    match_based_id: str
    external_ticket: Optional[ExternalTicket] = None
    review_comments: List[ReviewComment]
    repository: Repository
    line_of_code_url: HttpUrl
    triage_state: str
    state: str
    status: str
    severity: str
    confidence: str
    categories: List[str]
    created_at: datetime
    relevant_since: datetime
    rule_name: str
    rule_message: str
    location: Location
    sourcing_policy: Optional[SourcingPolicy] = None
    triaged_at: Optional[datetime] = None
    triage_comment: Optional[str] = None
    triage_reason: Optional[str] = None
    state_updated_at: datetime
    rule: Rule
    assistant: Optional[Assistant] = None
