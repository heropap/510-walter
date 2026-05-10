import React from "react";
import ReactDOM from "react-dom/client";
import { Activity, BookOpen, Brain, FileText, Gamepad2, GitMerge, Layers, MessageSquare, Minus, Network, Search, Send, UploadCloud } from "lucide-react";
import * as d3 from "d3";
import { api } from "./api";
import type { ConfigStatus, Decision, GraphEdge, GraphNode, KnowledgeGraph, RagCitation, Textbook } from "./types";
import "./styles.css";

const TEXTBOOK_COLORS = ["#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F", "#EDC948", "#B07AA1"];
const BODY_SYSTEMS = ["全部", "呼吸系统", "循环系统", "消化系统", "神经系统", "免疫系统", "感染病", "全身/通用"];

type ImportState = {
  status: "idle" | "running" | "success" | "error";
  fileName?: string;
  message?: string;
};

type GraphExpansionDepth = 1 | 2;

function formatNumber(value: unknown): string {
  if (typeof value !== "number") return "0";
  return value.toLocaleString("zh-CN");
}

function StatusPill({ ok, children }: { ok: boolean; children: React.ReactNode }) {
  return <span className={`pill ${ok ? "ok" : "warn"}`}>{children}</span>;
}

function citationTitle(citation: RagCitation): string {
  const title = citation.document_name || citation.title || citation.dataset_name;
  return String(title || "Dify 知识库片段");
}

function citationPreview(citation: RagCitation): string {
  const content = String(citation.content || citation.summary || "");
  return content.length > 180 ? `${content.slice(0, 180)}...` : content;
}

