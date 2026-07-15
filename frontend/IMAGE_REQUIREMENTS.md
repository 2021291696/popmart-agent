# 图片需求清单（Image Requirements）

> **2026-07-12 更新**：所有"📊 需要图表"占位符已替换为 recharts 真实图表（趋势图 + 饼图）。
> 仍需静态图片资源列在下方，**已实现** 的项目保留作为历史记录。

---

## ✅ 仍需图片（P0）

### 首页 - Hero 区系统截图
- **文件名**：`hero-system-demo.png`
- **位置**：`Landing.jsx` Hero 区右侧（`<div className="placeholder-img architecture-preview">`）
- **内容**：展示 3 个 Agent（IP 情报 / 消费者洞察 / 防伪与二手）协同工作的截图
- **推荐尺寸**：1200×800px

### 首页 - 完整架构图
- **位置**：`Landing.jsx` 架构区（`full-architecture`）
- **推荐尺寸**：1400×900px

### 客诉应对页 - 防伪指南 4 张对比图
- 包装对比、包装 logo、防伪码位置、产品细节

---

## ✅ 已实现（不需要图片）

### 老板早会页（Executive）
- ~~LABUBU 热度趋势图~~ → TrendChart + mockData（`demoTrendData`）
- 实际渲染：折线图 + 面积填充，X 轴时间、Y 轴提及量

### 备货分析页（Supply）
- ~~销量趋势图~~ → TrendChart + mockData（`demoSalesTrend`）
- ~~区域热力图~~ → 暂留占位（地图库太重，演示阶段用文字描述即可）

### 客诉应对页（Risk）
- ~~风险趋势图（三条折线）~~ → TrendChart + mockData（`demoRiskTrend`）
- ~~投诉类型分布饼图~~ → PieChart + mockData（`demoComplaintTypes`）
- ~~假货平台气泡图~~ → 保留占位（演示阶段用 Top 5 表格替代）

---

## 🎨 工具与流程

- **截图**：Windows 用 Snipping Tool / Snipaste
- **图表绘制**：现已用 recharts 实时生成，无需图表素材
- **图标**：lucide-react（SVG，已装包）

---

*最后更新：2026-07-12*
