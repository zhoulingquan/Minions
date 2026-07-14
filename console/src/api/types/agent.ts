export interface AgentRequest {
  input: unknown;
  session_id?: string | null;
  user_id?: string | null;
  channel?: string | null;
  [key: string]: unknown;
}

export interface ContextCompactConfig {
  enabled: boolean;
  compact_threshold_ratio: number;
  reserve_threshold_ratio: number;
}

export interface ToolResultPruningConfig {
  enabled: boolean;
  pruning_recent_n: number;
  pruning_old_msg_max_bytes: number;
  pruning_recent_msg_max_bytes: number;
  offload_retention_days: number;
  exempt_file_extensions: string[];
  exempt_tool_names: string[];
}

export type ContextStrategy = "native" | "scroll";

export interface LightContextConfig {
  strategy: ContextStrategy;
  dialog_path: string;
  token_count_estimate_divisor: number;
  context_compact_config: ContextCompactConfig;
  tool_result_pruning_config: ToolResultPruningConfig;
}

export interface AutoTitleConfig {
  enabled: boolean;
  timeout_seconds: number;
}

export interface DoomLoopStageConfig {
  after: number;
  action: string;
  prompt: string;
}

export interface DoomLoopConfig {
  enabled: boolean;
  window_size: number;
  similarity_threshold: number;
  stages: DoomLoopStageConfig[];
}

export interface IterationGateConfig {
  enabled: boolean;
  max_iterations?: number | null;
}

export interface RubricGateConfig {
  enabled: boolean;
  prompt: string;
  max_interventions: number;
  in_loop_modes: boolean;
}

export interface LoopConfig {
  iteration?: IterationGateConfig;
  doom_loop: DoomLoopConfig;
  rubric?: RubricGateConfig;
}

export interface AgentsRunningConfig {
  max_iters: number;
  loop: LoopConfig;
  shell_command_timeout: number;
  shell_command_executable: string;
  llm_retry_enabled: boolean;
  llm_max_retries: number;
  llm_backoff_base: number;
  llm_backoff_cap: number;
  llm_max_concurrent: number;
  llm_max_qpm: number;
  llm_rate_limit_pause: number;
  llm_rate_limit_jitter: number;
  llm_acquire_timeout: number;
  history_max_length: number;
  context_manager_backend: string;
  light_context_config: LightContextConfig;
  approval_level?: string;
  auto_title_config: AutoTitleConfig;
}
