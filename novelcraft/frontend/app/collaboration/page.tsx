"use client";

import { Suspense, useState, useEffect } from "react";
import { useSearchParams } from "next/navigation";
import dynamic from "next/dynamic";
import { Plus, Users, Clock, ArrowRight, Trash2 } from "lucide-react";
import { useAuthStore } from "@/lib/store/authStore";

const CollaborationEditor = dynamic(
  () => import("@/components/CollaborationEditor"),
  { ssr: false }
);

const API_URL = process.env.NEXT_PUBLIC_API_URL || "";

interface Room {
  room_id: string;
  room_name: string;
  chapter_id: string;
  created_at: string;
}

interface Chapter {
  id: string;
  title: string;
  chapter_number: number;
}

function CollaborationPageContent() {
  const searchParams = useSearchParams();
  const roomIdFromUrl = searchParams.get("room");
  const { user } = useAuthStore();
  const userId = user?.id || searchParams.get("user") || `user-${Date.now()}`;
  const userName = user?.full_name || user?.username || searchParams.get("name") || "匿名用户";

  const [currentRoom, setCurrentRoom] = useState<string | null>(roomIdFromUrl);
  const [roomName, setRoomName] = useState("");
  const [rooms, setRooms] = useState<Room[]>([]);
  const [chapters, setChapters] = useState<Chapter[]>([]);
  const [selectedChapterId, setSelectedChapterId] = useState("");
  const [isCreating, setIsCreating] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [deletingRoomId, setDeletingRoomId] = useState<string | null>(null);

  useEffect(() => {
    loadRooms();
    loadChapters();
  }, []);

  const loadRooms = async () => {
    setIsLoading(true);
    try {
      const response = await fetch(`${API_URL}/api/collaboration/rooms`);
      if (response.ok) {
        const data = await response.json();
        setRooms(data.rooms || []);
      } else {
        console.error("加载房间列表失败:", response.status);
        setRooms([]);
      }
    } catch (error) {
      console.error("加载房间列表错误:", error);
      setRooms([]);
    } finally {
      setIsLoading(false);
    }
  };

  const loadChapters = async () => {
    try {
      const response = await fetch(`${API_URL}/api/writing/chapters`);
      if (response.ok) {
        const data = await response.json();
        setChapters(data.chapters || data || []);
      }
    } catch (error) {
      console.error("加载章节列表错误:", error);
    }
  };

  const createRoom = async () => {
    if (!roomName.trim()) {
      alert("请输入房间名称");
      return;
    }
    if (!selectedChapterId) {
      alert("请选择要协同编辑的章节");
      return;
    }

    setIsCreating(true);
    try {
      const response = await fetch(`${API_URL}/api/collaboration/rooms`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          chapter_id: selectedChapterId,
          room_name: roomName.trim(),
        }),
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "创建房间失败");
      }

      const room: Room = await response.json();
      setCurrentRoom(room.room_id);
      setRoomName("");
      await loadRooms();
    } catch (error: any) {
      console.error("创建房间错误:", error);
      alert(error.message || "创建房间失败，请重试");
    } finally {
      setIsCreating(false);
    }
  };

  const joinRoom = (roomId: string) => {
    setCurrentRoom(roomId);
  };

  const deleteRoom = async (roomId: string, roomName: string, e: React.MouseEvent) => {
    e.stopPropagation();

    if (!confirm(`确定要删除房间 "${roomName}" 吗？此操作不可恢复。`)) {
      return;
    }

    setDeletingRoomId(roomId);
    try {
      const response = await fetch(`${API_URL}/api/collaboration/rooms/${roomId}`, {
        method: "DELETE",
      });

      if (!response.ok) {
        const error = await response.json();
        throw new Error(error.detail || "删除房间失败");
      }

      // 刷新房间列表
      await loadRooms();
    } catch (error: any) {
      console.error("删除房间错误:", error);
      alert(error.message || "删除房间失败，请重试");
    } finally {
      setDeletingRoomId(null);
    }
  };

  if (!currentRoom) {
    return (
      <div className="min-h-screen bg-claude-cream">
        <header className="border-b border-claude-border">
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
            <h1 className="text-2xl font-bold text-claude-dark tracking-tight">实时协同编辑</h1>
          </div>
        </header>

        <main className="max-w-5xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          <div className="grid md:grid-cols-2 gap-6">
            {/* 创建房间 */}
            <div className="card p-6">
              <div className="flex items-center mb-4">
                <Plus className="w-6 h-6 text-claude-brown mr-2" />
                <h2 className="text-xl font-semibold text-claude-dark">创建新房间</h2>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-claude-brown mb-2">
                    选择章节
                  </label>
                  <select
                    value={selectedChapterId}
                    onChange={(e) => setSelectedChapterId(e.target.value)}
                    className="input-base"
                  >
                    <option value="">-- 请选择章节 --</option>
                    {chapters.map((ch) => (
                      <option key={ch.id} value={ch.id}>
                        第{ch.chapter_number}章 {ch.title}
                      </option>
                    ))}
                  </select>
                  {chapters.length === 0 && (
                    <p className="mt-1 text-xs text-claude-brown/60">暂无章节，请先在项目中创建章节</p>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-claude-brown mb-2">
                    房间名称
                  </label>
                  <input
                    type="text"
                    value={roomName}
                    onChange={(e) => setRoomName(e.target.value)}
                    placeholder="例如：第一章协同编辑"
                    className="input-base"
                    onKeyDown={(e) => {
                      if (e.key === "Enter" && !isCreating) {
                        createRoom();
                      }
                    }}
                  />
                </div>

                <button
                  onClick={createRoom}
                  disabled={isCreating}
                  className="btn-primary w-full flex items-center justify-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <Plus className="w-5 h-5" />
                  <span>{isCreating ? "创建中..." : "创建房间"}</span>
                </button>
              </div>
            </div>

            {/* 房间列表 */}
            <div className="card p-6">
              <div className="flex items-center mb-4">
                <Users className="w-6 h-6 text-claude-brown mr-2" />
                <h2 className="text-xl font-semibold text-claude-dark">现有房间</h2>
              </div>

              {isLoading ? (
                <div className="text-center text-claude-brown/60 py-8">加载中...</div>
              ) : rooms.length === 0 ? (
                <div className="text-center text-claude-brown/60 py-8">
                  暂无房间，创建第一个吧
                </div>
              ) : (
                <div className="space-y-3 max-h-96 overflow-y-auto">
                  {rooms.map((room) => (
                    <div
                      key={room.room_id}
                      className="border border-claude-border rounded-lg p-4 hover:border-claude-accent hover:shadow-md transition cursor-pointer group bg-white"
                      onClick={() => joinRoom(room.room_id)}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex-1">
                          <h3 className="font-semibold text-claude-dark mb-1">
                            {room.room_name}
                          </h3>
                          <div className="flex items-center text-xs text-claude-brown/70">
                            <Clock className="w-3 h-3 mr-1" />
                            {new Date(room.created_at).toLocaleString("zh-CN")}
                          </div>
                        </div>
                        <div className="flex items-center space-x-2">
                          <button
                            onClick={(e) => deleteRoom(room.room_id, room.room_name, e)}
                            disabled={deletingRoomId === room.room_id}
                            className="p-2 text-claude-brown hover:bg-claude-beige rounded-lg transition opacity-0 group-hover:opacity-100 disabled:opacity-50"
                            title="删除房间"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                          <ArrowRight className="w-5 h-5 text-claude-accent flex-shrink-0" />
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>

          <div className="mt-6 bg-claude-beige border border-claude-border rounded-lg p-4">
            <h3 className="font-semibold text-claude-dark mb-2">使用提示</h3>
            <ul className="text-sm text-claude-brown space-y-1">
              <li>• 创建房间后，可以分享房间链接给其他用户</li>
              <li>• 点击现有房间可以直接进入协同编辑</li>
              <li>• 多人可以同时编辑，所有更改实时同步</li>
              <li>• 基于 CRDT 算法，保证无冲突</li>
            </ul>
          </div>
        </main>
      </div>
    );
  }

  const leaveRoom = () => {
    setCurrentRoom(null);
  };

  return (
    <CollaborationEditor roomId={currentRoom} userId={userId} userName={userName} onLeave={leaveRoom} />
  );
}

export default function CollaborationPage() {
  return (
    <Suspense fallback={<div>加载中...</div>}>
      <CollaborationPageContent />
    </Suspense>
  );
}
