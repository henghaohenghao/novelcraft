"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { useAuthStore } from "@/lib/store/authStore";

export default function Navigation() {
  const router = useRouter();
  const pathname = usePathname();
  const { user, isAuthenticated, logout, checkAuth } = useAuthStore();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    checkAuth();
  }, [checkAuth]);

  const handleLogout = () => {
    logout();
    router.push("/login");
  };

  if (!mounted) {
    return null;
  }

  const publicPaths = ["/login", "/register"];
  const isPublicPath = publicPaths.includes(pathname);

  return (
    <nav className="bg-white border-b border-claude-border">
      <div className="max-w-7xl mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-8">
          <a href="/" className="flex items-center gap-3 hover:opacity-80 transition-opacity">
            <img src="/logo.png" alt="NovelCraft Logo" className="h-14 w-auto" />
            <span className="text-2xl font-semibold text-claude-dark">NovelCraft</span>
          </a>
          {isAuthenticated && (
            <div className="flex items-center gap-6">
              <a
                href="/projects"
                className={`text-sm font-medium transition-colors ${
                  pathname === "/projects"
                    ? "text-claude-dark"
                    : "text-claude-brown hover:text-claude-dark"
                }`}
              >
                项目
              </a>
              <a
                href="/style-transfer"
                className={`text-sm font-medium transition-colors ${
                  pathname === "/style-transfer"
                    ? "text-claude-dark"
                    : "text-claude-brown hover:text-claude-dark"
                }`}
              >
                风格迁移
              </a>
              <a
                href="/collaboration"
                className={`text-sm font-medium transition-colors ${
                  pathname === "/collaboration"
                    ? "text-claude-dark"
                    : "text-claude-brown hover:text-claude-dark"
                }`}
              >
                协同编辑
              </a>
            </div>
          )}
        </div>

        <div className="flex items-center gap-4">
          {isAuthenticated && user ? (
            <>
              <span className="text-sm text-claude-brown">
                {user.full_name || user.username}
              </span>
              <button
                onClick={handleLogout}
                className="px-4 py-2 text-sm text-claude-brown hover:text-claude-dark border border-claude-border rounded-lg hover:border-claude-dark transition-all"
              >
                退出
              </button>
            </>
          ) : (
            !isPublicPath && (
              <>
                <a
                  href="/login"
                  className="px-4 py-2 text-sm text-claude-brown hover:text-claude-dark transition-colors"
                >
                  登录
                </a>
                <a
                  href="/register"
                  className="px-5 py-2 text-sm bg-claude-dark text-white rounded-lg hover:bg-claude-brown transition-colors font-medium"
                >
                  注册
                </a>
              </>
            )
          )}
        </div>
      </div>
    </nav>
  );
}