function GraphCanvas({
  graph,
  query,
  bodySystem,
  expansionDepth,
  expandedNodeIds,
  selected,
  onSelect,
  onToggleNode
}: {
  graph: KnowledgeGraph | null;
  query: string;
  bodySystem: string;
  expansionDepth: GraphExpansionDepth;
  expandedNodeIds: Set<string>;
  selected: GraphNode | null;
  onSelect: (node: GraphNode) => void;
  onToggleNode: (nodeId: string) => void;
}) {
  const ref = React.useRef<SVGSVGElement | null>(null);

  React.useEffect(() => {
    if (!ref.current || !graph) return;
    const svg = d3.select(ref.current);
    svg.selectAll("*").remove();
    const width = ref.current.clientWidth || 720;
    const height = ref.current.clientHeight || 620;
    const lowerQuery = query.trim().toLowerCase();
    const nodesById = new Map(graph.nodes.map((node) => [node.id, node]));
    const scopedNodes = graph.nodes.filter((node) => bodySystem === "全部" || node.body_system === bodySystem);
    const scopedNodeIds = new Set(scopedNodes.map((node) => node.id));
    const childIdsByParent = new Map<string, string[]>();
    const parentIdsByChild = new Map<string, string[]>();

    for (const edge of graph.edges) {
      if (edge.relation_type !== "contains") continue;
      const source = String(edge.source);
      const target = String(edge.target);
      if (!nodesById.has(source) || !nodesById.has(target)) continue;
      childIdsByParent.set(source, [...(childIdsByParent.get(source) || []), target]);
      parentIdsByChild.set(target, [...(parentIdsByChild.get(target) || []), source]);
    }

    const visibleNodeIds = new Set<string>();
    const visibleOrder: string[] = [];
    const maxNodes = 320;
    const addVisible = (nodeId: string) => {
      if (!scopedNodeIds.has(nodeId) || visibleNodeIds.has(nodeId) || visibleOrder.length >= maxNodes) return;
      visibleNodeIds.add(nodeId);
      visibleOrder.push(nodeId);
    };
    const addDescendants = (nodeId: string, remainingDepth: number) => {
      if (remainingDepth <= 0 || visibleOrder.length >= maxNodes) return;
      const childIds = childIdsByParent.get(nodeId) || [];
      for (const childId of childIds) {
        if (!scopedNodeIds.has(childId)) continue;
        addVisible(childId);
        addDescendants(childId, remainingDepth - 1);
      }
    };
    const addAncestors = (nodeId: string, remainingDepth: number) => {
      if (remainingDepth <= 0 || visibleOrder.length >= maxNodes) return;
      const parentIds = parentIdsByChild.get(nodeId) || [];
      for (const parentId of parentIds) {
        if (!scopedNodeIds.has(parentId)) continue;
        addAncestors(parentId, remainingDepth - 1);
        addVisible(parentId);
      }
    };
    const matchesQuery = (node: GraphNode) =>
      !lowerQuery || node.name.toLowerCase().includes(lowerQuery) || node.definition.toLowerCase().includes(lowerQuery);

    if (childIdsByParent.size === 0) {
      scopedNodes.filter(matchesQuery).slice(0, 260).forEach((node) => addVisible(node.id));
    } else if (lowerQuery) {
      scopedNodes
        .filter(matchesQuery)
        .slice(0, 120)
        .forEach((node) => {
          addAncestors(node.id, 2);
          addVisible(node.id);
          addDescendants(node.id, expansionDepth);
        });
    } else {
      const rootIds = scopedNodes
        .filter((node) => !(parentIdsByChild.get(node.id) || []).some((parentId) => scopedNodeIds.has(parentId)))
        .map((node) => node.id);
      const seedIds = rootIds.length > 0 ? rootIds : scopedNodes.map((node) => node.id);
      seedIds.slice(0, 90).forEach(addVisible);
      const processedExpandedIds = new Set<string>();
      for (let index = 0; index < visibleOrder.length && visibleOrder.length < maxNodes; index += 1) {
        const nodeId = visibleOrder[index];
        if (!expandedNodeIds.has(nodeId) || processedExpandedIds.has(nodeId)) continue;
        processedExpandedIds.add(nodeId);
        addDescendants(nodeId, expansionDepth);
      }
    }

    const filteredNodes = visibleOrder.map((nodeId) => nodesById.get(nodeId)).filter((node): node is GraphNode => Boolean(node));
    const nodeIds = new Set(filteredNodes.map((node) => node.id));
    const filteredEdges = graph.edges
      .filter((edge) => nodeIds.has(String(edge.source)) && nodeIds.has(String(edge.target)))
      .slice(0, 560);

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
      .on("click", (_event, d) => {
        onSelect(d);
        if ((childIdsByParent.get(d.id) || []).some((childId) => scopedNodeIds.has(childId))) {
          onToggleNode(d.id);
        }
      });

    node
      .append("circle")
      .attr("r", (d) => radius(d.frequency))
      .attr("fill", (d) => (d.source_textbooks?.length > 1 ? "#ff6b6b" : color(d.source_textbooks?.[0] || "整合")))
      .attr("stroke", (d) => (selected?.id === d.id ? "#111827" : "#ffffff"))
      .attr("stroke-width", (d) => (selected?.id === d.id ? 3 : 1.6));

    const expandableNode = node.filter((d) => (childIdsByParent.get(d.id) || []).some((childId) => scopedNodeIds.has(childId)));

    expandableNode
      .append("circle")
      .attr("class", "node-expander")
      .attr("cx", (d) => -radius(d.frequency) - 4)
      .attr("cy", (d) => -radius(d.frequency) - 4)
      .attr("r", 8)
      .attr("fill", (d) => (expandedNodeIds.has(d.id) ? "#ccfbf1" : "#ffffff"))
      .attr("stroke", "#0d9488")
      .attr("stroke-width", 1.5);

    expandableNode
      .append("text")
      .attr("class", "node-expander-symbol")
      .attr("x", (d) => -radius(d.frequency) - 4)
      .attr("y", (d) => -radius(d.frequency))
      .text((d) => (expandedNodeIds.has(d.id) ? "-" : "+"))
      .attr("text-anchor", "middle");

    node
      .append("text")
      .attr("x", (d) => radius(d.frequency) + 6)
      .attr("y", 5)
      .text((d) => d.name)
      .attr("font-size", 12.5)
      .attr("font-weight", 500)
      .attr("fill", "#1e293b")
      .clone(true)
      .lower()
      .attr("stroke", "#ffffff")
      .attr("stroke-width", 4)
      .attr("stroke-linejoin", "round");

    node.append("title").text((d) => {
      const childCount = (childIdsByParent.get(d.id) || []).filter((childId) => scopedNodeIds.has(childId)).length;
      return childCount > 0 ? `${d.name} · ${childCount} 个子节点` : d.name;
    });

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
  }, [graph, query, bodySystem, expansionDepth, expandedNodeIds, selected, onSelect, onToggleNode]);

  return <svg ref={ref} className="graph-svg" role="img" aria-label="知识图谱"></svg>;
}

