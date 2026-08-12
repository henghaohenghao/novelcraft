"use client";

import { useState, useEffect, useCallback, useMemo } from "react";
import { useParams } from "next/navigation";
import dynamic from "next/dynamic";
import remarkGfm from "remark-gfm";
import ReactFlow, {
  type Node,
  type Edge,
  type NodeTypes,
  Position,
  MarkerType,
  Background,
  Controls,
  Handle,
  useNodesState,
  useEdgesState,
} from "reactflow";
import "reactflow/dist/style.css";
import AgentTimeline from "@/components/AgentTimeline";
import apiClient from "@/lib/axios";

const ReactMarkdown = dynamic(() => import("react-markdown"), { ssr: false });

// Agent 执行追踪类型
interface ToolCallRecord {
  tool_name: string;
  tool_args: Record<string, unknown>;
  tool_output?: string;
  status: "running" | "completed" | "error";
}

interface AgentStepRecord {
  agent_name: string;
  agent_label: string;
  started_at: string;
  finished_at: string;
  status: "running" | "completed" | "error";
  summary: string;
  tool_calls: ToolCallRecord[];
  output_preview: string;
}

interface Project {
  id: string;
  title: string;
  synopsis: string;
  genre: string;
  style: string;
  status: string;
}

interface Outline {
  id: string;
  title: string;
  content: string;
  node_type: string;
  sort_order: number;
  depth: number;
  branch_label: string | null;
  children: Outline[];
}

interface Character {
  id: string;
  name: string;
  alias: string | null;
  description: string;
  personality: string;
  background: string;
  status: string;
}

interface Chapter {
  id: string;
  title: string;
  content: string;
  summary: string;
  status: string;
  revision_count: number;
  review_feedback: string | null;
  chapter_number: number;
}

interface GraphData {
  nodes: { id: string; name: string; labels: string[] }[];
  edges: { source: string; target: string; relation_type: string; description: string }[];
}

const RELATION_ZH: Record<string, string> = {
  FRIEND: "朋友",
  ENEMY: "敌人",
  RELATIVE: "亲属",
  MENTOR: "导师",
  LOVER: "恋人",
  COLLEAGUE: "同僚",
  RIVAL: "对手",
  SUBORDINATE: "下属",
  MASTER: "师父",
  ALLY: "盟友",
};

const LABEL_COLORS: Record<string, { bg: string; border: string; text: string }> = {
  Character: { bg: "#f8fafc", border: "#64748b", text: "#1e293b" },
  Faction: { bg: "#fef7ed", border: "#c08457", text: "#7c2d12" },
  Location: { bg: "#f6f8f3", border: "#8a9a5b", text: "#3f4f24" },
  default: { bg: "#faf9f7", border: "#a8a29e", text: "#44403c" },
};

const RELATION_COLORS: Record<string, string> = {
  FRIEND: "#64748b",
  ENEMY: "#9f534c",
  RELATIVE: "#8b6f47",
  MENTOR: "#5f7f7a",
  LOVER: "#b36b7a",
  COLLEAGUE: "#6b7280",
  RIVAL: "#a16207",
  SUBORDINATE: "#78716c",
  MASTER: "#4f766d",
  ALLY: "#6f7f4e",
};

const LABEL_ZH: Record<string, string> = {
  Character: "人物",
  Faction: "势力",
  Location: "地点",
  default: "其他",
};

function Neo4jNode({ data }: { data: { label: string; nodeType: string } }) {
  const colors = LABEL_COLORS[data.nodeType] || LABEL_COLORS.default;
  const typeLabel = LABEL_ZH[data.nodeType] || LABEL_ZH.default;

  return (
    <div style={{ position: "relative" }}>
      <Handle type="target" position={Position.Top} style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
      <div
        title={`${data.label} · ${typeLabel}`}
        style={{
          width: 108,
          height: 108,
          borderRadius: "50%",
          background: colors.bg,
          border: `1.5px solid ${colors.border}`,
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          textAlign: "center",
          fontSize: 18,
          fontWeight: 700,
          color: colors.text,
          lineHeight: 1.2,
          padding: 14,
          boxShadow: "0 12px 28px rgba(15, 23, 42, 0.08), inset 0 1px 0 rgba(255,255,255,0.9)",
          wordBreak: "break-word",
          letterSpacing: "0.02em",
        }}
      >
        <span>{data.label}</span>
        <span
          style={{
            marginTop: 7,
            fontSize: 12,
            fontWeight: 500,
            color: "#78716c",
            letterSpacing: "0.08em",
          }}
        >
          {typeLabel}
        </span>
      </div>
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
      <Handle type="source" position={Position.Bottom} style={{ opacity: 0 }} />
    </div>
  );
}

const nodeTypes: NodeTypes = {
  neo4j: Neo4jNode,
};

