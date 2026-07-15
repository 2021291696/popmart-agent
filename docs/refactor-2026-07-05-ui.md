# UI 重构计划 — 2026-07-05

> **Scope**: 在 `D:/MyAIWorkspace/notes/实习/泡泡玛特重构/app.py` 及其相关文件中,
> 修正全局审查发现的硬 bug 和视觉混乱。按 Ponytail 梯子分阶段,推荐顺序执行,每阶段都保留可运行的最小可用版本。

> **📌 状态(2026-07-09)**：P0 硬 bug + P1 视觉清理 + P2 契约改动(`agents_meta.py` 抽出、`quality_inference.py` 拆出、`final_answer_source` 字段、`.txt` prompt)全部实施完成。本文件保留作历史决策记录，**不再作为执行依据**。后续变更以 git log + 当前代码为准。
>
> **📌 状态(2026-07-11)**：体感/安全 P0–P2（失败不落缓存、假绿修复、登录冷却与退出登录等）见 `docs/ux-security-2026-07-11.md`；本文件仍为 07-05 UI 重构历史记录。

---

## ⚠️ 硬 bug(P0 — 影响功能)

| # | 文件:行 | 问题 | 修复 |
|---|---|---|---|
| 1 | `app.py:305-306` | Agent 头部的 alpha 拼接是无效路径 | 用 `st.status()` 替代 — Streamlit 原生,自带色彩,0 行 CSS |
| 2 | `app.py:313` | `qr:.2f` 当 quality_score 为 None 时崩溃 | 改成 `f"{qr:.2f}" if qr is not None else "—"`,而且根本不该取不到(说明逻辑有漏) |
| 3 | `app.py:32, 159` | `import json as _json` 与 `import json` 重名 | 只留 `import json` 一行 |
| 4 | `app.py:295, 425, 427` | `next()` 用法巧合能工作但脆弱 | 改成 dict 索引或 dict.get |
| 5 | `app.py:219-237` | `try: ... except Exception: pass` 吞错 | 改成只 `try`,无 chunks 时显示"加载数据失败",有 chunks 时显示计数 |

---

## 💅 视觉/UX 混乱(P1 — 影响观感)

### 行级快捷删(Ponytail rung 1,YAGNI = 删比改便宜)

| # | 位置 | 操作 | 理由 |
|---|---|---|---|
| 6 | `app.py:384-399` | 删"Agent 最终输出 →" + 下面 600 字截断 div | ReAct 步骤表格已经展示全过程,Agent 最终输出在 `_synthesize` 里已经被综合进最终报告 — **重复 2 次** |
| 7 | `app.py:320-330` | 删"工具调用:"统计行 | Action 列已经列出工具名,Step 计数 N 行 = 调用 N 次 |
| 8 | `app.py:401-411` | 删"综合分析报告" + 灰色边框的包裹 div | Streamlit 的 `st.markdown` 已经支持 markdown 渲染,包装 div 是装饰噪音 |
| 9 | `app.py:218-237` | 删"已载入: 36 chunks · ..." 那行 | **它属于 sidebar** 而不是输入区 |
| 10 | `app.py:421` | 删 `sub` 提取重复逻辑,直接用 `next(filter(...))` | 性能忽略,可读性大升 |

### 结构改(rung 4-5,中量)

| # | 位置 | 操作 | 备注 |
|---|---|---|---|
| 11 | `app.py:212-216, 245` | toggle 移到结果区上方 | toggle 控制的是"渲染什么",不该在输入区 |
| 12 | `app.py:289-290` | `st.expander(expanded=True)` 默认展开 | "推理过程"是这工具的卖点,默认可见 |
| 13 | `app.py:332-382` | 5 列表格 → 每个 step 一个 `st.expander` | Markdown 自然换行,字段独立可读 |
| 14 | `theme.py:160-166 + app.py:126-141` | 多处 mono section label 重复 3+ 次 | 抽 `mono_section_label(text)` 到 `theme.py`,内部用统一的 class |
| 15 | `app.py:88, 107, 127 + theme.py:127-141 + 162-164` | gold 色用 5+ 处,失去"稀缺强调" | section label 改用 fg-2 + accent 左边框;真正需要 gold:数字 / 链接 / 状态码 |

### 设计语言一致性

| # | 位置 | 问题 | 修复 |
|---|---|---|---|
| 16 | `app.py:130-141` | sidebar 显示 `agent_name` 用英文名(`ip_intelligence`) | 改用 `get_agent_meta()` 的中文 label,符合中文产品界面 |
| 17 | `app.py:138` | `■ ` 前缀 + 中文 label + 英文括号 agent_name | 选定一种:**中文 label + emoji 区分**(`🌶️ IP 情报` 这种),不用 `■` |
| 18 | `theme.py` | 字体加载用了 `@import`(Google Fonts) | 保留,但**加 `display=swap`** 让 fallback 立即生效(目前已有,但要验证) |
| 19 | `theme.py:88-95` | input border 用了 `var(--accent-subtle)` 在 focus 时,但 normal 时用 `var(--border-1)` | 一致,无需改 |

