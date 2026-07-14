---
date: 2026-07-10
type: log
tags:
  - log
  - vault-maintenance
  - ai-first
ai-first: true
updated: 2026-07-11
---

## For future Claude

This file is a chronological activity log for the `泡泡玛特重构` vault. Every init, ingest, save, health check, or structural change gets a timestamped entry. Read the most recent entries to understand what has changed in prior entries.

---

# Vault Activity Log

Format: `## [YYYY-MM-DD] action | Description`

---

## [2026-07-11] ux-security + neat-freak | 体感/安全 P0–P2 落地并文档对齐

- Demo 行为：失败分析不写缓存、不假绿成功；好缓存才展示成功报告；pickle→json 仅迁移成功预设。
- 认证：`STREAMLIT_PASSWORD` 强制登录 + session 级 lockout/cooldown + 退出登录；有密码时不允许 `ALLOW_LOCAL_DEV` 绕过。
- UI：推理折叠默认收起；历史可恢复；用户文本/markdown spoof 中和。
- 文档：`README.md` / `index.md` / `_CLAUDE.md` 缓存路径改为 `.demo_cache.json`；新增 `docs/ux-security-2026-07-11.md`。
- 清理：删除 `scripts/_patch_*`、`_accept_*` 等一次性验收脚本与临时 readout/pytest 目录；保留 `demo-screenshots/accept-*.png`、`p2-*.png` 与正式单测。
- 回归：`tests/test_security.py` + `tests/test_cache_store.py`（验收时 20 passed）。

## [2026-07-10] init | Vault initialized with _CLAUDE.md, index.md, log.md via /obsidian-init
