import React from "react";
import ReactDOM from "react-dom/client";
import { Activity, BookOpen, Brain, FileText, Gamepad2, GitMerge, Layers, MessageSquare, Network, Search, Send, UploadCloud } from "lucide-react";
import * as d3 from "d3";
import { api } from "./api";
import type { ConfigStatus, Decision, GraphEdge, GraphNode, KnowledgeGraph, Textbook } from "./types";
import "./styles.css";

const TEXTBOOK_COLORS = ["#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F", "#EDC948", "#B07AA1"];
const BODY_SYSTEMS = ["全部", "呼吸系统", "循环系统", "消化系统", "神经系统", "免疫系统", "感染病", "全身/通用"];

function formatNumber(value: unknown): string {
  if (typeof value !== "number") return "0";
  return value.toLocaleString("zh-CN");
}

function StatusPill({ ok, children }: { ok: boolean; children: React.ReactNode }) {
  return <span className={`pill ${ok ? "ok" : "warn"}`}>{children}</span>;
}

function GraphCanvas({
  graph,
  query,
  bodySystem,
  selected,
  onSelect
}: {
  graph: KnowledgeGraph | null;
  query: string;
  bodySystem: string;
  selected: GraphNode | null;
  onSelect: (node: GraphNode) => void;
}) {
  const ref = React.useRef<SVGSVGElement | null>(null);

  React.useEffect(() => {
    if (!ref.current || !graph) return;
    const svg = d3.select(ref.current);
    svg.selectAll("*").remove();
    const width = ref.current.clientWidth || 720;
    const height = ref.current.clientHeight || 620;
    const lowerQuery = query.trim().toLowerCase();
    const filteredNodes = graph.nodes
      .filter((node) => bodySystem === "全部" || node.body_system === bodySystem)
      .filter((node) => !lowerQuery || node.name.toLowerCase().includes(lowerQuery) || node.definition.toLowerCase().includes(lowerQuery))
      .slice(0, 260);
    const nodeIds = new Set(filteredNodes.map((node) => node.id));
    const filteredEdges = graph.edges
      .filter((edge) => nodeIds.has(String(edge.source)) && nodeIds.has(String(edge.target)))
      .slice(0, 420);

    const root = svg.append("g");
    svg.call(
      d3
        .zoom<SVGSVGElement, unknown>()
        .scaleExtent([0.35, 4])
        .on("zoom", (event) => root.attr("transform", event.transform))
    );

    svg
      .append("defs")
      .append("marker")
      .attr("id", "arrow")
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", 18)
      .attr("refY", 0)
      .attr("markerWidth", 6)
      .attr("markerHeight", 6)
      .attr("orient", "auto")
      .append("path")
      .attr("fill", "#7b8794")
      .attr("d", "M0,-5L10,0L0,5");

    type SimNode = GraphNode & d3.SimulationNodeDatum;
    type SimEdge = Omit<GraphEdge, "source" | "target"> & { source: string | SimNode; target: string | SimNode };
    const nodes: SimNode[] = filteredNodes.map((node, index) => ({ ...node, x: width / 2 + Math.cos(index) * 140, y: height / 2 + Math.sin(index) * 120 }));
    const links: SimEdge[] = filteredEdges.map((edge) => ({ ...edge }));
    const maxFrequency = d3.max(nodes, (node) => node.frequency) || 1;
    const radius = d3.scaleSqrt().domain([1, maxFrequency]).range([7, 22]);
    const color = d3.scaleOrdinal<string, string>().domain(graph.nodes.map((node) => node.source_textbooks?.[0] || "整合")).range(TEXTBOOK_COLORS);

    const link = root
      .append("g")
      .attr("class", "links")
      .selectAll("line")
      .data(links)
      .join("line")
      .attr("stroke", (edge) => (edge.relation_type === "contains" ? "#4E79A7" : edge.relation_type === "parallel" ? "#76B7B2" : "#8b97a6"))
      .attr("stroke-width", 1.2)
      .attr("stroke-opacity", 0.44)
      .attr("stroke-dasharray", (edge) => (edge.relation_type === "parallel" ? "5 5" : "0"))
      .attr("marker-end", (edge) => (edge.relation_type === "contains" ? "url(#arrow)" : null));

    const node = root
      .append("g")
      .attr("class", "nodes")
      .selectAll<SVGGElement, SimNode>("g")
      .data(nodes)
      .join("g")
      .attr("class", "node")
      .call(
        d3
          .drag<SVGGElement, SimNode>()
          .on("start", (event, d) => {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
          })
          .on("drag", (event, d) => {
            d.fx = event.x;
            d.fy = event.y;
          })
          .on("end", (event, d) => {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
          })
      )
      .on("click", (_event, d) => onSelect(d));

    node
      .append("circle")
      .attr("r", (d) => radius(d.frequency))
      .attr("fill", (d) => (d.source_textbooks?.length > 1 ? "#ff6b6b" : color(d.source_textbooks?.[0] || "整合")))
      .attr("stroke", (d) => (selected?.id === d.id ? "#111827" : "#ffffff"))
      .attr("stroke-width", (d) => (selected?.id === d.id ? 3 : 1.6));

    node
      .append("text")
      .attr("x", 12)
      .attr("y", 4)
      .text((d) => d.name)
      .attr("font-size", 11)
      .attr("fill", "#1f2937")
      .clone(true)
      .lower()
      .attr("stroke", "#ffffff")
      .attr("stroke-width", 4);

    const simulation = d3
      .forceSimulation<SimNode>(nodes)
      .force("link", d3.forceLink<SimNode, SimEdge>(links).id((d) => d.id).distance(80).strength(0.36))
      .force("charge", d3.forceManyBody().strength(-190))
      .force("center", d3.forceCenter(width / 2, height / 2))
      .force("collision", d3.forceCollide<SimNode>().radius((d) => radius(d.frequency) + 22));

    simulation.on("tick", () => {
      link
        .attr("x1", (d) => (d.source as SimNode).x || 0)
        .attr("y1", (d) => (d.source as SimNode).y || 0)
        .attr("x2", (d) => (d.target as SimNode).x || 0)
        .attr("y2", (d) => (d.target as SimNode).y || 0);
      node.attr("transform", (d) => `translate(${d.x || 0},${d.y || 0})`);
    });

    return () => {
      simulation.stop();
    };
  }, [graph, query, bodySystem, selected, onSelect]);

  return <svg ref={ref} className="graph-svg" role="img" aria-label="知识图谱"></svg>;
}

