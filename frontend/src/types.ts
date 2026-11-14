export interface JevBox {
  section_filter: string | null;
  servicio_csv: string;
  estrato: number | null;
  trimestre: string;
  is_greeting_or_chitchat: boolean;
  is_user_memory_operation: boolean;
  is_out_of_scope_or_private: boolean;
  is_security_canary_probe: boolean;
}

export interface RouterDecision {
  choice: "direct_reply" | "structured_tool" | "rag_search" | "hybrid_multi_tool";
  noul_triggered: boolean;
  score: number;
  box: JevBox;
  rationale: string;
  tools_to_invoke: string[];
}

export interface ContextWindowReport {
  total_messages_before: number;
  kept_messages_after: number;
  tokens_before: number;
  tokens_after: number;
  max_token_budget: number;
  trimmed_count: number;
  summarization_triggered: boolean;
  rolling_summary: string;
}

export interface MemoryItem {
  namespace?: string;
  key: string;
  label: string;
  value: string;
  source_thread_id: string;
  updated_at: string;
  score?: number;
}

export interface StructuredOutputReport {
  tool_name: string;
  source_file: string;
  filters_applied: Record<string, unknown>;
  records_matched: number;
  summary_metrics: Record<string, string | number>;
  rows: Array<Record<string, unknown>>;
}

export interface RagCitation {
  rank: number;
  chunk_id: string;
  section: string;
  slug: string;
  title: string;
  source_url: string;
  heading_path: string;
  score: number;
  dense_score: number;
  lexical_score: number;
  search_mode: string;
  snippet: string;
  injection_detected: boolean;
  risk_level: string;
  matched_rules: string[];
}

export interface SecurityAudit {
  checked_chunks: number;
  any_injection_detected: boolean;
  risk_level: string;
  matched_rules: string[];
  events: Array<{
    chunk_id: string;
    title: string;
    section: string;
    source_url: string;
    injection_detected: boolean;
    risk_level: string;
    matched_rules: string[];
    neutralized_segments: string[];
  }>;
}

export interface TurnPayload {
  thread_id: string;
  user_id: string;
  question: string;
  answer: string;
  reasoning: string;
  model_used: string;
  router_decision: RouterDecision;
  context_window: ContextWindowReport;
  newly_saved_memories: MemoryItem[];
  long_term_memories: MemoryItem[];
  structured_outputs: StructuredOutputReport[];
  rag_citations: RagCitation[];
  security_audit: SecurityAudit;
  tts_speech_text?: string;
  server_pid?: number;
}

export interface DemoPreset {
  id: string;
  number: string;
  title: string;
  minute_block: string;
  question: string;
  expected_route: string;
  description: string;
}
