import { FormEvent, useEffect, useState } from "react";
import { api, Execution } from "./api";

export function App() {
  const [request, setRequest] = useState("分析 2024 年 1 月销售额，并生成 Markdown 报告");
  const [execution, setExecution] = useState<Execution | null>(null);
  const [history, setHistory] = useState<Execution[]>([]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const loadHistory = () => api.list().then((data) => setHistory(data.items)).catch(() => undefined);
  useEffect(() => { void loadHistory(); }, []);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (!request.trim()) return;
    setBusy(true); setError("");
    try {
      const result = await api.create(request);
      setExecution(result); await loadHistory();
    } catch (reason) { setError(reason instanceof Error ? reason.message : "提交失败"); }
    finally { setBusy(false); }
  }

  async function selectExecution(id: string) {
    setError("");
    try { setExecution(await api.get(id)); }
    catch (reason) { setError(reason instanceof Error ? reason.message : "读取失败"); }
  }

  return <main className="shell">
    <header><div><p className="eyebrow">LOCAL AI WORKFLOW</p><h1>AgentFlow</h1><p>让模型选择工具，让后端可靠执行，让每次分析都可追溯。</p></div></header>
    <section className="grid">
      <div className="panel composer"><h2>提交分析任务</h2><form onSubmit={submit}>
        <textarea value={request} onChange={(e) => setRequest(e.target.value)} rows={5} />
        <button disabled={busy}>{busy ? "执行中…" : "开始执行"}</button>
      </form>{error && <p className="error">{error}</p>}</div>
      <div className="panel"><h2>最近执行</h2>{history.length === 0 ? <p className="muted">暂无历史记录</p> : <div className="history">{history.map((item) => <button className="history-item" key={item.execution_id} onClick={() => void selectExecution(item.execution_id)}><span>{item.user_request}</span><b className={`status ${item.status}`}>{item.status}</b></button>)}</div>}</div>
    </section>
    {execution && <section className="panel result"><div className="result-head"><div><h2>执行详情</h2><p className="mono">{execution.execution_id}</p></div><b className={`status ${execution.status}`}>{execution.status}</b></div><p>{execution.user_request}</p><div className="steps">{execution.steps.map((step) => <article className="step" key={step.step_id}><div><b>步骤 {step.step_index}</b><span>{step.tool_name}</span><b className={`status ${step.status}`}>{step.status}</b></div><pre>{JSON.stringify(step.output_data, null, 2)}</pre>{step.error_message && <p className="error">{step.error_message}</p>}</article>)}</div>{execution.final_output && <div className="report"><h3>最终回答</h3><pre>{execution.final_output}</pre></div>}{execution.error_message && <p className="error">{execution.error_message}</p>}</section>}
  </main>;
}
