"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/store/authStore";

export default function Home() {
  const router = useRouter();
  const { isAuthenticated, checkAuth } = useAuthStore();
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const [isHoveringTitle, setIsHoveringTitle] = useState(false);
  const titleRef = useRef<HTMLHeadingElement>(null);

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  useEffect(() => {
    if (isAuthenticated) {
      router.push("/projects");
    }
  }, [isAuthenticated, router]);

  useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      setMousePos({ x: e.clientX, y: e.clientY });

      if (titleRef.current) {
        const rect = titleRef.current.getBoundingClientRect();
        const isHovering =
          e.clientX >= rect.left &&
          e.clientX <= rect.right &&
          e.clientY >= rect.top &&
          e.clientY <= rect.bottom;
        setIsHoveringTitle(isHovering);
      }
    };

    window.addEventListener("mousemove", handleMouseMove);
    return () => window.removeEventListener("mousemove", handleMouseMove);
  }, []);

  const getCirclePosition = () => {
    if (!titleRef.current) return { x: 0, y: 0 };
    const rect = titleRef.current.getBoundingClientRect();
    return {
      x: mousePos.x - rect.left,
      y: mousePos.y - rect.top,
    };
  };

  const circlePos = getCirclePosition();

  return (
    <div className="min-h-[85vh] relative">
      {/* Mouse Circle */}
      <div
        className="fixed pointer-events-none z-50 rounded-full transition-all duration-100 ease-out"
        style={{
          left: `${mousePos.x}px`,
          top: `${mousePos.y}px`,
          width: '160px',
          height: '160px',
          transform: 'translate(-50%, -50%)',
          backgroundColor: 'transparent',
        }}
      />

      {/* Hero Section */}
      <section className="max-w-4xl mx-auto text-center pt-12 pb-8">
        <div className="relative inline-block">
          {/* Base Title */}
          <h1
            ref={titleRef}
            className="text-6xl font-bold text-claude-dark mb-4 tracking-tight leading-tight"
          >
            AI 驱动的小说创作平台
          </h1>

          {/* White Title Overlay with Circular Mask */}
          <h1
            className="text-6xl font-bold text-white mb-4 tracking-tight leading-tight absolute top-0 left-0 pointer-events-none"
            style={{
              clipPath: isHoveringTitle
                ? `circle(45px at ${circlePos.x}px ${circlePos.y}px)`
                : 'circle(0px at 50% 50%)',
              transition: 'clip-path 0.1s ease-out',
            }}
          >
            AI 驱动的小说创作平台
          </h1>
        </div>
        <p className="text-xl text-claude-brown mb-8 leading-relaxed max-w-2xl mx-auto">
          多智能体协同、实时协作、风格定制<br />让创作更高效、更自由
        </p>
        <div className="flex justify-center gap-4">
          <Link
            href="/register"
            className="btn-primary"
          >
            开始创作
          </Link>
          <Link
            href="/login"
            className="btn-secondary"
          >
            登录
          </Link>
        </div>
      </section>

      {/* Features */}
      <section className="max-w-5xl mx-auto pt-2 pb-8">
        <div className="grid md:grid-cols-3 gap-5">
          <FeatureCard
            title="风格迁移"
            description="支持古龙、金庸、曹文轩等多种作家风格，一键转换文本风格，保持原意的同时赋予全新韵味"
          />
          <FeatureCard
            title="实时协同"
            description="多人同时编辑同一文档，无冲突协作机制，实时同步每一处修改，团队创作更流畅"
          />
          <FeatureCard
            title="多智能体"
            description="规划-写作-审查-修改完整循环，AI 团队协同工作，确保内容质量与创作效率"
          />
        </div>
      </section>

      {/* Stats */}
      {/* <section className="max-w-4xl mx-auto pt-2 pb-12">
        <div className="bg-white rounded-2xl border border-claude-border p-8">
          <div className="grid md:grid-cols-3 gap-8 text-center">
            <StatItem number="6+" label="支持的作家风格" />
            <StatItem number="50+" label="并发协同用户" />
            <StatItem number="99%+" label="工作流可靠性" />
          </div>
        </div>
      </section> */}

      {/* Footer */}
      <footer className="border-t border-claude-border mt-24">
        <div className="max-w-7xl mx-auto px-6 py-8">
          <div className="text-center text-claude-brown text-sm">
            © 2026 NovelCraft. All rights reserved.
          </div>
        </div>
      </footer>
    </div>
  );
}

function FeatureCard({
  title,
  description,
}: {
  title: string;
  description: string;
}) {
  return (
    <div className="card p-5 h-full">
      <h3 className="text-xl font-semibold text-claude-dark mb-2">{title}</h3>
      <p className="text-claude-brown leading-relaxed">{description}</p>
    </div>
  );
}

function StatItem({ number, label }: { number: string; label: string }) {
  return (
    <div>
      <div className="text-5xl font-bold text-claude-dark mb-2">{number}</div>
      <div className="text-claude-brown">{label}</div>
    </div>
  );
}