/** Event type display labels and colors. */
export const EVENT_COLORS: Record<string, string> = {
  plugin_run_start: "bg-blue-500",
  plugin_run_complete: "bg-blue-600",
  plugin_run_error: "bg-red-500",
  skill_run_start: "bg-accent",
  skill_gather_complete: "bg-accent-light",
  skill_llm_response: "bg-accent",
  skill_apply_complete: "bg-accent-dark",
  skill_run_complete: "bg-accent-dark",
  skill_run_error: "bg-red-500",
  seed_written: "bg-amber-500",
  garden_written: "bg-amber-600",
  action_logged: "bg-gray-600",
  trigger_fired: "bg-purple-500",
  tool_call_start: "bg-cyan-500",
  tool_call_complete: "bg-cyan-600",
  input_received: "bg-indigo-500",
  input_complete: "bg-indigo-600",
};

export const EVENT_LABELS: Record<string, string> = {
  plugin_run_start: "Plugin Start",
  plugin_run_complete: "Plugin Done",
  plugin_run_error: "Plugin Error",
  skill_run_start: "Skill Start",
  skill_gather_complete: "Skill Gather",
  skill_llm_response: "Skill LLM",
  skill_apply_complete: "Skill Apply",
  skill_run_complete: "Skill Done",
  skill_run_error: "Skill Error",
  seed_written: "Seed Written",
  garden_written: "Garden Written",
  action_logged: "Action Logged",
  trigger_fired: "Trigger Fired",
  tool_call_start: "Tool Start",
  tool_call_complete: "Tool Done",
  input_received: "Input Received",
  input_complete: "Input Complete",
};

export const CATEGORY_COLORS: Record<string, string> = {
  input: "bg-blue-900/50 text-blue-300",
  process: "bg-accent/15 text-accent-light",
  output: "bg-orange-900/50 text-orange-300",
};