function TextbookPanel({
  textbooks,
  activeId,
  onSelect,
  onUpload,
  importState,
  stats
}: {
  textbooks: Textbook[];
  activeId: string | null;
  onSelect: (id: string) => void;
  onUpload: (file: File) => Promise<void>;
  importState: ImportState;
  stats: Record<string, number | boolean> | null;
}) {
  const importing = importState.status === "running";
  return (
    <aside className="left-panel">
      <div className="panel-heading">
        <BookOpen size={18} />
        <span>教材管理</span>
      </div>
      <label className={`upload-box ${importing ? "busy" : ""}`} aria-busy={importing}>
        <UploadCloud size={22} />
        <span>{importing ? "正在导入..." : "上传 PDF / DOCX / MD"}</span>
        <input
          type="file"
          accept=".md,.markdown,.txt,.pdf,.docx"
          disabled={importing}
          onChange={(event) => {
            const file = event.target.files?.[0];
            if (file) {
              void onUpload(file).finally(() => {
                event.currentTarget.value = "";
              });
            }
          }}
        />
      </label>
      <div className={`import-flow ${importState.status}`}>
        <div className="import-flow-title">文件导入流程</div>
        <ol>
          <li className={importing || importState.status === "success" ? "active" : ""}>上传文件并转换 Markdown</li>
          <li className={importing || importState.status === "success" ? "active" : ""}>按标题拆分章节</li>
          <li className={importing || importState.status === "success" ? "active" : ""}>生成教材知识图谱</li>
          <li className={importing || importState.status === "success" ? "active" : ""}>刷新整合图谱和本地 RAG 索引</li>
        </ol>
        {importState.message ? <p>{importState.message}</p> : <p className="muted">支持 Markdown、TXT、PDF、DOCX。</p>}
        {importState.fileName ? <small>{importState.fileName}</small> : null}
      </div>
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
        <div className="stat-title">整合压缩统计</div>
        <div className="stat-row"><span>原始字符数</span><b>{formatNumber(stats?.source_chars)}</b></div>
        <div className="stat-row"><span>整合后字符</span><b>{formatNumber(stats?.merged_chars)}</b></div>
        <div className="stat-row"><span>压缩比率</span><b>{typeof stats?.compression_ratio === "number" ? `${(stats.compression_ratio * 100).toFixed(1)}%` : "—"}</b></div>
        <div style={{ marginTop: 8 }}>
          <StatusPill ok={Boolean(stats?.target_met)}>目标 ≤ 30%</StatusPill>
        </div>
      </div>
    </aside>
  );
}

