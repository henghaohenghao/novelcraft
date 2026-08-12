"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import apiClient from "@/lib/axios";
import ProtectedRoute from "@/components/ProtectedRoute";

interface Project {
  id: string;
  title: string;
  synopsis: string;
  genre: string;
  style: string;
  status: string;
  created_at: string;
}

function ProjectsContent() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [title, setTitle] = useState("");
  const [synopsis, setSynopsis] = useState("");
  const [genre, setGenre] = useState("");
  const [style, setStyle] = useState("");
  const [loading, setLoading] = useState(false);

  const fetchProjects = async () => {
    try {
      const response = await apiClient.get("/api/projects");
      setProjects(response.data);
    } catch (error) {
      console.error("Failed to fetch projects:", error);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    try {
      await apiClient.post("/api/projects", { title, synopsis, genre, style });
      setShowCreate(false);
      setTitle("");
      setSynopsis("");
      setGenre("");
      setStyle("");
      fetchProjects();
    } catch (error) {
      console.error("Failed to create project:", error);
    }
    setLoading(false);
  };

  const handleDelete = async (id: string) => {
    if (!confirm("确定删除此项目？")) return;
    try {
      await apiClient.delete(`/api/projects/${id}`);
      fetchProjects();
    } catch (error) {
      console.error("Failed to delete project:", error);
    }
  };

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex justify-between items-center mb-8">
        <h1 className="text-3xl font-bold text-claude-dark">我的项目</h1>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="btn-primary"
        >
          {showCreate ? "取消" : "新建项目"}
        </button>
      </div>

      {showCreate && (
        <form onSubmit={handleCreate} className="card p-8 mb-8">
          <h2 className="text-xl font-semibold text-claude-dark mb-6">创建新项目</h2>
          <div className="space-y-5">
            <div>
              <label className="block text-sm font-medium text-claude-dark mb-2">项目名称</label>
              <input
                type="text"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                className="input-base"
                placeholder="输入项目名称"
                required
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-claude-dark mb-2">梗概</label>
              <textarea
                value={synopsis}
                onChange={(e) => setSynopsis(e.target.value)}
                className="input-base h-32 resize-none"
                placeholder="输入小说梗概..."
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-claude-dark mb-2">类型</label>
                <input
                  type="text"
                  value={genre}
                  onChange={(e) => setGenre(e.target.value)}
                  className="input-base"
                  placeholder="如：玄幻、都市、悬疑"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-claude-dark mb-2">风格</label>
                <input
                  type="text"
                  value={style}
                  onChange={(e) => setStyle(e.target.value)}
                  className="input-base"
                  placeholder="如：古风、搞笑风、言情"
                />
              </div>
            </div>
            <div className="flex gap-3 pt-2">
              <button
                type="submit"
                disabled={loading}
                className="btn-primary disabled:opacity-50"
              >
                {loading ? "创建中..." : "创建项目"}
              </button>
              <button
                type="button"
                onClick={() => setShowCreate(false)}
                className="btn-secondary"
              >
                取消
              </button>
            </div>
          </div>
        </form>
      )}

      <div className="space-y-4">
        {projects.map((p) => (
          <div key={p.id} className="card p-6 flex justify-between items-start">
            <div className="flex-1">
              <Link
                href={`/projects/${p.id}`}
                className="text-xl font-semibold text-claude-dark hover:text-claude-brown transition-colors"
              >
                {p.title}
              </Link>
              <div className="flex gap-2 mt-2 text-sm text-claude-brown">
                {p.genre && <span>{p.genre}</span>}
                {p.style && <span>· {p.style}</span>}
                <span>· {p.status}</span>
                <span>· {new Date(p.created_at).toLocaleDateString("zh-CN")}</span>
              </div>
              {p.synopsis && (
                <p className="text-claude-brown mt-3 leading-relaxed line-clamp-2">
                  {p.synopsis}
                </p>
              )}
            </div>
            <button
              onClick={() => handleDelete(p.id)}
              className="ml-4 text-sm text-claude-brown hover:text-red-600 transition-colors"
            >
              删除
            </button>
          </div>
        ))}
        {projects.length === 0 && !showCreate && (
          <div className="text-center py-16">
            <p className="text-claude-brown text-lg mb-4">暂无项目</p>
            <button
              onClick={() => setShowCreate(true)}
              className="btn-primary"
            >
              创建第一个项目
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

export default function ProjectsPage() {
  return (
    <ProtectedRoute>
      <ProjectsContent />
    </ProtectedRoute>
  );
}