function GraphView({ graph }: { graph: GraphData }) {
  const { rfNodes, rfEdges, stats } = useMemo(() => {
    const nodeCount = graph.nodes.length;
    const safeNodeCount = Math.max(nodeCount, 1);
    const centerX = 560;
    const centerY = 390;
    const radiusX = Math.max(320, Math.min(600, safeNodeCount * 62));
    const radiusY = Math.max(230, Math.min(400, safeNodeCount * 42));

    const rfNodes: Node[] = graph.nodes.map((node, i) => {
      const angle = (2 * Math.PI * i) / safeNodeCount - Math.PI / 2;
      return {
        id: node.id,
        type: "neo4j",
        position: {
          x: centerX + radiusX * Math.cos(angle) - 54,
          y: centerY + radiusY * Math.sin(angle) - 54,
        },
        data: { label: node.name, nodeType: node.labels[0] || "default" },
      };
    });

    const mergedEdges = Array.from(
      graph.edges
        .reduce<
          Map<
            string,
            {
              source: string;
              target: string;
              relationTypes: string[];
            }
          >
        >((acc, edge) => {
          const pairKey = [edge.source, edge.target].sort().join("--");
          const existing = acc.get(pairKey);

          if (!existing) {
            acc.set(pairKey, {
              source: edge.source,
              target: edge.target,
              relationTypes: [edge.relation_type],
            });
            return acc;
          }

          if (!existing.relationTypes.includes(edge.relation_type)) {
            existing.relationTypes.push(edge.relation_type);
          }

          return acc;
        }, new Map())
        .values()
    );

    const rfEdges: Edge[] = mergedEdges.map((edge, i) => {
      const relationColor = RELATION_COLORS[edge.relationTypes[0]] || "#78716c";
      const relationLabel = edge.relationTypes
        .map((type) => RELATION_ZH[type] || type)
        .join(" / ");

      return {
        id: `e-${edge.source}-${edge.target}-${i}`,
        source: edge.source,
        target: edge.target,
        label: relationLabel,
        type: "bezier",
        animated: false,
        markerEnd: { type: MarkerType.ArrowClosed, width: 18, height: 18, color: relationColor },
        style: { stroke: relationColor, strokeWidth: 2.2, strokeOpacity: 0.72 },
        labelStyle: {
          fontSize: 15,
          fontWeight: 600,
          fill: "#44403c",
        },
        labelBgStyle: {
          fill: "#fafaf9",
          fillOpacity: 0.92,
        },
        labelBgPadding: [8, 5] as [number, number],
        labelBgBorderRadius: 999,
      };
    });

    return { rfNodes, rfEdges, stats: { nodeCount, edgeCount: mergedEdges.length } };
  }, [graph]);

  const [nodes, setNodes, onNodesChange] = useNodesState(rfNodes);
  const [edges, setEdges, onEdgesChange] = useEdgesState(rfEdges);

  useEffect(() => {
    setNodes(rfNodes);
    setEdges(rfEdges);
  }, [rfNodes, rfEdges, setNodes, setEdges]);

  return (
    <div className="overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-sm">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-stone-100 bg-stone-50 px-5 py-4">
        <div>
          <div className="text-lg font-semibold text-stone-900">人物关系图谱</div>
          <div className="mt-1 text-sm text-stone-500">可拖拽节点、滚轮缩放，关系以曲线连接展示</div>
        </div>
        <div className="flex gap-2 text-sm">
          <span className="rounded-full border border-stone-200 bg-white px-3 py-1 text-stone-600">{stats.nodeCount} 个节点</span>
          <span className="rounded-full border border-stone-200 bg-white px-3 py-1 text-stone-600">{stats.edgeCount} 条关系</span>
        </div>
      </div>
      <div style={{ width: "100%", height: 700, position: "relative", background: "linear-gradient(135deg, #fbfaf8 0%, #f5f3ef 100%)" }}>
        <ReactFlow
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          nodeTypes={nodeTypes}
          fitView
          fitViewOptions={{ padding: 0.2 }}
          minZoom={0.18}
          maxZoom={2.2}
          defaultEdgeOptions={{
            type: "bezier",
            markerEnd: { type: MarkerType.ArrowClosed, color: "#78716c" },
          }}
          proOptions={{ hideAttribution: true }}
        >
          <Background color="#ddd6ce" gap={32} size={0.8} />
          <Controls />
        </ReactFlow>
      </div>
      <div className="flex flex-wrap items-center gap-3 border-t border-stone-100 bg-white px-5 py-3 text-sm text-stone-500">
        {Object.entries(LABEL_ZH).map(([type, label]) => {
          const colors = LABEL_COLORS[type] || LABEL_COLORS.default;
          return (
            <span key={type} className="flex items-center gap-1.5">
              <span style={{ width: 12, height: 12, borderRadius: "50%", background: colors.bg, border: `1.5px solid ${colors.border}`, display: "inline-block" }} />
              {label}
            </span>
          );
        })}
      </div>
    </div>
  );
}

