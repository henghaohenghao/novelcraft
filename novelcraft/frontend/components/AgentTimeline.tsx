"use client";

import { useState } from "react";

// --- 类型定义 ---

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

// --- 样式映射 ---
// 统一采用 Claude 大地色系，通过深浅与点缀色区分不同 Agent，避免五颜六色

const AGENT_STYLES: Record<
  string,
  { bg: string; border: string; text: string; icon: string; dot: string }
> = {
  supervisor: {
    bg: "bg-claude-beige",
    border: "border-claude-border",
    text: "text-claude-dark",
    icon: "🧠",
    dot: "#2A2420",
  },
  planner: {
    bg: "bg-claude-cream",
    border: "border-claude-border",
    text: "text-claude-brown",
    icon: "📋",
    dot: "#6B5B4F",
  },
  writer: {
    bg: "bg-claude-cream",
    border: "border-claude-border",
    text: "text-claude-brown",
    icon: "✍️",
    dot: "#CC9966",
  },
  reviewer: {
    bg: "bg-claude-beige",
    border: "border-claude-border",
    text: "text-claude-dark",
    icon: "🔍",
    dot: "#8A9A5B",
  },
  reviser: {
    bg: "bg-claude-cream",
    border: "border-claude-border",
    text: "text-claude-brown",
    icon: "🔧",
    dot: "#9F7E5C",
  },
};

const TOOL_DISPLAY_NAMES: Record<string, string> = {
  search_character_relations: "查询角色关系",
  search_world_setting: "查询世界观设定",
  get_previous_chapter_summary: "获取前章摘要",
  check_character_consistency: "检查角色一致性",
  lookup_style_guide: "查询风格指南",
  verify_plot_logic: "验证情节逻辑",
  verify_character_behavior: "验证人物行为",
  verify_setting_consistency: "验证设定一致性",
  targeted_revise: "精准局部修改",
};

// --- 子组件 ---

function ToolCallItem({ tool }: { tool: ToolCallRecord }) {
  const [expanded, setExpanded] = useState(false);
  const displayName = TOOL_DISPLAY_NAMES[tool.tool_name] || tool.tool_name;

  const statusIcon =
    tool.status === "completed" ? (
      <span className="text-claude-accent">✓</span>
    ) : tool.status === "running" ? (
      <span className="text-claude-brown animate-pulse">●</span>
    ) : (
      <span className="text-claude-brown/50">✗</span>
    );

  // 提取关键参数用于简短展示
  const argsPreview = Object.entries(tool.tool_args)
    .slice(0, 2)
    .map(([k, v]) => `${k}: ${String(v).slice(0, 30)}`)
    .join(", ");

  return (
    <div className="ml-6 my-1">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 text-xs w-full text-left hover:bg-white/60 rounded px-2 py-1 transition-colors"
      >
        {statusIcon}
        <span className="font-mono text-claude-brown">{displayName}</span>
        {argsPreview && (
          <span className="text-claude-brown/50 truncate">({argsPreview})</span>
        )}
        <span className="text-claude-brown/40 ml-auto">{expanded ? "▲" : "▼"}</span>
      </button>
      {expanded && tool.tool_output && (
        <div className="ml-6 mt-1 p-2 bg-white rounded border border-claude-border text-xs text-claude-brown max-h-40 overflow-y-auto whitespace-pre-wrap">
          {tool.tool_output.length > 500
            ? tool.tool_output.slice(0, 500) + "..."
            : tool.tool_output}
        </div>
      )}
    </div>
  );
}

