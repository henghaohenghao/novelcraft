"use client";

import { useState, useEffect, useRef } from "react";
import * as Y from "yjs";
import { Awareness } from "y-protocols/awareness";
import { Users, Wifi, WifiOff, Copy, Check, Save, LogOut } from "lucide-react";
import CollaborationEditorInner from "./CollaborationEditorInner";

// API 走相对路径（经 next.config.js rewrites 转发到后端）。
// WS 基于当前页面 host 动态构造，浏览器 https 时自动用 wss。
const API_URL = process.env.NEXT_PUBLIC_API_URL || "";
const getWsUrl = () => {
  if (process.env.NEXT_PUBLIC_WS_URL) return process.env.NEXT_PUBLIC_WS_URL;
  if (typeof window === "undefined") return "";
  const proto = window.location.protocol === "https:" ? "wss:" : "ws:";
  return `${proto}//${window.location.host}`;
};

const getColorForUser = (userId: string) => {
  // 柔和的大地色系，保持用户间区分度的同时贴合整体风格
  const colors = [
    "#CC9966", "#6B5B4F", "#8A9A5B", "#9F7E5C",
    "#A1887F", "#7C8B73", "#B08968", "#5F7F7A",
  ];
  const hash = userId.split("").reduce((acc, char) => acc + char.charCodeAt(0), 0);
  return colors[hash % colors.length];
};

interface CollaborationEditorProps {
  roomId: string;
  userId: string;
  userName: string;
  onLeave?: () => void;
}

interface User {
  user_id: string;
  user_name: string;
  connection_id: string;
}

