# 泡泡玛特前端项目

> FDE 面试作品 - React 18 + Vite 5 + FastAPI

## 项目结构

```
frontend/
├── index.html              # 入口 HTML
├── package.json            # 依赖配置
├── vite.config.js          # Vite 配置（端口 3000）
├── .env                    # 环境变量（VITE_API_BASE_URL）
├── public/
│   └── data/
│       └── cache.json      # .demo_cache.json 稳定副本（API 不可达时降级）
├── src/
│   ├── main.jsx            # React 入口（装配 BrowserRouter + ErrorBoundary + Lazy）
│   ├── App.jsx             # 布局壳（Nav + Footer + Banner）
│   ├── index.css           # 全局样式 + CSS 变量
│   ├── components/         # 共享组件
│   │   ├── Nav.jsx
│   │   ├── Footer.jsx
│   │   ├── PageHeader.jsx
│   │   ├── Placeholder.jsx
│   │   ├── DemoBanner.jsx
│   │   ├── ErrorBoundary.jsx
│   │   ├── ScrollToTop.jsx
│   │   ├── Loading.jsx
│   │   └── charts/
│   │       ├── TrendChart.jsx
│   │       └── PieChart.jsx
│   ├── pages/              # 路由级页面（lazy 加载）
│   │   ├── Landing.jsx
│   │   ├── Executive.jsx
│   │   ├── Supply.jsx
│   │   ├── Risk.jsx
│   │   └── NotFound.jsx
│   ├── services/
│   │   └── api.js          # API 客户端（三层降级：API → 本地 cache.json → null）
│   └── data/
│       └── mockData.js     # 演示数据，所有项标 _source 字段
```

## 快速启动

### 前端
```bash
npm install
npm run dev          # http://localhost:3000
npm run build        # 生产构建到 dist/
```

### 后端 API（演示用）
```bash
cd ../
uv add fastapi uvicorn
uv run python -m uvicorn api:app --host 0.0.0.0 --port 8000
# API 文档：http://localhost:8000/docs
```

### 后端 Streamlit（完整 Demo）
```bash
./run_demo.bat   # Windows
./run_demo.sh    # Mac/Linux
```

## 环境变量

### 前端 `.env`
```
VITE_API_BASE_URL=http://localhost:8000
VITE_API_KEY=    # 留空 = 不启用前端认证
```

### 后端 `.env`（项目根）
```
# FastAPI 按 STREAMLIT_PASSWORD 启用 API Key 认证
# 留空 = 不启用认证（演示场景）
STREAMLIT_PASSWORD=
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET  | `/` | API 自描述 |
| GET  | `/api/scenarios` | 三个预设场景 + cached 标记 |
| GET  | `/api/analyze?query=...` | 按 query 获取缓存中的分析 |
| POST | `/api/analyze` | 提交新查询（当前直接复用缓存） |

## 工程化亮点

### 共享架构
- Nav/Footer/PageHeader 在 App.jsx 统一管理
- Placeholder 统一占位符，3 个图表组件复用

### 健壮性
- `React.lazy + Suspense` 路由级 code splitting
- `ErrorBoundary` 防白屏
- `ScrollToTop` 修 SPA 滚动位置
- `api.js` 三层降级：API → 本地 cache.json → null

### 安全
- `normalize_query` 输入校验
- FastAPI `_check_auth` 钩子（按 env 启用）
- 全局异常处理器兜底

### 可维护
- 所有代码带 ponytail 注释解释"为什么"
- CSS 变量分层（index.css → page CSS → inline）
- mockData 标 `_source` 字段，方便面试官追问时回答

## 演示话术

面试时建议这么说：

> 这是独立的 React 前端门面，展示系统的三大应用场景。背后对接 Python Multi-Agent 后端，通过 FastAPI 暴露。设计基于 Stripe 的数据可信度 + Linear 的视觉舒适度，配色注入泡泡玛特品牌基因。
>
> 工程上：路由级 code splitting、错误边界、三层降级（API → 本地缓存 → null）、输入校验。前端配置 VITE_API_BASE_URL，后端走 uvicorn，几行就能上线。

---

*最后更新：2026-07-12*
