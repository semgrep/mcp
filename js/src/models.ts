export interface CodeFile {
  filename: string;
  content: string;
}

export interface CodeWithLanguage {
  content: string;
  language: string;
}

export interface SemgrepScanResult {
  version: string;
  results: Array<Record<string, any>>;
  errors: Array<Record<string, any>>;
  paths: Record<string, any>;
  skipped_rules: string[];
}

export interface ExternalTicket {
  external_slug: string;
  url: string;
  id: number;
  linked_issue_ids: number[];
}

export interface ReviewComment {
  external_discussion_id: string;
  external_note_id: number;
}

export interface Repository {
  name: string;
  url: string;
}

export interface Location {
  file_path: string;
  line: number;
  column: number;
  end_line: number;
  end_column: number;
}

export interface SourcingPolicy {
  id: number;
  name: string;
  slug: string;
}

export interface Rule {
  name: string;
  message: string;
  confidence: string;
  category: string;
  subcategories: string[];
  vulnerability_classes: string[];
  cwe_names: string[];
  owasp_names: string[];
}

export interface Autofix {
  fix_code: string;
  explanation: string;
}

export interface Guidance {
  summary: string;
  instructions: string;
}

export interface Autotriage {
  verdict: string;
  reason: string;
}

export interface Component {
  tag: string;
  risk: string;
}

export interface Assistant {
  autofix: Autofix;
  guidance: Guidance;
  autotriage: Autotriage;
  component: Component;
}

export interface Finding {
  id: number;
  ref: string;
  first_seen_scan_id: number;
  syntactic_id: string;
  match_based_id: string;
  external_ticket?: ExternalTicket;
  review_comments: ReviewComment[];
  repository: Repository;
  line_of_code_url: string;
  triage_state: string;
  state: string;
  status: string;
  severity: string;
  confidence: string;
  categories: string[];
  created_at: string;
  relevant_since: string;
  rule_name: string;
  rule_message: string;
  location: Location;
  sourcing_policy?: SourcingPolicy;
  triaged_at?: string;
  triage_comment?: string;
  triage_reason?: string;
  state_updated_at: string;
  rule: Rule;
  assistant?: Assistant;
}