function TextbookPanel({
  textbooks,
  activeId,
  onSelect,
  onUpload,
  stats
}: {
  textbooks: Textbook[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onUpload: (file: File) => void;
  stats: Record<string, number | boolean> | null;
}) {
  return (
    <aside className="left-panel">
      <div className="panel-heading">
        <BookOpen size={18} />
        <span>教材管理</span>
      </div>
      <label className="upload-box">
        <UploadCloud size={22} />
        <span>上传 PDF / DOCX / MD</span>
        <input
          type="file"
          accept=".md,.markdown,.txt,.pdf,.docx"
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) onUpload(file);
          }}
        />
      </label>
      <div className="book-list">
        <button className={`book-item ${activeId === "merged" ? "active" : ""}`} onClick={() => onSelect("merged")}>
          <Network size={16} />
          <div>
            <strong>整合图谱</strong>
            <small>跨教材去重合并</small>
          </div>
        </button>
        {textbooks.map((book, index) => (
          <button key={book.id} className={`book-item ${activeId === book.id ? "active" : ""}`} onClick={() => onSelect(book.id)}>
            <span className="color-dot" style={{ backgroundColor: TEXTBOOK_COLORS[index % TEXTBOOK_COLORS.length] }} />
            <div>
              <strong>{book.title}</strong>
              <small>{book.chapter_count} 个章节 · {book.status}</small>
            </div>
          </button>
        ))}
      </div>
      <div className="stats-card">
        <div className="stat-title">压缩统计</div>
        <div className="stat-row"><span>原始字符</span><b>{formatNumber(stats?.source_chars)}</b></div>
        <div className="stat-row"><span>整合字符</span><b>{formatNumber(stats?.merged_chars)}</b></div>
        <div className="stat-row"><span>压缩比</span><b>{typeof stats?.compression_ratio === "number" ? `${(stats.compression_ratio * 100).toFixed(2)}%` : "0%"}</b></div>
        <StatusPill ok={Boolean(stats?.target_met)}>目标 30%</StatusPill>
      </div>
    </aside>
  );
}