function NodeDetail({ node }: { node: GraphNode | null }) {
  if (!node) {
    return (
      <div className="node-detail empty">
        <Layers size={20} />
        <span>点击图谱中的节点，查看定义、来源教材和医学标签</span>
      </div>
    );
  }
  const tags = [node.category, node.body_system, node.scale_level, node.stage].filter(Boolean);
  return (
    <div className="node-detail">
      <div className="detail-top">
        <h3>{node.name}</h3>
        <StatusPill ok={node.importance === "high"}>{node.importance === "high" ? "高优先级" : node.importance}</StatusPill>
      </div>
      <p>{node.definition}</p>
      {tags.length > 0 && (
        <div className="tag-grid">
          {tags.map((tag) => (
            <span key={tag}>{tag}</span>
          ))}
        </div>
      )}
      {node.evidence && <div className="evidence">{node.evidence}</div>}
      <small>来源：{node.source_textbooks?.join("、") || "整合图谱"} · 出现频次 {node.frequency}</small>
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
  const [question, setQuestion] = React.useState("肺炎链球菌的荚膜有什么作用？");
  const [answer, setAnswer] = React.useState("");
  const [citations, setCitations] = React.useState<RagCitation[]>([]);
  const [busy, setBusy] = React.useState(false);
  async function ask() {
    setBusy(true);
    try {
      const result = await api.ragQuery(question);
      setAnswer(result.answer);
      setCitations(result.citations || []);
    } catch (error) {
      setAnswer(error instanceof Error ? error.message : String(error));
      setCitations([]);
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
      <div className="citation-list">
        <div className="citation-heading">引用来源 {citations.length > 0 ? citations.length : ""}</div>
        {citations.length === 0 ? <p className="muted">暂无引用。请确认 Dify LLM 上下文已绑定知识检索结果。</p> : null}
        {citations.slice(0, 5).map((citation, index) => (
          <article key={`${citation.segment_id || citationTitle(citation)}-${index}`} className="citation-card">
            <div>
              <b>{citationTitle(citation)}</b>
              {typeof citation.score === "number" ? <span>{Math.round(citation.score * 100)}%</span> : null}
            </div>
            {citationPreview(citation) ? <p>{citationPreview(citation)}</p> : null}
            {citation.segment_position ? <small>片段 {citation.segment_position}</small> : null}
          </article>
        ))}
      </div>
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
  const [graphExpansionDepth, setGraphExpansionDepth] = React.useState<GraphExpansionDepth>(2);
  const [expandedGraphNodeIds, setExpandedGraphNodeIds] = React.useState<Set<string>>(() => new Set());
  const [stats, setStats] = React.useState<Record<string, number | boolean> | null>(null);
  const [decisions, setDecisions] = React.useState<Decision[]>([]);
  const [importState, setImportState] = React.useState<ImportState>({ status: "idle" });
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
        setExpandedGraphNodeIds(new Set());
      })
      .catch((err) => setError(err instanceof Error ? err.message : String(err)));
  }, [activeId]);

  const toggleGraphNode = React.useCallback((nodeId: string) => {
    setExpandedGraphNodeIds((current) => {
      const next = new Set(current);
      if (next.has(nodeId)) {
        next.delete(nodeId);
      } else {
        next.add(nodeId);
      }
      return next;
    });
  }, []);

  const collapseGraphNodes = React.useCallback(() => {
    setExpandedGraphNodeIds(new Set());
  }, []);

  async function upload(file: File) {
    setError("");
    setImportState({ status: "running", fileName: file.name, message: "正在上传并转换文件..." });
    try {
      const result = await api.upload(file);
      setImportState({ status: "running", fileName: file.name, message: "正在刷新教材列表、图谱和 RAG 索引..." });
      await refresh();
      setActiveId(result.textbook.id);
      const graphResult = await api.graph(result.textbook.id);
      setGraph(graphResult);
      setSelected(graphResult.nodes[0] || null);
      setExpandedGraphNodeIds(new Set());
      const chunks = result.rag_index?.chunks;
      const nodeCount = typeof result.graph_stats.node_count === "number" ? result.graph_stats.node_count : 0;
      const difyStatus = typeof result.dify_sync?.status === "string" ? result.dify_sync.status : "unknown";
      const difyChunks = typeof result.dify_sync?.chunks_sent === "number" ? result.dify_sync.chunks_sent : 0;
      const difyMessage =
        difyStatus === "synced"
          ? `，已同步 Dify ${difyChunks.toLocaleString("zh-CN")} 个 chunk`
          : difyStatus === "skipped"
            ? "，Dify 同步已跳过"
            : `，Dify 同步状态：${difyStatus}`;
      setImportState({
        status: "success",
        fileName: file.name,
        message: `已导入《${result.textbook.title}》，生成 ${nodeCount} 个节点${typeof chunks === "number" ? `，本地 RAG ${chunks.toLocaleString("zh-CN")} 个 chunk` : ""}${difyMessage}。`
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setError(message);
      setImportState({ status: "error", fileName: file.name, message });
    }
  }

  async function integrate() {
    await api.integrate();
    await refresh();
    const result = await api.mergedGraph();
    setGraph(result);
    setActiveId("merged");
    setExpandedGraphNodeIds(new Set());
  }

  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand">
          <Activity size={24} />
          <div>
            <h1>学科知识整合智能体</h1>
            <span>多教材知识图谱 · 智能整合 · RAG 问答</span>
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
        <TextbookPanel textbooks={textbooks} activeId={activeId} onSelect={setActiveId} onUpload={upload} importState={importState} stats={stats} />
        <section className="center-panel">
          <div className="graph-toolbar">
            <div className="search-box">
              <Search size={16} />
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="搜索知识点名称或定义..." />
            </div>
            <select value={bodySystem} onChange={(event) => setBodySystem(event.target.value)}>
              {BODY_SYSTEMS.map((item) => (
                <option key={item}>{item}</option>
              ))}
            </select>
            <select
              value={graphExpansionDepth}
              onChange={(event) => setGraphExpansionDepth(Number(event.target.value) as GraphExpansionDepth)}
              aria-label="展开深度"
              title="展开深度"
            >
              <option value={1}>子级</option>
              <option value={2}>孙级</option>
            </select>
            <button className="toolbar-icon-button" type="button" onClick={collapseGraphNodes} disabled={expandedGraphNodeIds.size === 0} aria-label="收起全部" title="收起全部">
              <Minus size={16} />
            </button>
          </div>
          <div className="graph-wrap">
            <GraphCanvas
              graph={graph}
              query={query}
              bodySystem={bodySystem}
              expansionDepth={graphExpansionDepth}
              expandedNodeIds={expandedGraphNodeIds}
              selected={selected}
              onSelect={setSelected}
              onToggleNode={toggleGraphNode}
            />
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