---

## 🏗️ 契约级改动(P2 — 影响生产就绪度)

| # | 文件 | 操作 |
|---|---|---|
| 20 | `src/agents.py` + 新 `src/agents_meta.py` | 抽出三个 Agent 的 metadata(label/color/tools/prompt),由 `agents_meta.py` 单文件管。`build_agents()` 读 metadata 自动构造。这样新加一个 Agent 只改一个文件 |
| 21 | `app.py:_infer_quality_context` → `src/quality_inference.py` | 拆成模块,加 `tests/test_quality_inference.py` 三个用例:高 sources=高分、无 tool calls=低分、有失败=中分 |
| 22 | `orchestrator._synthesize` 失败处理 | 加 `result.final_answer_source = "llm" | "fallback"` 字段,UI 据此显示"LLM 综合失败,基于 Agent 直出结论" 而不是把它**像成功一样**展示 |
| 23 | `app.py:212` | toggle 加 `key="show_reasoning"` 防止 Streamlit 状态错乱 |
| 24 | `agents.py:_AGENT_PROMPTS` dict | 每个 system prompt 单独成 `.txt` 文件,因为会被测、会被多轮迭代,inline 难维护 |

---

## 📋 执行顺序(按 rung 排,每阶段可独立 merge)

### Phase 1(P0) — 硬 bug,半天搞定

1. 修 bug #1 (#305-306)
2. 删 `import json as _json` (#3,#32)
3. 改 `sub = next(...)` → 安全 `dict.get` (#4)
4. 改 `qr:.2f` 容错 (#2)
5. 改 try-except pass (#5)

**验收**:首页 + 提交 query 不报错,显示正常。

### Phase 2(P1 快捷删) — 1h

6. 删"Agent 最终输出 →" 块 (#6)
7. 删"工具调用:" 统计 (#7)
8. 删"综合分析报告" 灰色包裹 + toggle 提前(#8,#11)
9. 删 sidebar 重复 mono label 代码,合并 helper (#14)

**验收**:Streamlit 重启后页面更清爽,信息密度更大。

### Phase 3(P1 结构调整) — 半天

10. toggle 移到结果区,默认 ON (#11,#12)
11. 5 列表格 → expander stack (#13)
12. sidebar agent 中文 label (#16)
13. gold 用法收敛 (#15)

**验收**:暗色深度统一,gold 留给真正重要的事。

### Phase 4(P2 契约级) — 1-2 天

14. 抽 `agents_meta.py`
15. `quality_inference.py` + 单测
16. orchestrator 加 `final_answer_source` 字段
17. system prompt 抽 `.txt`

**验收**:新加一个 Agent 只需 10 行;回归测试覆盖质量打分。

---

## 🚫 暂不做

- 不用真搞 PWA / 一键部署 — 用户没要
- 不写集成测试 — phase 4 单元测试已足够
- 不重写 `src/theme.py` 的设计 token — 它们 working,改动了 UI 色彩一致性会破
- 不更换 OpenDesign portfolio token — 与之对齐本身就是好品味

---

## ⚙️ 配置变更清单

- 无新依赖
- 无 pyproject.toml 改动
- 无 env 变量改动
- 无 git 分支约定

---

## 📊 当前质量评估(对照 OpenDesign 标准)

| 维度 | 当前 | 改造后目标 |
|---|---|---|
| 排版 token | OK(已对齐 portfolio) | 不变 |
| 配色 token | OK | 收敛 gold 用法 |
| 字体层次 | OK(Fraunces 标题/Sora 正文/JetBrains Mono 标签) | 不变 |
| 动效 | OK(hover 微交互) | 不变 |
| 无障碍 | 半 OK(toggle 标签 OK,表格列宽崩) | 修复表格 |
| 暗色对比 | OK ≥ 4.5:1 | 不变 |
| LCP | OK(加噪点 SVG 缓存友好) | 不变 |
| **代码-UI 一致性** | ❌ 弱 | ✅ 强 |
| **可维护性** | ❌ 弱(gold 扩散、helper 缺失) | ✅ 强 |
| **可测试性** | ❌ 弱(无 UI 测试、prompt 无 fixture) | ✅ 强 |

---

## ✅ 验收清单(完成所有阶段后)

- [ ] P0 5 条 bug 修复
- [ ] P1 10 条清理完成,toggle 默认展开,布局无重复
- [ ] P2 契约修改,新加 Agent 只需 10 行
- [ ] pytest 跑过
- [ ] Streamlit 首页 + 提交 query 端到端无报错
- [ ] 浏览器截屏 4 张:首屏/输入/思考展开/最终报告,人眼审过

---

**Why this plan?** 用户说"问题很多,先全局检查"。
本计划先**承认所有问题**而非挑着修,按 rung 排好 ROI,先验证后承诺,避免边改边漏。

**How to apply**:照本计划一路执行 phase 1-4。每阶段结束 verify(后台跑 streamlit + curl 200),然后立即提交。
