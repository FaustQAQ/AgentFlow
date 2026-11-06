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
  dataset_id: number | null;
};

export type Dataset = { id: number; name: string; original_filename: string; file_type: string; total_rows: number; successful_rows: number; failed_rows: number; created_at: string; updated_at: string };
export type UploadPreview = { preview_id: string; filename: string; headers: string[]; mapping: Record<string,string>; total_rows: number; successful_rows: number; failed_rows: number; preview_rows: Record<string,string>[]; errors: {row:number;message:string}[] };

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
  create: (user_request: string, dataset_id: number) =>
    request<Execution>("/api/v1/executions", {
      method: "POST",
      body: JSON.stringify({ user_request, dataset_id }),
    }),
  list: () => request<{ items: Execution[]; total: number }>("/api/v1/executions"),
  get: (id: string) => request<Execution>(`/api/v1/executions/${id}`),
  remove: (id: string) => request<void>(`/api/v1/executions/${id}`, { method: "DELETE" }),
  datasets: () => request<{items: Dataset[]; total: number}>("/api/v1/datasets"),
  upload: (file: File, name: string) => { const body = new FormData(); body.append("file", file); body.append("name", name); return request<UploadPreview>("/api/v1/datasets/upload", { method: "POST", body, headers: {} }); },
  importDataset: (previewId: string) => { const body = new FormData(); body.append("preview_id", previewId); return request<Dataset>("/api/v1/datasets/preview/import", { method: "POST", body, headers: {} }); },
  deleteDataset: (id: number) => request<void>(`/api/v1/datasets/${id}`, { method: "DELETE" }),
};