function AgentStepCard({
  step,
  isLast,
}: {
  step: AgentStepRecord;
  isLast: boolean;
}) {
  const [expanded, setExpanded] = useState(false);
  const style = AGENT_STYLES[step.agent_name] || {
    bg: "bg-claude-cream",
    border: "border-claude-border",
    text: "text-claude-dark",
    icon: "🤖",
    dot: "#A8A29E",
  };

  const statusBadge =
    step.status === "completed" ? (
      <span className="inline-flex items-center gap-1 text-xs bg-claude-beige text-claude-dark px-2 py-0.5 rounded-full">
        ✓ 完成
      </span>
    ) : step.status === "running" ? (
      <span className="inline-flex items-center gap-1 text-xs bg-claude-beige text-claude-brown px-2 py-0.5 rounded-full animate-pulse">
        ● 执行中
      </span>
    ) : (
      <span className="inline-flex items-center gap-1 text-xs bg-claude-beige text-claude-brown/70 px-2 py-0.5 rounded-full">
        ✗ 错误
      </span>
    );

  return (
    <div className="relative flex gap-3">
      {/* 时间线竖线 */}
      {!isLast && (
        <div className="absolute left-[19px] top-12 bottom-0 w-0.5 bg-claude-border" />
      )}

      {/* 节点圆点 */}
      <div
        className={`relative z-10 flex-shrink-0 w-10 h-10 rounded-full ${style.bg} ${style.border} border-2 flex items-center justify-center text-lg shadow-sm`}
      >
        {style.icon}
      </div>

      {/* 卡片内容 */}
      <div className={`flex-1 mb-3`}>
        <div
          className={`rounded-lg border ${style.border} ${style.bg} shadow-sm overflow-hidden`}
        >
          {/* 头部 */}
          <button
            onClick={() => setExpanded(!expanded)}
            className={`w-full flex items-center justify-between px-4 py-2.5 hover:brightness-95 transition-all`}
          >
            <div className="flex items-center gap-2">
              <span className={`font-semibold text-sm ${style.text}`}>
                {step.agent_label}
              </span>
              {statusBadge}
            </div>
            <div className="flex items-center gap-2">
              {step.tool_calls.length > 0 && (
                <span className="text-xs text-claude-brown/50">
                  {step.tool_calls.length} 个工具调用
                </span>
              )}
              <span className="text-claude-brown/40 text-xs">
                {expanded ? "▲" : "▼"}
              </span>
            </div>
          </button>

          {/* 摘要（始终显示） */}
          {step.summary && (
            <div className="px-4 py-2 border-t border-claude-border bg-white/50">
              <p className="text-xs text-claude-brown">{step.summary}</p>
            </div>
          )}

          {/* 展开详情：工具调用 + 输出预览 */}
          {expanded && (
            <div className="px-4 py-3 border-t border-claude-border bg-white/30 space-y-2">
              {/* 工具调用列表 */}
              {step.tool_calls.length > 0 && (
                <div>
                  <div className="text-xs font-medium text-claude-brown mb-1">
                    工具调用
                  </div>
                  {step.tool_calls.map((tc, i) => (
                    <ToolCallItem key={i} tool={tc} />
                  ))}
                </div>
              )}

              {/* 输出预览 */}
              {step.output_preview && (
                <div>
                  <div className="text-xs font-medium text-claude-brown mb-1">
                    输出预览
                  </div>
                  <div className="p-2 bg-white rounded border border-claude-border text-xs text-claude-brown max-h-40 overflow-y-auto whitespace-pre-wrap">
                    {step.output_preview.length > 500
                      ? step.output_preview.slice(0, 500) + "..."
                      : step.output_preview}
                  </div>
                </div>
              )}

              {/* 时间戳 */}
              <div className="text-xs text-claude-brown/40">
                {step.started_at && new Date(step.started_at).toLocaleTimeString()}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// --- 主组件 ---

export default function AgentTimeline({
  steps,
}: {
  steps: AgentStepRecord[];
}) {
  if (steps.length === 0) {
    return null;
  }

  return (
    <div className="rounded-xl border border-claude-border bg-white shadow-sm overflow-hidden">
      <div className="px-5 py-3 border-b border-claude-border bg-claude-cream">
        <div className="flex items-center justify-between">
          <div>
            <h3 className="text-sm font-semibold text-claude-dark">
              多智能体执行时间线
            </h3>
            <p className="text-xs text-claude-brown mt-0.5">
              Supervisor 动态调度各 Agent，Agent 自主调用工具完成任务
            </p>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full" style={{ background: "#2A2420" }} />
            <span className="text-xs text-claude-brown">调度</span>
            <span className="w-2 h-2 rounded-full ml-2" style={{ background: "#6B5B4F" }} />
            <span className="text-xs text-claude-brown">规划</span>
            <span className="w-2 h-2 rounded-full ml-2" style={{ background: "#CC9966" }} />
            <span className="text-xs text-claude-brown">写作</span>
            <span className="w-2 h-2 rounded-full ml-2" style={{ background: "#8A9A5B" }} />
            <span className="text-xs text-claude-brown">审查</span>
            <span className="w-2 h-2 rounded-full ml-2" style={{ background: "#9F7E5C" }} />
            <span className="text-xs text-claude-brown">修改</span>
          </div>
        </div>
      </div>
      <div className="p-4">
        {steps.map((step, i) => (
          <AgentStepCard
            key={i}
            step={step}
            isLast={i === steps.length - 1}
          />
        ))}
      </div>
    </div>
  );
}
