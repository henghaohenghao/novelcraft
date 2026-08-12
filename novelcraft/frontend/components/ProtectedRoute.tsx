"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/store/authStore";

export default function ProtectedRoute({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const { checkAuth } = useAuthStore();
  const [checked, setChecked] = useState(false);
  const [authed, setAuthed] = useState(false);

  useEffect(() => {
    const init = async () => {
      try {
        await checkAuth();
        // checkAuth 更新 store 后，重新读取
        const token = localStorage.getItem("access_token");
        if (token) {
          setAuthed(true);
        } else {
          router.push("/login");
        }
      } catch {
        router.push("/login");
      } finally {
        setChecked(true);
      }
    };
    init();
  }, [checkAuth, router]);

  if (!checked) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">正在验证身份...</p>
        </div>
      </div>
    );
  }

  if (!authed) {
    return null;
  }

  return <>{children}</>;
}