function NodeDetail({ node }: { node: GraphNode | null }) {
  if (!node) {
    return (
      <div className="node-detail empty">
        <Layers size={18} />
        <span>点击图谱节点查看定义、来源和医学标签。</span>
      </div>
    );
  }
  return (
    <div className="node-detail">
      <div className="detail-top">
        <h3>{node.name}</h3>
        <StatusPill ok={node.importance === "high"}>{node.importance}</StatusPill>
      </div>
      <p>{node.definition}</p>
      <div className="tag-grid">
        <span>{node.category}</span>
        <span>{node.body_system}</span>
        <span>{node.scale_level}</span>
        <span>{node.stage}</span>
      </div>
      <div className="evidence">{node.evidence || "暂无证据片段"}</div>
      <small>来源：{node.source_textbooks?.join("、") || "整合图谱"} · 频次 {node.frequency}</small>
    </div>
  );
}

function IntegrationTab({ decisions, onRefresh }: { decisions: Decision[]; onRefresh: () => void }) {
  return (
    <div className="tab-content">
      <button className="primary-action" onClick={onRefresh}>
        <GitMerge size={16} /> 重新整合
      </button>
      <div className="decision-list">
        {decisions.length === 0 ? <p className="muted">暂无整合决策。</p> : null}
        {decisions.map((decision) => (
          <article key={decision.id} className="decision-card">
            <div>
              <b>{decision.action}</b>
              <span>{Math.round(decision.confidence * 100)}%</span>
            </div>
            <p>{decision.reason}</p>
            <small>节省字符：{decision.char_saved.toLocaleString("zh-CN")} · {decision.status}</small>
          </article>
        ))}
      </div>
    </div>
  );
}

