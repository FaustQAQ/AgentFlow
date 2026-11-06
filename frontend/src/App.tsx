import { FormEvent, useEffect, useState } from "react";
import { api, Dataset, Execution, UploadPreview } from "./api";

export function App() {
  const [request, setRequest] = useState("分析 2024 年 1 月销售额，并生成 Markdown 报告");
  const [execution, setExecution] = useState<Execution | null>(null);
  const [history, setHistory] = useState<Execution[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [datasetId, setDatasetId] = useState<number | "">("");
  const [preview, setPreview] = useState<UploadPreview | null>(null);
  const [uploading, setUploading] = useState(false);

  const loadHistory = () => api.list().then((data) => setHistory(data.items)).catch(() => undefined);
  const loadDatasets = () => api.datasets().then((data) => { setDatasets(data.items); if (data.items[0] && datasetId === "") setDatasetId(data.items[0].id); }).catch(() => undefined);
  useEffect(() => { void loadHistory(); void loadDatasets(); }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!request.trim() || datasetId === "") { setError("请先选择数据集"); return; }
    setBusy(true); setError("");
    try {
      const result = await api.create(request, datasetId);
      setExecution(result); await loadHistory();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "提交失败"); }
    finally { setBusy(false); }
  }

  async function upload(file?: File) { if (!file) return; setUploading(true); setError(""); try { setPreview(await api.upload(file, file.name.replace(/\.[^.]+$/, ""))); } catch (reason) { setError(reason instanceof Error ? reason.message : "上传失败"); } finally { setUploading(false); } }
  async function confirmImport() { if (!preview) return; try { const ds = await api.importDataset(preview.preview_id); setDatasets((items) => [ds, ...items]); setDatasetId(ds.id); setPreview(null); } catch (reason) { setError(reason instanceof Error ? reason.message : "导入失败"); } }

  async function selectExecution(id: string) {
    setError("");
    try { setExecution(await api.get(id)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "读取失败"); }
  }

  return <main className="shell">
    <header><div><p className="eyebrow">AGENTIC SALES ANALYTICS PLATFORM</p><h1>AgentFlow</h1><p>智能销售数据分析 Agent 平台 · 让模型选择工具，让后端可靠执行，让每次分析都可追溯。</p></div></header>
    <section className="grid">
      <div className="panel composer"><h2>销售数据管理</h2><label className="upload">{uploading ? "解析中…" : "选择 CSV / XLSX 文件"}<input type="file" accept=".csv,.xlsx" onChange={(e) => void upload(e.target.files?.[0])} /></label>{preview && <div className="preview"><p>预览：{preview.filename} · 成功 {preview.successful_rows} · 失败 {preview.failed_rows}</p><button type="button" onClick={() => void confirmImport()}>确认导入</button></div>}<h2>提交分析任务</h2><form onSubmit={submit}>
        <select value={datasetId} onChange={(e) => setDatasetId(e.target.value ? Number(e.target.value) : "")}><option value="">选择数据集</option>{datasets.map((d) => <option key={d.id} value={d.id}>{d.name}（{d.successful_rows} 条）</option>)}</select>
        <textarea value={request} onChange={(e) => setRequest(e.target.value)} rows={5} />
        <button disabled={busy}>{busy ? "执行中…" : "开始执行"}</button>
      </form>{error && <p className="error">{error}</p>}</div>
      <div className="panel"><h2>数据集</h2>{datasets.length === 0 ? <p className="muted">暂无数据集</p> : <div className="history">{datasets.map((item) => <div className="history-item" key={item.id}><span>{item.name}<small>{item.original_filename} · {item.successful_rows} 条</small></span><button type="button" onClick={() => void api.deleteDataset(item.id).then(() => void loadDatasets())}>删除</button></div>)}</div>}<h2>最近执行</h2>{history.length === 0 ? <p className="muted">暂无历史记录</p> : <div className="history">{history.map((item) => <button className="history-item" key={item.execution_id} onClick={() => void selectExecution(item.execution_id)}><span>{item.user_request}</span><b className={`status ${item.status}`}>{item.status}</b></button>)}</div>}</div>
    </section>
    {execution && <section className="panel result"><div className="result-head"><div><h2>执行详情</h2><p className="mono">{execution.execution_id}</p></div><b className={`status ${execution.status}`}>{execution.status}</b></div><p>{execution.user_request}</p><div className="steps">{execution.steps.map((step) => <article className="step" key={step.step_id}><div><b>步骤 {step.step_index}</b><span>{step.tool_name}</span><b className={`status ${step.status}`}>{step.status}</b></div><pre>{JSON.stringify(step.output_data, null, 2)}</pre>{step.error_message && <p className="error">{step.error_message}</p>}</article>)}</div>{execution.final_output && <div className="report"><h3>最终回答</h3><pre>{execution.final_output}</pre></div>}{execution.error_message && <p className="error">{execution.error_message}</p>}</section>}
  </main>;
}
