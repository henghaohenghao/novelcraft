# NovelCraft 前端实现文档

## 技术栈

- **框架**: Next.js 14 (App Router)
- **UI**: Tailwind CSS + Lucide Icons
- **状态管理**: Zustand + TanStack Query
- **协同编辑**: Tiptap + Yjs + WebSocket
- **HTTP 客户端**: Axios

## 项目结构

```
frontend/
├── src/
│   ├── app/
│   │   ├── page.tsx                    # 首页
│   │   ├── layout.tsx                  # 根布局
│   │   ├── providers.tsx               # 全局 Provider
│   │   ├── globals.css                 # 全局样式
│   │   ├── style-transfer/
│   │   │   └── page.tsx               # 风格迁移页面
│   │   └── collaboration/
│   │       └── page.tsx               # 协同编辑页面
│   └── components/
│       └── CollaborationEditor.tsx    # 协同编辑器组件
├── package.json
├── tsconfig.json
├── tailwind.config.js
└── next.config.js
```

## 已实现的页面

### 1. 首页 (`/`)

**功能**:
- 产品介绍
- 功能卡片展示
- 统计数据展示
- 导航链接

**特点**:
- 响应式设计
- 渐变背景
- 卡片悬停效果

### 2. 风格迁移页面 (`/style-transfer`)

**功能**:
- 风格列表展示
- 文本输入
- 实时风格转换
- 结果复制

**API 集成**:
```typescript
// 获取风格列表
GET /api/style-transfer/styles

// 执行风格迁移
POST /api/style-transfer/transfer
{
  "original_text": "...",
  "style_id": "gulong",
  "project_id": "demo"
}
```

**特点**:
- 使用 TanStack Query 管理状态
- 加载状态显示
- 错误处理
- 字数统计

### 3. 协同编辑页面 (`/collaboration`)

**功能**:
- 实时多人编辑
- 在线状态显示
- 光标位置共享
- 自动同步

**技术实现**:
- Tiptap 富文本编辑器
- Yjs CRDT 算法
- WebSocket 实时通信
- Collaboration Cursor 扩展

**URL 参数**:
```
/collaboration?room=room-123&user=user-001&name=张三
```

## 环境变量

创建 `.env.local`:

```bash
# 后端 API 地址
NEXT_PUBLIC_API_URL=http://localhost:8000

# WebSocket 地址
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

## 安装和运行

### 1. 安装依赖

```bash
cd novelcraft/frontend
npm install
```

### 2. 启动开发服务器

```bash
npm run dev
```

访问: http://localhost:3000

### 3. 构建生产版本

```bash
npm run build
npm start
```

## 核心组件

### CollaborationEditor

协同编辑器组件，集成 Tiptap + Yjs。

**Props**:
```typescript
interface CollaborationEditorProps {
  roomId: string;    // 房间 ID
  userId: string;    // 用户 ID
  userName: string;  // 用户名
}
```

**功能**:
- 实时协同编辑
- 光标位置共享
- 在线用户统计
- 连接状态显示

### Providers

全局 Provider 组件，提供 React Query 上下文。

```typescript
<QueryClientProvider client={queryClient}>
  {children}
</QueryClientProvider>
```

## API 集成

### 风格迁移 API

```typescript
// 获取风格列表
const { data } = useQuery({
  queryKey: ["styles"],
  queryFn: async () => {
    const response = await axios.get(`${API_BASE_URL}/api/style-transfer/styles`);
    return response.data;
  },
});

// 执行风格迁移
const mutation = useMutation({
  mutationFn: async (data) => {
    const response = await axios.post(
      `${API_BASE_URL}/api/style-transfer/transfer`,
      data
    );
    return response.data;
  },
});
```

### WebSocket 集成

```typescript
// 创建 Yjs 文档
const ydoc = new Y.Doc();

// 创建 WebSocket Provider
const provider = new WebsocketProvider(
  WS_URL,
  roomId,
  ydoc,
  {
    params: {
      user_id: userId,
      user_name: userName,
      connection_id: `conn-${Date.now()}`,
    },
  }
);

// 监听连接状态
provider.on("status", (event) => {
  setStatus(event.status);
});
```

## 样式系统

### Tailwind CSS

使用 Tailwind CSS 进行样式管理：

```typescript
// 按钮样式
className="bg-purple-600 text-white px-6 py-2 rounded-lg hover:bg-purple-700"

// 卡片样式
className="bg-white rounded-xl p-6 shadow-md hover:shadow-xl transition"

// 响应式布局
className="grid md:grid-cols-2 lg:grid-cols-4 gap-8"
```

### 自定义样式

在 `globals.css` 中定义编辑器样式：

```css
.ProseMirror {
  outline: none;
}

.collaboration-cursor__caret {
  border-left: 2px solid;
  pointer-events: none;
}
```

## 待实现功能

### 短期
- [ ] 项目管理页面
- [ ] 大纲编辑器
- [ ] 人物管理
- [ ] 工作流状态展示

### 中期
- [ ] 用户认证
- [ ] 项目设置
- [ ] 导出功能
- [ ] 历史版本

### 长期
- [ ] 插画生成
- [ ] 数据可视化
- [ ] 移动端适配
- [ ] PWA 支持

## 开发指南

### 添加新页面

1. 在 `src/app/` 下创建新目录
2. 创建 `page.tsx` 文件
3. 导出 React 组件

```typescript
// src/app/new-page/page.tsx
export default function NewPage() {
  return <div>New Page</div>;
}
```

### 添加新组件

1. 在 `src/components/` 下创建组件文件
2. 导出组件

```typescript
// src/components/MyComponent.tsx
export default function MyComponent() {
  return <div>My Component</div>;
}
```

### API 调用

使用 TanStack Query 管理 API 调用：

```typescript
import { useQuery, useMutation } from "@tanstack/react-query";
import axios from "axios";

// 查询
const { data, isLoading } = useQuery({
  queryKey: ["key"],
  queryFn: async () => {
    const response = await axios.get("/api/endpoint");
    return response.data;
  },
});

// 变更
const mutation = useMutation({
  mutationFn: async (data) => {
    const response = await axios.post("/api/endpoint", data);
    return response.data;
  },
});
```

## 故障排查

### 问题 1: WebSocket 连接失败

**解决方案**:
- 检查后端 WebSocket 服务是否运行
- 确认 `NEXT_PUBLIC_WS_URL` 配置正确
- 查看浏览器控制台错误信息

### 问题 2: API 请求失败

**解决方案**:
- 检查后端服务是否运行
- 确认 `NEXT_PUBLIC_API_URL` 配置正确
- 检查 CORS 配置

### 问题 3: 样式不生效

**解决方案**:
- 确认 Tailwind CSS 配置正确
- 重启开发服务器
- 清除 `.next` 缓存

## 性能优化

### 代码分割

Next.js 自动进行代码分割，每个页面独立打包。

### 图片优化

使用 Next.js Image 组件：

```typescript
import Image from "next/image";

<Image src="/logo.png" alt="Logo" width={200} height={50} />
```

### 懒加载

使用动态导入：

```typescript
import dynamic from "next/dynamic";

const HeavyComponent = dynamic(() => import("@/components/HeavyComponent"), {
  loading: () => <div>Loading...</div>,
});
```

## 部署

### Vercel 部署（推荐）

```bash
# 安装 Vercel CLI
npm i -g vercel

# 部署
vercel
```

### Docker 部署

```dockerfile
FROM node:18-alpine

WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
RUN npm run build

EXPOSE 3000
CMD ["npm", "start"]
```

---

**前端实现完成！** 🎉