function RagTab({ difyReady }: { difyReady: boolean }) {
  const [question, setQuestion] = React.useState("肺炎导致低氧血症的机制是什么？");
  const [answer, setAnswer] = React.useState("");
  const [busy, setBusy] = React.useState(false);
  async function ask() {
    setBusy(true);
    try {
      const result = await api.ragQuery(question);
      setAnswer(result.answer);
    } catch (error) {
      setAnswer(error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="tab-content">
      <StatusPill ok={difyReady}>{difyReady ? "Dify 已配置" : "等待 Dify 配置"}</StatusPill>
      <textarea value={question} onChange={(event) => setQuestion(event.target.value)} />
      <button className="primary-action" disabled={busy} onClick={ask}>
        <Send size={16} /> {busy ? "检索中" : "提问"}
      </button>
      <pre className="answer-box">{answer || "回答会显示在这里，并附带教材引用。"}</pre>
    </div>
  );
}

function ChatTab() {
  const [message, setMessage] = React.useState("为什么把炎症相关知识点合并？");
  const [history, setHistory] = React.useState<Array<{ role: string; content: string }>>([]);
  async function send() {
    const current = message;
    setHistory((items) => [...items, { role: "user", content: current }]);
    setMessage("");
    const result = await api.chat(current);
    setHistory((items) => [...items, { role: "assistant", content: result.answer }]);
  }
  return (
    <div className="tab-content">
      <div className="chat-log">
        {history.map((item, index) => (
          <div key={`${item.role}-${index}`} className={`bubble ${item.role}`}>{item.content}</div>
        ))}
        {history.length === 0 ? <p className="muted">可询问整合理由，或要求保留/拆分知识点。</p> : null}
      </div>
      <div className="inline-input">
        <input value={message} onChange={(event) => setMessage(event.target.value)} />
        <button onClick={send}><Send size={16} /></button>
      </div>
    </div>
  );
}

function LearningTab() {
  return (
    <div className="tab-content material-grid">
      {[
        ["结构型", "思维导图", "由图谱视图生成结构化导航"],
        ["互动型", "闪卡+测验", "复用闯关游戏样例题库"],
        ["读写型", "整合报告", "一键生成 Markdown 报告"],
        ["展示型", "幻灯片", "NotebookLM 待配置，当前为占位"]
      ].map(([style, title, desc]) => (
        <article className="material-card" key={title}>
          <b>{style}</b>
          <h4>{title}</h4>
          <p>{desc}</p>
        </article>
      ))}
    </div>
  );
}

function GameTab() {
  const [tree, setTree] = React.useState<Record<string, unknown> | null>(null);
  React.useEffect(() => {
    api.game().then(setTree).catch(() => setTree(null));
  }, []);
  const levels = (tree?.levels as Array<Record<string, unknown>> | undefined) || [];
  return (
    <div className="tab-content">
      <div className="game-map">
        {levels.map((level, index) => (
          <div className="level-node" key={String(level.id)}>
            <span>{index + 1}</span>
            <div>
              <b>{String(level.title)}</b>
              <small>{(level.questions as unknown[] | undefined)?.length || 0} 题 · 重点关卡</small>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function FunctionPanel({ config, decisions, onIntegrate }: { config: ConfigStatus | null; decisions: Decision[]; onIntegrate: () => void }) {
  const [tab, setTab] = React.useState("integrate");
  const tabs = [
    ["integrate", "整合", GitMerge],
    ["rag", "问答", MessageSquare],
    ["chat", "对话", Brain],
    ["materials", "学习材料", FileText],
    ["game", "闯关", Gamepad2]
  ] as const;
  return (
    <aside className="right-panel">
      <div className="tabs">
        {tabs.map(([id, label, Icon]) => (
          <button key={id} className={tab === id ? "active" : ""} onClick={() => setTab(id)}>
            <Icon size={15} /> {label}
          </button>
        ))}
      </div>
      {tab === "integrate" ? <IntegrationTab decisions={decisions} onRefresh={onIntegrate} /> : null}
      {tab === "rag" ? <RagTab difyReady={Boolean(config?.dify.chat_configured)} /> : null}
      {tab === "chat" ? <ChatTab /> : null}
      {tab === "materials" ? <LearningTab /> : null}
      {tab === "game" ? <GameTab /> : null}
    </aside>
  );
}

function App() {
  const [config, setConfig] = React.useState<ConfigStatus | null>(null);
  const [textbooks, setTextbooks] = React.useState<Textbook[]>([]);
  const [activeId, setActiveId] = React.useState<string | null>("merged");
  const [graph, setGraph] = React.useState<KnowledgeGraph | null>(null);
  const [selected, setSelected] = React.useState<GraphNode | null>(null);
  const [query, setQuery] = React.useState("");
  const [bodySystem, setBodySystem] = React.useState("全部");
  const [stats, setStats] = React.useState<Record<string, number | boolean> | null>(null);
  const [decisions, setDecisions] = React.useState<Decision[]>([]);
  const [error, setError] = React.useState("");

  const refresh = React.useCallback(async () => {
    const [configResult, books, statsResult, decisionResult] = await Promise.all([api.config(), api.textbooks(), api.stats(), api.decisions()]);
    setConfig(configResult);
    setTextbooks(books);
    setStats(statsResult);
    setDecisions(decisionResult);
  }, []);

  React.useEffect(() => {
    refresh().catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, [refresh]);

  React.useEffect(() => {
    const loader = activeId === "merged" ? api.mergedGraph : () => api.graph(activeId || "merged");
    loader()
      .then((result) => {
        setGraph(result);
        setSelected(result.nodes[0] || null);
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, [activeId]);

  async function upload(file: File) {
    await api.upload(file);
    await refresh();
  }

  async function integrate() {
    await api.integrate();
    await refresh();
    const result = await api.mergedGraph();
    setGraph(result);
    setActiveId("merged");
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <Activity size={22} />
          <div>
            <h1>学科知识整合智能体</h1>
            <span>7 本医学教材 · 知识图谱 · RAG 问答 · 整合报告</span>
          </div>
        </div>
        <div className="status-group">
          <StatusPill ok={Boolean(config?.deepseek.configured)}>DeepSeek {config?.deepseek.configured ? "已配置" : "未配置"}</StatusPill>
          <StatusPill ok={Boolean(config?.dify.chat_configured)}>Dify {config?.dify.chat_configured ? "已配置" : "等待配置"}</StatusPill>
          <StatusPill ok>{textbooks.length} 本教材</StatusPill>
        </div>
      </header>
      {error ? <div className="error-banner">{error}</div> : null}
      <main className="workspace">
        <TextbookPanel textbooks={textbooks} activeId={activeId} onSelect={setActiveId} onUpload={upload} stats={stats} />
        <section className="center-panel">
          <div className="graph-toolbar">
            <div className="search-box">
              <Search size={16} />
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索知识点、定义或章节" />
            </div>
            <select value={bodySystem} onChange={(event) => setBodySystem(event.target.value)}>
              {BODY_SYSTEMS.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
          </div>
          <div className="graph-wrap">
            <GraphCanvas graph={graph} query={query} bodySystem={bodySystem} selected={selected} onSelect={setSelected} />
          </div>
          <NodeDetail node={selected} />
        </section>
        <FunctionPanel config={config} decisions={decisions} onIntegrate={integrate} />
      </main>
      <footer className="statusbar">
        <span>节点：{graph?.nodes.length || 0}</span>
        <span>关系：{graph?.edges.length || 0}</span>
        <span>RAG chunks：{formatNumber(stats?.rag_chunks)}</span>
      </footer>
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
