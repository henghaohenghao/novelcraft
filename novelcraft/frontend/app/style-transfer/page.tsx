"use client";

import { useState } from "react";
import { useQuery, useMutation } from "@tanstack/react-query";

// 留空 => 相对路径，经由 next.config.js rewrites 转发到后端
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "";

interface Style {
  style_id: string;
  style_name: string;
  description: string;
  author_example: string;
}

export default function StyleTransferPage() {
  const [originalText, setOriginalText] = useState("");
  const [selectedStyle, setSelectedStyle] = useState("");
  const [transformedText, setTransformedText] = useState("");
  const [copied, setCopied] = useState(false);

  const { data: stylesData, isLoading: stylesLoading } = useQuery({
    queryKey: ["styles"],
    queryFn: async () => {
      const response = await fetch(`${API_BASE_URL}/api/style-transfer/styles`);
      return response.json();
    },
  });

  const transferMutation = useMutation({
    mutationFn: async (data: { original_text: string; style_id: string }) => {
      const response = await fetch(`${API_BASE_URL}/api/style-transfer/transfer`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...data, project_id: "demo-project" }),
      });
      const result = await response.json();
      if (!response.ok) {
        throw new Error(result.error || result.detail || `HTTP ${response.status}`);
      }
      return result;
    },
    onSuccess: (data) => {
      if (data.status === "completed" && data.transformed_text) {
        setTransformedText(data.transformed_text);
      } else if (data.status === "failed") {
        alert(`转换失败: ${data.error || "未知错误"}`);
      }
    },
    onError: (error: Error) => {
      alert(`请求失败: ${error.message}`);
    },
  });

  const handleTransfer = () => {
    if (!originalText || !selectedStyle) {
      alert("请输入文本并选择风格");
      return;
    }
    transferMutation.mutate({
      original_text: originalText,
      style_id: selectedStyle,
    });
  };

  const handleCopy = () => {
    navigator.clipboard.writeText(transformedText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const styles: Style[] = stylesData?.styles || [];

  return (
    <div className="max-w-6xl mx-auto space-y-8">
      <div>
        <h1 className="text-3xl font-bold text-claude-dark mb-2">风格迁移</h1>
        <p className="text-claude-brown">选择目标风格，一键转换文本韵味</p>
      </div>

      <div className="card p-8">
        <h2 className="text-lg font-semibold text-claude-dark mb-6">选择目标风格</h2>
        {stylesLoading ? (
          <div className="flex items-center justify-center py-12">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-claude-brown"></div>
          </div>
        ) : (
          <div className="grid md:grid-cols-3 gap-4">
            {styles.map((style) => (
              <button
                key={style.style_id}
                onClick={() => setSelectedStyle(style.style_id)}
                className={`p-5 rounded-lg border-2 text-left transition-all ${
                  selectedStyle === style.style_id
                    ? "border-claude-dark bg-claude-beige"
                    : "border-claude-border hover:border-claude-brown"
                }`}
              >
                <div className="font-semibold text-claude-dark mb-2">
                  {style.style_name}
                </div>
                <div className="text-sm text-claude-brown mb-3 leading-relaxed">
                  {style.description.split("\n")[0]}
                </div>
                <div className="text-xs text-claude-brown">
                  代表作：{style.author_example}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        <div className="card p-6">
          <h2 className="text-lg font-semibold text-claude-dark mb-4">原始文本</h2>
          <textarea
            value={originalText}
            onChange={(e) => setOriginalText(e.target.value)}
            placeholder="输入要转换的文本..."
            className="input-base h-64 resize-none"
          />
          <div className="mt-4 flex justify-between items-center">
            <span className="text-sm text-claude-brown">
              {originalText.length} 字
            </span>
            <button
              onClick={handleTransfer}
              disabled={transferMutation.isPending || !originalText || !selectedStyle}
              className="btn-primary disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {transferMutation.isPending ? "转换中..." : "开始转换"}
            </button>
          </div>
        </div>

        <div className="card p-6">
          <h2 className="text-lg font-semibold text-claude-dark mb-4">转换后文本</h2>
          <div className="w-full h-64 p-4 border border-claude-border rounded-lg bg-claude-beige overflow-y-auto">
            {transformedText ? (
              <p className="whitespace-pre-wrap text-claude-dark leading-relaxed">{transformedText}</p>
            ) : (
              <p className="text-claude-brown">转换结果将显示在这里...</p>
            )}
          </div>
          <div className="mt-4 flex justify-between items-center">
            <span className="text-sm text-claude-brown">
              {transformedText.length} 字
            </span>
            {transformedText && (
              <button
                onClick={handleCopy}
                className="btn-secondary"
              >
                {copied ? "已复制" : "复制"}
              </button>
            )}
          </div>
        </div>
      </div>

      <div className="bg-white border border-claude-border rounded-xl p-6">
        <h3 className="font-semibold text-claude-dark mb-3">使用提示</h3>
        <ul className="text-sm text-claude-brown space-y-2 leading-relaxed">
          <li>• 选择一个目标风格（如搞笑、古风等）</li>
          <li>• 输入要转换的文本（建议 100-500 字）</li>
          <li>• 点击"开始转换"按钮</li>
          <li>• 等待 1-3 秒，查看转换结果</li>
        </ul>
      </div>
    </div>
  );
}
