export type Step = {
  step_id: string;
  execution_id: string;
  step_index: number;
  tool_name: string;
  arguments: Record<string, unknown>;
  status: string;
  output_data: Record<string, unknown> | string | null;
  error_type: string | null;
  error_message: string | null;
  started_at: string | null;
  completed_at: string | null;
};

export type Execution = {
  execution_id: string;
  user_request: string;
  status: string;
  final_output: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
  steps: Step[];
};

const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${baseUrl}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail ?? `请求失败（${response.status}）`);
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export const api = {
  create: (user_request: string) =>
    request<Execution>("/api/v1/executions", {
      method: "POST",
      body: JSON.stringify({ user_request }),
    }),
  list: () => request<{ items: Execution[]; total: number }>("/api/v1/executions"),
  get: (id: string) => request<Execution>(`/api/v1/executions/${id}`),
  remove: (id: string) => request<void>(`/api/v1/executions/${id}`, { method: "DELETE" }),
};