export default function CollaborationEditor({
  roomId,
  userId,
  userName,
  onLeave,
}: CollaborationEditorProps) {
  const [status, setStatus] = useState<"connecting" | "connected" | "disconnected">("connecting");
  const [onlineUsers, setOnlineUsers] = useState<User[]>([]);
  const [ydoc] = useState(() => new Y.Doc());
  const [websocket, setWebsocket] = useState<WebSocket | null>(null);
  const [copied, setCopied] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isLoaded, setIsLoaded] = useState(false);

  // 创建 awareness，不使用 useState 以避免初始化问题
  const awarenessRef = useRef<Awareness | null>(null);

  useEffect(() => {
    if (!awarenessRef.current) {
      awarenessRef.current = new Awareness(ydoc);
      console.log("Awareness 创建成功:", awarenessRef.current);
    }
  }, [ydoc]);

  // 加载文档快照
  useEffect(() => {
    const loadSnapshot = async () => {
      try {
        const response = await fetch(`${API_URL}/api/collaboration/rooms/${roomId}/snapshot`);
        if (response.ok) {
          const data = await response.json();
          if (data.yjs_document) {
            const docBytes = Uint8Array.from(Buffer.from(data.yjs_document, "hex"));
            Y.applyUpdate(ydoc, docBytes);
            console.log("文档快照加载成功");
          }
        }
      } catch (error) {
        console.error("加载文档快照失败:", error);
      } finally {
        setIsLoaded(true);
      }
    };

    loadSnapshot();
  }, [roomId, ydoc]);

  useEffect(() => {
    if (!isLoaded) return;

    const awareness = awarenessRef.current;
    if (!awareness) {
      console.error("Awareness 未初始化");
      return;
    }

    console.log("Awareness 实例:", awareness);

    const connectionId = `conn-${Date.now()}-${Math.random().toString(36).substring(2, 9)}`;
    const wsUrl = `${getWsUrl()}/api/collaboration/ws/${roomId}?user_id=${userId}&user_name=${encodeURIComponent(userName)}&connection_id=${connectionId}`;

    const ws = new WebSocket(wsUrl);

    // 设置本地 awareness 状态
    try {
      awareness.setLocalStateField("user", {
        name: userName,
        color: getColorForUser(userId),
      });
      console.log("Awareness 状态设置成功");
    } catch (error) {
      console.error("设置 Awareness 状态失败:", error);
    }

    ws.onopen = () => {
      console.log("WebSocket 连接成功");
      setStatus("connected");
    };

    ws.onmessage = (event) => {
      try {
        const message = JSON.parse(event.data);
        console.log("收到消息:", message);

        if (message.type === "welcome") {
          console.log("欢迎消息:", message);
        } else if (message.type === "user_list") {
          console.log("在线用户列表:", message.users);
          setOnlineUsers(message.users || []);
        } else if (message.type === "yjs_update") {
          console.log("收到 Yjs 更新");
          const update = Uint8Array.from(Buffer.from(message.update, "hex"));
          Y.applyUpdate(ydoc, update, ws);
        }
      } catch (error) {
        console.error("处理消息错误:", error);
      }
    };

    ws.onerror = (error) => {
      console.error("WebSocket 错误:", error);
      setStatus("disconnected");
    };

    ws.onclose = () => {
      console.log("WebSocket 连接关闭");
      setStatus("disconnected");
    };

    setWebsocket(ws);

    // Yjs 更新监听
    const updateHandler = (update: Uint8Array, origin: any) => {
      console.log("本地 Yjs 更新", origin);
      if (origin !== ws && ws.readyState === WebSocket.OPEN) {
        const updateHex = Buffer.from(update).toString("hex");
        console.log("发送 Yjs 更新到服务器");
        ws.send(JSON.stringify({
          type: "yjs_update",
          update: updateHex,
        }));
      }
    };

    ydoc.on("update", updateHandler);

    // 心跳
    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send(JSON.stringify({ type: "ping" }));
      }
    }, 30000);

    // 定期保存快照
    const saveInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        saveSnapshot();
      }
    }, 60000);

    return () => {
      ydoc.off("update", updateHandler);
      clearInterval(pingInterval);
      clearInterval(saveInterval);
      if (awareness) {
        awareness.destroy();
      }
      ws.close();
    };
  }, [roomId, userId, userName, ydoc, isLoaded]);

  const saveSnapshot = async () => {
    if (isSaving || !websocket || websocket.readyState !== WebSocket.OPEN) return;

    setIsSaving(true);
    try {
      const stateVector = Y.encodeStateVector(ydoc);
      const docUpdate = Y.encodeStateAsUpdate(ydoc);

      websocket.send(JSON.stringify({
        type: "save_snapshot",
        state_vector: Buffer.from(stateVector).toString("hex"),
        document: Buffer.from(docUpdate).toString("hex"),
      }));

      console.log("快照保存请求已发送");
    } catch (error) {
      console.error("保存快照失败:", error);
    } finally {
      setTimeout(() => setIsSaving(false), 1000);
    }
  };

  const copyRoomLink = () => {
    const link = `${window.location.origin}/collaboration?room=${roomId}&name=${encodeURIComponent("新用户")}`;
    navigator.clipboard.writeText(link);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  if (!isLoaded) {
    return (
      <div className="min-h-screen bg-claude-cream flex items-center justify-center">
        <div className="text-claude-brown/60">加载文档中...</div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-claude-cream">
      <header className="border-b border-claude-border bg-claude-cream">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-4">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold text-claude-dark tracking-tight">实时协同编辑</h1>
            <div className="flex items-center space-x-3">
              <button
                onClick={saveSnapshot}
                disabled={isSaving}
                className="flex items-center space-x-2 px-3 py-2 border border-claude-border text-claude-dark rounded-lg hover:bg-claude-beige transition disabled:opacity-50"
              >
                <Save className="w-4 h-4" />
                <span className="text-sm">{isSaving ? "保存中..." : "保存"}</span>
              </button>
              <button
                onClick={copyRoomLink}
                className="flex items-center space-x-2 px-3 py-2 border border-claude-border text-claude-dark rounded-lg hover:bg-claude-beige transition"
              >
                {copied ? (
                  <>
                    <Check className="w-4 h-4" />
                    <span className="text-sm">已复制</span>
                  </>
                ) : (
                  <>
                    <Copy className="w-4 h-4" />
                    <span className="text-sm">分享房间</span>
                  </>
                )}
              </button>
              <button
                onClick={onLeave}
                className="flex items-center space-x-2 px-3 py-2 border border-claude-border text-claude-brown rounded-lg hover:bg-claude-beige transition"
              >
                <LogOut className="w-4 h-4" />
                <span className="text-sm">退出房间</span>
              </button>
              <div className="flex items-center space-x-2">
                {status === "connected" ? (
                  <Wifi className="w-5 h-5 text-claude-accent" />
                ) : (
                  <WifiOff className="w-5 h-5 text-claude-brown/50" />
                )}
                <span className="text-sm text-claude-brown">
                  {status === "connected" ? "已连接" : status === "connecting" ? "连接中..." : "未连接"}
                </span>
              </div>
              <div className="flex items-center space-x-2">
                <Users className="w-5 h-5 text-claude-brown" />
                <span className="text-sm text-claude-brown">{onlineUsers.length} 人在线</span>
              </div>
            </div>
          </div>
        </div>
      </header>

      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        {onlineUsers.length > 0 && (
          <div className="card p-4 mb-4">
            <div className="flex items-center space-x-3">
              <span className="text-sm font-medium text-claude-brown">在线用户:</span>
              <div className="flex items-center space-x-2">
                {onlineUsers.map((user) => (
                  <div
                    key={user.connection_id}
                    className="flex items-center space-x-1 px-3 py-1 rounded-full text-sm"
                    style={{
                      backgroundColor: `${getColorForUser(user.user_id)}1A`,
                      color: getColorForUser(user.user_id),
                    }}
                  >
                    <div
                      className="w-2 h-2 rounded-full"
                      style={{ backgroundColor: getColorForUser(user.user_id) }}
                    />
                    <span className="font-medium">{user.user_name}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        <div className="card p-8">
          {status === "connected" && awarenessRef.current ? (
            <>
              {console.log("渲染编辑器 - awareness:", awarenessRef.current)}
              <CollaborationEditorInner
                ydoc={ydoc}
                awareness={awarenessRef.current}
                userName={userName}
                userColor={getColorForUser(userId)}
              />
            </>
          ) : (
            <div className="flex items-center justify-center min-h-[500px] text-claude-brown/60">
              {status === "connecting" ? "正在连接协同服务器..." : awarenessRef.current ? "连接已断开，请刷新页面重试" : "正在初始化编辑器..."}
            </div>
          )}
        </div>

        <div className="mt-6 bg-claude-beige border border-claude-border rounded-lg p-4">
          <h3 className="font-semibold text-claude-dark mb-2">协同编辑提示</h3>
          <ul className="text-sm text-claude-brown space-y-1">
            <li>• 多人可以同时编辑，所有更改实时同步</li>
            <li>• 可以看到其他用户的光标位置和颜色</li>
            <li>• 基于 CRDT 算法，保证无冲突</li>
            <li>• 点击"保存"按钮手动保存，或自动每分钟保存一次</li>
            <li>• 点击"分享房间"按钮复制链接邀请其他用户</li>
          </ul>
        </div>
      </main>
    </div>
  );
}
