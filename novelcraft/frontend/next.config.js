/** @type {import('next').NextConfig} */

// 后端地址：浏览器访问不到（8000 未对外暴露），
// 由 Next.js 服务器在内部转发。默认指向本机 8000。
const BACKEND_ORIGIN = process.env.BACKEND_ORIGIN || "http://localhost:8000";

const nextConfig = {
  output: "standalone",
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_ORIGIN}/api/:path*`,
      },
    ];
  },
  transpilePackages: [
    "yjs",
    "y-websocket",
    "lib0",
    "@tiptap/extension-collaboration",
    "@tiptap/extension-collaboration-cursor",
    "reactflow",
    "react-markdown",
    "remark-gfm",
    "react-flow-renderer",
  ],
};

module.exports = nextConfig;