/** 项目详情页面：大纲规划、人物工坊、章节写作、关系图谱四大模块 */
export default function ProjectDetailPage() {
  const params = useParams();
  const projectId = params.id as string;

  const [project, setProject] = useState<Project | null>(null);
  const [outlines, setOutlines] = useState<Outline[]>([]);
  const [characters, setCharacters] = useState<Character[]>([]);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [graph, setGraph] = useState<GraphData | null>(null);
  const [activeTab, setActiveTab] = useState<"outline" | "characters" | "writing" | "graph">("outline");
  const [generatingOutline, setGeneratingOutline] = useState(false);
  const [generatingChapter, setGeneratingChapter] = useState<string | null>(null);
  const [creatingChapter, setCreatingChapter] = useState<string | null>(null);
  const [streamContent, setStreamContent] = useState("");
  const [streamReviewFeedback, setStreamReviewFeedback] = useState("");
  const [agentTrace, setAgentTrace] = useState<AgentStepRecord[]>([]);
  const [chapterCount, setChapterCount] = useState(10);

  // 章节内容手动编辑状态
  const [editingChapterId, setEditingChapterId] = useState<string | null>(null);
  const [editingContent, setEditingContent] = useState("");
  const [savingChapter, setSavingChapter] = useState(false);

  // 大纲节点手动编辑状态
  const [editingOutlineId, setEditingOutlineId] = useState<string | null>(null);
  const [editingOutlineTitle, setEditingOutlineTitle] = useState("");
  const [editingOutlineContent, setEditingOutlineContent] = useState("");
  const [savingOutline, setSavingOutline] = useState(false);

  // Human-in-the-Loop：人工审核暂停状态
  type HumanReviewAction = "approve" | "revise" | "replan" | "edit";
  interface HumanReviewState {
    chapterId: string;
    threadId: string;
    reviewSummary: string;
    overallScore: number | null;
    passed: boolean;
    recommendedAction: string;
    issues: { severity?: string; category?: string; description?: string }[];
    revisionCount: number;
    draft: string;
  }
  const [humanReview, setHumanReview] = useState<HumanReviewState | null>(null);
  const [humanAction, setHumanAction] = useState<HumanReviewAction>("revise");
  const [humanFeedback, setHumanFeedback] = useState("");
  const [humanEditedContent, setHumanEditedContent] = useState("");
  const [resumingChapter, setResumingChapter] = useState<string | null>(null);

  /** 计算下一个章节的起始编号（接着已有大纲继续） */
  const nextChapterNumber = useMemo(() => {
    const flatten = (nodes: Outline[]): number[] =>
      nodes.flatMap((n) => [n.sort_order, ...flatten(n.children)]);
    const allSortOrders = flatten(outlines);
    return allSortOrders.length > 0 ? Math.max(...allSortOrders) + 2 : 1;
  }, [outlines]);

  const fetchProject = useCallback(async () => {
    const res = await apiClient.get(`/api/projects/${projectId}`);
    setProject(res.data);
  }, [projectId]);

  const fetchOutlines = useCallback(async () => {
    const res = await apiClient.get(`/api/outlines/project/${projectId}/tree`);
    setOutlines(res.data);
  }, [projectId]);

  const fetchCharacters = useCallback(async () => {
    const res = await apiClient.get(`/api/characters/project/${projectId}`);
    setCharacters(res.data);
  }, [projectId]);

  const fetchChapters = useCallback(async () => {
    const res = await apiClient.get(`/api/writing/chapters/project/${projectId}`);
    setChapters(res.data);
  }, [projectId]);

  const fetchGraph = useCallback(async () => {
    const res = await apiClient.get(`/api/characters/project/${projectId}/graph`);
    setGraph(res.data);
  }, [projectId]);

  useEffect(() => {
    fetchProject();
    fetchOutlines();
    fetchCharacters();
    fetchChapters();
    fetchGraph();
  }, [fetchProject, fetchOutlines, fetchCharacters, fetchChapters, fetchGraph]);

  /** AI 生成章节大纲 */
  const handleGenerateOutline = async () => {
    if (!project) return;
    setGeneratingOutline(true);
    try {
      await apiClient.post(`/api/outlines/generate`, {
        project_id: projectId,
        synopsis: project.synopsis,
        chapter_count: chapterCount,
      });
      fetchOutlines();
    } catch {}
    setGeneratingOutline(false);
  };

  /** 在大纲节点下创建章节 */
  const handleCreateChapter = async (outlineId: string, title: string, chapterNumber: number) => {
    setCreatingChapter(outlineId);
    try {
      await apiClient.post(`/api/writing/chapters`, {
        project_id: projectId,
        outline_id: outlineId,
        title,
        chapter_number: chapterNumber,
      });
      await fetchChapters();
      // 创建成功后跳转到写作 tab，给用户视觉反馈
      setActiveTab("writing");
    } catch (err: any) {
      const msg = err?.response?.data?.detail || err?.message || "未知错误";
      console.error("创建章节失败:", err);
      alert(`创建章节失败：${msg}`);
    } finally {
      setCreatingChapter(null);
    }
  };

  /** 进入章节内容编辑模式 */
  const handleStartEditChapter = (ch: Chapter) => {
    setEditingChapterId(ch.id);
    setEditingContent(ch.content || "");
  };

  /** 取消编辑 */
  const handleCancelEditChapter = () => {
    setEditingChapterId(null);
    setEditingContent("");
  };

  /** 保存编辑后的章节内容 */
  const handleSaveChapter = async (chapterId: string) => {
    setSavingChapter(true);
    try {
      await apiClient.put(`/api/writing/chapters/${chapterId}`, {
        content: editingContent,
      });
      await fetchChapters();
      setEditingChapterId(null);
      setEditingContent("");
    } catch (err) {
      console.error("保存章节失败:", err);
    }
    setSavingChapter(false);
  };

  /** 进入大纲节点编辑模式 */
  const handleStartEditOutline = (node: Outline) => {
    setEditingOutlineId(node.id);
    setEditingOutlineTitle(node.title);
    setEditingOutlineContent(node.content || "");
  };

  /** 取消大纲编辑 */
  const handleCancelEditOutline = () => {
    setEditingOutlineId(null);
    setEditingOutlineTitle("");
    setEditingOutlineContent("");
  };

  /** 保存编辑后的大纲节点 */
  const handleSaveOutline = async (outlineId: string) => {
    setSavingOutline(true);
    try {
      await apiClient.put(`/api/outlines/${outlineId}`, {
        title: editingOutlineTitle,
        content: editingOutlineContent,
      });
      await fetchOutlines();
      setEditingOutlineId(null);
      setEditingOutlineTitle("");
      setEditingOutlineContent("");
    } catch (err) {
      console.error("保存大纲失败:", err);
    }
    setSavingOutline(false);
  };

  /** 处理 SSE 流式响应（generate 与 resume 共用） */
  const processSSEStream = async (res: Response) => {
    const reader = res.body?.getReader();
    if (!reader) return;

    const decoder = new TextDecoder();
    let buffer = "";
    let isStreamingContent = false;

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      for (const line of lines) {
        if (line.startsWith("data: ")) {
          try {
            const { event: evt, data } = JSON.parse(line.slice(6));

            // --- Agent 步骤追踪事件 ---
            if (evt === "agent_step") {
              setAgentTrace((prev) => [...prev, data as AgentStepRecord]);
              continue;
            }

            if (evt === "status") {
              if (data.status === "writing") {
                isStreamingContent = true;
                setStreamContent("");
                setStreamReviewFeedback("");
                continue;
              }

              if (data.status === "drafted") {
                continue;
              }

              if (data.status === "reviewing") {
                isStreamingContent = false;
              }

              if (data.status === "reviewed" && data.feedback) {
                setStreamReviewFeedback(data.feedback);
                continue;
              }

              if (data.status === "supervisor_routing") {
                // Supervisor 路由信息已在 agent_step 中展示
                continue;
              }

              // 人工审核相关状态
              if (data.status === "human_review_pending") {
                setStreamContent((prev) => prev + `\n\n> ⏸️ ${data.message}\n`);
                continue;
              }
              if (data.status === "resumed") {
                setStreamContent((prev) => prev + `\n\n> ▶️ ${data.message}\n`);
                continue;
              }

              if (!isStreamingContent) {
                setStreamContent((prev) => prev + `\n> ${data.message}\n`);
              }
              // 显示计划预览
              if (data.status === "planned" && data.plan) {
                setStreamContent((prev) => prev + `\n### 计划预览\n\n${data.plan}\n\n`);
              }
            } else if (evt === "content") {
              setStreamContent((prev) => prev + data.chunk);
            } else if (evt === "revision_content_start") {
              setStreamContent((prev) => prev + `\n\n---\n\n> 📝 第 ${data.revision} 次修改后的内容：\n\n`);
            } else if (evt === "revision_content_end") {
              // revision content stream finished
            } else if (evt === "human_review_required") {
              // Human-in-the-Loop：图被 interrupt 暂停，展示决策面板
              setHumanReview({
                chapterId: data.chapter_id,
                threadId: data.thread_id,
                reviewSummary: data.review_summary || "",
                overallScore: data.overall_score,
                passed: data.passed,
                recommendedAction: data.recommended_action || "revise_full",
                issues: data.issues || [],
                revisionCount: data.revision_count || 0,
                draft: data.draft || "",
              });
              // 根据推荐动作预选决策
              const recMap: Record<string, HumanReviewAction> = {
                accept: "approve",
                revise_full: "revise",
                revise_issues: "revise",
                replan: "replan",
              };
              setHumanAction(recMap[data.recommended_action] || "revise");
              setHumanFeedback("");
              setHumanEditedContent(data.draft || "");
              setStreamContent((prev) => prev + `\n\n---\n\n> 🛑 等待人工审核决策（评分 ${data.overall_score ?? "?"}/10）\n`);
            } else if (evt === "result") {
              fetchChapters();
            } else if (evt === "error") {
              setStreamContent((prev) => prev + `\n\n❌ 错误：${data.message}\n`);
            }
          } catch {}
        }
      }
    }
  };

  /** 启动多智能体流水线生成章节（SSE 流式接收） */
  const handleGenerateChapter = async (chapterId: string) => {
    setGeneratingChapter(chapterId);
    setStreamContent("");
    setStreamReviewFeedback("");
    setAgentTrace([]);
    setHumanReview(null);

    try {
      const token = localStorage.getItem('access_token');
      // SSE 请求直连后端，绕过 Next.js rewrites（rewrites 会缓冲流式响应）
      const sseBaseURL = process.env.NEXT_PUBLIC_API_URL || '';
      const res = await fetch(`${sseBaseURL}/api/writing/chapters/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({ chapter_id: chapterId, style: project?.style || "" }),
      });
      await processSSEStream(res);
    } catch (err) {
      console.error("生成章节失败:", err);
      setStreamContent((prev) => prev + `\n❌ 生成失败: ${err}\n`);
    }
    setGeneratingChapter(null);
  };

  /** 恢复被人工审核暂停的章节生成（Human-in-the-Loop） */
  const handleResumeChapter = async () => {
    if (!humanReview) return;
    const chapterId = humanReview.chapterId;
    setResumingChapter(chapterId);
    setHumanReview(null);

    try {
      const token = localStorage.getItem('access_token');
      // SSE 请求直连后端，绕过 Next.js rewrites（rewrites 会缓冲流式响应）
      const sseBaseURL = process.env.NEXT_PUBLIC_API_URL || '';
      const res = await fetch(`${sseBaseURL}/api/writing/chapters/${chapterId}/resume`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          chapter_id: chapterId,
          action: humanAction,
          feedback: humanFeedback,
          edited_content: humanAction === "edit" ? humanEditedContent : "",
        }),
      });
      await processSSEStream(res);
    } catch (err) {
      console.error("恢复章节失败:", err);
      setStreamContent((prev) => prev + `\n❌ 恢复失败: ${err}\n`);
    }
    setResumingChapter(null);
  };

  /** 递归渲染大纲树形结构 */
  const renderOutlineTree = (nodes: Outline[], level: number = 0) => {
    return nodes.map((node) => (
      <div key={node.id} style={{ marginLeft: level * 24 }}>
        <div className="border border-claude-border rounded-lg p-3 mb-2 bg-white">
          {editingOutlineId === node.id ? (
            <div className="space-y-2">
              <input
                type="text"
                value={editingOutlineTitle}
                onChange={(e) => setEditingOutlineTitle(e.target.value)}
                className="w-full text-sm border border-claude-border rounded px-2 py-1 bg-white focus:outline-none focus:border-claude-accent font-medium text-claude-dark"
                placeholder="大纲标题"
              />
              <textarea
                value={editingOutlineContent}
                onChange={(e) => setEditingOutlineContent(e.target.value)}
                className="w-full text-sm border border-claude-border rounded p-2 bg-white focus:outline-none focus:border-claude-accent text-claude-brown leading-relaxed"
                rows={4}
                placeholder="大纲内容..."
              />
              <div className="flex gap-2 justify-end">
                <button
                  onClick={handleCancelEditOutline}
                  disabled={savingOutline}
                  className="btn-secondary text-xs px-2 py-1 disabled:opacity-50"
                >
                  取消
                </button>
                <button
                  onClick={() => handleSaveOutline(node.id)}
                  disabled={savingOutline}
                  className="btn-primary text-xs px-2 py-1 disabled:opacity-50"
                >
                  {savingOutline ? "保存中..." : "保存"}
                </button>
              </div>
            </div>
          ) : (
            <>
              <div className="flex justify-between items-center">
                <span className="font-medium text-claude-dark">
                  {node.branch_label && (
                    <span className="text-xs bg-claude-beige text-claude-brown px-1.5 py-0.5 rounded mr-2">
                      {node.branch_label}
                    </span>
                  )}
                  {node.title}
                </span>
                <div className="flex gap-1">
                  <button
                    onClick={() => handleStartEditOutline(node)}
                    className="text-xs border border-claude-border text-claude-dark px-2 py-1 rounded hover:bg-claude-beige transition"
                  >
                    编辑
                  </button>
                  <button
                    onClick={() => handleCreateChapter(node.id, node.title, node.sort_order + 1)}
                    disabled={!!creatingChapter}
                    className={`text-xs border border-claude-border px-2 py-1 rounded transition ${
                      creatingChapter
                        ? "text-claude-brown/50 cursor-not-allowed bg-claude-beige/50"
                        : "text-claude-dark hover:bg-claude-beige"
                    }`}
                  >
                    {creatingChapter === node.id ? "创建中..." : "创建章节"}
                  </button>
                </div>
              </div>
              {node.content && <p className="text-sm text-claude-brown mt-1">{node.content}</p>}
            </>
          )}
        </div>
        {node.children && renderOutlineTree(node.children, level + 1)}
      </div>
    ));
  };

  if (!project) {
    return <div className="text-center py-16 text-claude-brown">加载中...</div>;
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-claude-dark tracking-tight">{project.title}</h1>
        <p className="text-claude-brown mt-1">
          {project.genre} · {project.style} · 状态：{project.status}
        </p>
        {project.synopsis && (
          <p className="text-claude-dark mt-2 p-3 bg-claude-beige rounded-lg">{project.synopsis}</p>
        )}
      </div>

      <div className="flex gap-2 mb-6 border-b border-claude-border">
        {(["outline", "characters", "writing", "graph"] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-2 border-b-2 transition ${
              activeTab === tab
                ? "border-claude-dark text-claude-dark font-medium"
                : "border-transparent text-claude-brown hover:text-claude-dark"
            }`}
          >
            {tab === "outline" && "大纲规划"}
            {tab === "characters" && "人物工坊"}
            {tab === "writing" && "章节写作"}
            {tab === "graph" && "关系图谱"}
          </button>
        ))}
      </div>

      {activeTab === "outline" && (
        <div>
          <div className="flex gap-4 items-end mb-4">
            <div>
              <label className="block text-sm font-medium text-claude-brown mb-1">章节数量</label>
              <input
                type="number"
                value={chapterCount || ""}
                onChange={(e) => setChapterCount(Number(e.target.value))}
                className="border border-claude-border rounded-lg px-3 py-2 w-24 bg-white focus:outline-none focus:ring-2 focus:ring-claude-brown focus:border-transparent"
                min={1}
                max={50}
              />
            </div>
            <button
              onClick={handleGenerateOutline}
              disabled={generatingOutline || !project.synopsis}
              className="btn-primary disabled:opacity-50"
            >
              {generatingOutline
                ? "生成中..."
                : outlines.length > 0
                  ? `继续生成大纲（从第 ${nextChapterNumber} 章）`
                  : "AI 生成大纲"}
            </button>
            {!project.synopsis && (
              <span className="text-sm text-claude-brown/70">请先在项目设置中填写梗概</span>
            )}
            {outlines.length > 0 && project.synopsis && (
              <span className="text-sm text-claude-brown/70">
                将接着第 {nextChapterNumber - 1} 章继续生成 {chapterCount} 章
              </span>
            )}
          </div>
          <div className="space-y-1">
            {outlines.length > 0 ? renderOutlineTree(outlines) : (
              <p className="text-claude-brown/60 py-8 text-center">暂无大纲，点击"AI 生成大纲"自动生成</p>
            )}
          </div>
        </div>
      )}

      {activeTab === "characters" && (
        <div>
          <div className="mb-4 rounded-lg border border-claude-border bg-claude-beige px-4 py-3 text-sm text-claude-brown">
            人物会在生成章节后自动从正文中提取，并同步更新关系图谱。
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {characters.map((char) => (
              <div key={char.id} className="border border-claude-border rounded-lg p-4 bg-white">
                <h3 className="font-semibold text-lg text-claude-dark">
                  {char.name}
                  {char.alias && <span className="text-claude-brown/70 text-sm ml-2">({char.alias})</span>}
                </h3>
                <div className="text-sm text-claude-brown mt-2 space-y-1">
                  {char.personality && <p>性格：{char.personality}</p>}
                  {char.background && <p>背景：{char.background}</p>}
                  {char.description && <p>定位：{char.description}</p>}
                </div>
                <span className={`text-xs mt-2 inline-block px-2 py-0.5 rounded-full border ${
                  char.status === "alive"
                    ? "bg-claude-cream border-claude-border text-claude-dark"
                    : "bg-claude-beige border-claude-border text-claude-brown/70"
                }`}>
                  {char.status}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {activeTab === "writing" && (
        <div>
          <div className="space-y-4">
            {chapters.map((ch) => (
              <div key={ch.id} className="border border-claude-border rounded-lg p-4 bg-white">
                <div className="flex justify-between items-center mb-2">
                  <h3 className="font-semibold text-claude-dark">
                    第{ch.chapter_number}章 {ch.title}
                    <span className={`ml-2 text-xs px-2 py-0.5 rounded-full border ${
                      ch.status === "completed"
                        ? "bg-claude-cream border-claude-border text-claude-dark"
                        : "bg-claude-beige border-claude-border text-claude-brown"
                    }`}>
                      {ch.status}
                    </span>
                    {ch.revision_count > 0 && (
                      <span className="ml-2 text-xs text-claude-brown/60">修改{ch.revision_count}次</span>
                    )}
                  </h3>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleGenerateChapter(ch.id)}
                      disabled={!!generatingChapter || !!resumingChapter}
                      title={
                        generatingChapter && generatingChapter !== ch.id
                          ? `正在生成第 ${chapters.find(c => c.id === generatingChapter)?.chapter_number} 章，请等待完成`
                          : resumingChapter
                          ? "正在恢复章节生成，请等待"
                          : ""
                      }
                      className="btn-primary text-sm px-3 py-1 disabled:opacity-50"
                    >
                      {generatingChapter === ch.id ? "生成中..." : ch.content ? "重新生成" : "AI 生成"}
                    </button>
                    {ch.content && editingChapterId !== ch.id && (
                      <button
                        onClick={() => handleStartEditChapter(ch)}
                        className="btn-secondary text-sm px-3 py-1"
                      >
                        编辑
                      </button>
                    )}
                  </div>
                </div>
                {ch.summary && (
                  <div className="text-sm text-claude-brown bg-claude-cream p-2 rounded mb-2 prose prose-sm max-w-none">
                    <div className="font-medium mb-1">摘要：</div>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{ch.summary}</ReactMarkdown>
                  </div>
                )}
                {ch.review_feedback && (
                  <div className="text-sm text-claude-brown bg-claude-beige border border-claude-border p-2 rounded mb-2 prose prose-sm max-w-none">
                    <div className="font-medium mb-1">审查意见：</div>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {ch.review_feedback}
                    </ReactMarkdown>
                  </div>
                )}
                {ch.content && editingChapterId === ch.id && (
                  <div className="mt-2 space-y-2">
                    <textarea
                      value={editingContent}
                      onChange={(e) => setEditingContent(e.target.value)}
                      className="w-full text-sm border border-claude-border rounded p-3 bg-white focus:outline-none focus:border-claude-accent font-mono leading-relaxed"
                      rows={16}
                      placeholder="编辑章节内容..."
                    />
                    <div className="flex gap-2 justify-end">
                      <button
                        onClick={handleCancelEditChapter}
                        disabled={savingChapter}
                        className="btn-secondary text-sm px-3 py-1 disabled:opacity-50"
                      >
                        取消
                      </button>
                      <button
                        onClick={() => handleSaveChapter(ch.id)}
                        disabled={savingChapter}
                        className="btn-primary text-sm px-3 py-1 disabled:opacity-50"
                      >
                        {savingChapter ? "保存中..." : "保存"}
                      </button>
                    </div>
                  </div>
                )}
                {ch.content && editingChapterId !== ch.id && (
                  <div className="mt-2 p-3 bg-claude-cream rounded max-h-96 overflow-y-auto">
                    <div className="text-sm prose prose-sm max-w-none">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {ch.content}
                      </ReactMarkdown>
                    </div>
                  </div>
                )}
                {(generatingChapter === ch.id || resumingChapter === ch.id || (humanReview && humanReview.chapterId === ch.id)) && (
                  <div className="mt-2 space-y-3">
                    {/* Agent 执行时间线 */}
                    {agentTrace.length > 0 && (
                      <AgentTimeline steps={agentTrace} />
                    )}
                    <div className="p-3 bg-claude-cream rounded max-h-64 overflow-y-auto">
                      <div className="text-sm prose prose-sm max-w-none">
                        {streamContent ? (
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{streamContent}</ReactMarkdown>
                        ) : (
                          <span className="text-claude-brown/60">正在连接...</span>
                        )}
                      </div>
                    </div>
                    {streamReviewFeedback && (
                      <div className="p-3 bg-claude-beige border border-claude-border text-claude-brown rounded max-h-48 overflow-y-auto">
                        <div className="font-medium mb-1">审查意见：</div>
                        <div className="text-sm prose prose-sm max-w-none">
                          <ReactMarkdown remarkPlugins={[remarkGfm]}>{streamReviewFeedback}</ReactMarkdown>
                        </div>
                      </div>
                    )}
                    {/* Human-in-the-Loop 人工审核决策面板 */}
                    {humanReview && humanReview.chapterId === ch.id && (
                      <div className="p-4 bg-amber-50 border border-amber-300 rounded-lg space-y-3">
                        <div className="flex items-center justify-between">
                          <h4 className="font-semibold text-amber-900">
                            🛑 人工审核决策
                          </h4>
                          {humanReview.overallScore !== null && (
                            <span className="text-sm text-amber-800">
                              评分 {humanReview.overallScore}/10 · {humanReview.passed ? "通过" : "未通过"} · 已修改 {humanReview.revisionCount} 次
                            </span>
                          )}
                        </div>
                        {humanReview.reviewSummary && (
                          <p className="text-sm text-amber-800">{humanReview.reviewSummary}</p>
                        )}
                        {humanReview.issues.length > 0 && (
                          <div className="text-sm text-amber-900 space-y-1">
                            <div className="font-medium">审查问题：</div>
                            <ul className="list-disc list-inside space-y-0.5">
                              {humanReview.issues.slice(0, 6).map((iss, idx) => (
                                <li key={idx}>
                                  {iss.severity && <span className="text-xs bg-amber-200 text-amber-900 px-1 rounded mr-1">{iss.severity}</span>}
                                  {iss.category && <span className="text-xs text-amber-700 mr-1">[{iss.category}]</span>}
                                  {iss.description}
                                </li>
                              ))}
                            </ul>
                          </div>
                        )}
                        {/* 决策动作选择 */}
                        <div className="flex flex-wrap gap-2">
                          {([
                            { key: "approve", label: "✅ 接受草稿", desc: "直接采纳当前内容，结束流程" },
                            { key: "revise", label: "✏️ 让AI修改", desc: "根据反馈让修改Agent继续打磨" },
                            { key: "replan", label: "🔄 重新规划", desc: "推翻计划，从规划阶段重来" },
                            { key: "edit", label: "📝 手动编辑", desc: "亲自编辑内容后继续" },
                          ] as const).map((opt) => (
                            <button
                              key={opt.key}
                              onClick={() => setHumanAction(opt.key)}
                              title={opt.desc}
                              className={`px-3 py-1.5 text-sm rounded border transition ${
                                humanAction === opt.key
                                  ? "bg-amber-700 border-amber-700 text-white"
                                  : "bg-white border-amber-300 text-amber-900 hover:bg-amber-100"
                              }`}
                            >
                              {opt.label}
                            </button>
                          ))}
                        </div>
                        {/* 反馈输入（approve 之外的动作都可填） */}
                        {humanAction !== "approve" && (
                          <div>
                            <label className="text-sm font-medium text-amber-900 block mb-1">给 Agent 的反馈意见：</label>
                            <textarea
                              value={humanFeedback}
                              onChange={(e) => setHumanFeedback(e.target.value)}
                              placeholder="例如：第三段节奏太快，需要增加环境描写；人物对话不够自然..."
                              className="w-full text-sm border border-amber-300 rounded p-2 bg-white focus:outline-none focus:border-amber-500"
                              rows={3}
                            />
                          </div>
                        )}
                        {/* 手动编辑内容输入 */}
                        {humanAction === "edit" && (
                          <div>
                            <label className="text-sm font-medium text-amber-900 block mb-1">编辑章节内容：</label>
                            <textarea
                              value={humanEditedContent}
                              onChange={(e) => setHumanEditedContent(e.target.value)}
                              className="w-full text-sm border border-amber-300 rounded p-2 bg-white focus:outline-none focus:border-amber-500 font-mono"
                              rows={10}
                            />
                          </div>
                        )}
                        <div className="flex gap-2 pt-1">
                          <button
                            onClick={handleResumeChapter}
                            className="px-4 py-1.5 bg-amber-700 text-white text-sm rounded hover:bg-amber-800 transition"
                          >
                            提交决策并继续
                          </button>
                          <button
                            onClick={() => setHumanReview(null)}
                            className="px-4 py-1.5 bg-white border border-amber-300 text-amber-900 text-sm rounded hover:bg-amber-100 transition"
                          >
                            取消
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
            {chapters.length === 0 && (
              <p className="text-claude-brown/60 text-center py-8">
                暂无章节。请先在"大纲规划"中创建章节，然后在此生成内容。
              </p>
            )}
          </div>
        </div>
      )}

      {activeTab === "graph" && (
        <div>
          <h3 className="font-semibold text-claude-dark mb-4">人物关系图谱</h3>
          {graph && graph.nodes.length > 0 && (
            <GraphView graph={graph} />
          )}
          {(!graph || graph.nodes.length === 0) && (
            <p className="text-claude-brown/60 text-center py-8">暂无关系数据，请先在"人物工坊"中创建人物</p>
          )}
        </div>
      )}
    </div>
  );
}