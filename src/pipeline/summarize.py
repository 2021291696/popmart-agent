"""整理（智能化）阶段 —— 对每个抓取源用 LLM 做结构化摘要。

流水线位置:chunk (机械分块) -> summarize (LLM 整理) -> embed -> store

输入:scraped/*.json 的全文文本
输出:data/summarized/<key>.json,字段:
  - key, label, url, kind, fetched_at
  - summary: LLM 生成的结构化摘要(纯文本,保留段落)
  - key_facts: LLM 抽取的关键事实列表[str]
  - llm_model: 使用的模型名

错误策略:不做降级,任一源失败即整次刷新报错抛出。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from ..llm_client import LLMClient
from ..config import Settings, load_settings


SCRAPED_DIR = Path(__file__).parent.parent / "rag" / "data" / "scraped"
SUMMARIZED_DIR = Path(__file__).parent.parent / "rag" / "data" / "summarized"


SYSTEM_PROMPT = """你是潮玩行业资深分析师,负责把抓取的原始网页文本整理成结构化摘要,供后续 RAG 检索使用。

要求:
1. 提取核心事实:数字、日期、IP 名、人物、机构、关键事件(每个事实一句完整陈述,带数值)
2. 保留原文重要表述:对潮玩行业分析有价值的判断、趋势、对比直接保留原文措辞
3. 整理段落结构:用清晰小标题分段(如"## 财务数据"、"## IP 矩阵"、"## 市场表现")
4. 严格基于原文:不要编造原文没有的数据,不确定的内容写"原文未提及"
5. 输出一段连贯摘要(summary),长度约原文的 20%-40%
6. 末尾列出 5-10 条 key_facts(每条一行,以"- "开头,必须是 summary 中已出现的具体事实)

严格 JSON 输出,不要 markdown 代码块,不要解释:
{"summary": "...", "key_facts": ["...", "..."]}
"""


def _build_user_prompt(label: str, text: str) -> str:
    # 超长文本截断:超过 12000 字符按段落截取前段(后续可扩展为分段摘要)
    if len(text) > 12000:
        text = text[:12000] + "\n\n...(后续内容已截断,基于以上整理)"
    return f"源: {label}\n\n原文:\n{text}"


def _parse_llm_json(raw: str) -> dict:
    """容错解析 LLM 返回的 JSON。

    策略（按顺序尝试, 全部失败才抛错, 不降级, 让上层重试或报错）:
      1. 直接 json.loads
      2. 去 markdown 代码块包裹再尝试
      3. 取首尾大括号 (首 { 到末 })
      4. 平衡大括号扫描: 找到第一个完整 JSON 对象 (容错 LLM 把 JSON 重复输出多遍)
      5. 全部失败, 抛出错误
    """
    if not raw or not raw.strip():
        raise ValueError("LLM 返回为空")
    raw = raw.strip()

    def _is_valid(d):
        return isinstance(d, dict) and isinstance(d.get("summary"), str) and isinstance(d.get("key_facts"), list)

    # 策略1: 直接解析
    try:
        data = json.loads(raw)
        if _is_valid(data):
            return data
    except Exception:
        pass

    # 策略2: 去掉 markdown 代码块
    cleaned = raw
    if cleaned.startswith("```"):
        lines = [ln for ln in cleaned.split("\n") if not ln.strip().startswith("```")]
        cleaned = "\n".join(lines).strip()
    try:
        data = json.loads(cleaned)
        if _is_valid(data):
            return data
    except Exception:
        pass

    # 策略3: 取首尾大括号
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            data = json.loads(cleaned[start:end + 1])
            if _is_valid(data):
                return data
        except Exception:
            pass

    # 策略4: 平衡大括号扫描 (LLM 把同一 JSON 重复输出 2-N 次时取第一个完整对象)
    # 从第一个 { 开始, 跟踪 string 状态 (跳过转义引号和内部引号), 找到匹配的 }
    first = cleaned.find("{")
    if first != -1:
        depth = 0
        in_str = False
        esc = False
        for i in range(first, len(cleaned)):
            ch = cleaned[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        try:
                            data = json.loads(cleaned[first:i + 1])
                            if _is_valid(data):
                                return data
                        except Exception:
                            pass
                        break

    # 策略5: 全部失败, 抛出包含原始文本的错误(便于排查)
    raise ValueError(f"无法解析 LLM 返回为 JSON, 原始前 500 字符: {raw[:500]}")


def summarize_one(client: LLMClient, label: str, text: str, model: str) -> dict:
    """对单条源做结构化摘要。失败抛出不降级。"""
    if not text or not text.strip():
        raise ValueError(f"源 {label} 文本为空,无法整理")
    user_prompt = _build_user_prompt(label, text)

    # 重试 2 次: 第一次失败时提示 LLM "严格返回 JSON"
    last_err: Exception | None = None
    for attempt in range(2):
        if attempt == 0:
            messages = [{"role": "user", "content": user_prompt}]
        else:
            messages = [
                {"role": "user", "content": user_prompt},
                {"role": "assistant", "content": raw or ""},
                {"role": "user", "content": "你的上一次回复不是合法 JSON。请**只**返回严格的 JSON 对象(不要 markdown 代码块,不要解释文字), 形如 {\"summary\": \"...\", \"key_facts\": [\"...\", ...]}"},
            ]
        try:
            raw = client.chat(
                system=SYSTEM_PROMPT,
                messages=messages,
                temperature=0.2,
                max_tokens=3000,
            )
            parsed = _parse_llm_json(raw)
            summary = parsed.get("summary", "").strip()
            key_facts = parsed.get("key_facts", [])
            if not summary:
                raise ValueError(f"源 {label} 整理结果 summary 为空")
            if not isinstance(key_facts, list):
                key_facts = []
            return {
                "summary": summary,
                "key_facts": [str(f).strip() for f in key_facts if str(f).strip()],
                "llm_model": model,
            }
        except Exception as e:
            last_err = e
            raw = ""  # 用于重试 messages
            continue
    # 两次都失败, 抛出最后一次错误(不降级)
    raise RuntimeError(f"源 {label} 整理失败(2 次重试均失败): {last_err}") from last_err


def summarize_scraped(
    client: LLMClient | None = None,
    settings: Settings | None = None,
    on_progress: Callable[[str], None] | None = None,
    output_dir: Path | None = None,
) -> list[dict]:
    """遍历 scraped/*.json,对每个源做整理,写入 data/summarized/*.json。

    返回 list[dict],每个 dict:
      - key, label, url, kind, fetched_at, text(原始正文,给后续 chunk 做原材料),
        summary, key_facts, llm_model
    """
    if on_progress is None:
        on_progress = lambda msg: None  # noqa: E731

    if settings is None:
        settings = load_settings()
    if client is None:
        client = LLMClient(settings)

    destination = output_dir or SUMMARIZED_DIR
    destination.mkdir(parents=True, exist_ok=True)

    if not SCRAPED_DIR.exists():
        return []

    results: list[dict] = []
    index_path = SCRAPED_DIR / "_index.json"
    if not index_path.exists():
        raise FileNotFoundError(f"未找到 {index_path},请先点 [刷新数据] 抓取")

    index = json.loads(index_path.read_text(encoding="utf-8"))
    ok_entries = [e for e in index.get("ok", []) if e.get("key")]
    if not ok_entries:
        raise RuntimeError("没有成功抓取的源可供整理")

    for i, entry in enumerate(ok_entries, 1):
        key = entry["key"]
        full_path = SCRAPED_DIR / f"{key}.json"
        if not full_path.exists():
            raise FileNotFoundError(f"抓取文件缺失: {full_path}")
        data = json.loads(full_path.read_text(encoding="utf-8"))
        label = data.get("label", key)
        text = data.get("text", "")
        url = data.get("url", "")
        kind = data.get("kind", "")
        fetched_at = data.get("fetched_at", "")

        on_progress(f"[{i}/{len(ok_entries)}] 整理 {label} ...")
        summarized = summarize_one(client, label, text, settings.llm_model)

        record = {
            "key": key,
            "label": label,
            "url": url,
            "kind": kind,
            "fetched_at": fetched_at,
            "summary": summarized["summary"],
            "key_facts": summarized["key_facts"],
            "llm_model": summarized["llm_model"],
        }
        # 原子写:先写 .tmp 再 rename,避免并发读到半写
        out_path = destination / f"{key}.json"
        tmp_path = destination / f"{key}.json.tmp"
        tmp_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        tmp_path.replace(out_path)
        on_progress(f"[{i}/{len(ok_entries)}] 整理完成: {label} ({len(summarized['key_facts'])} facts)")
        results.append(record)

    # 索引文件,记录本次整理结果
    summary_index = {
        "summarized_at": index.get("fetched_at", ""),
        "llm_model": settings.llm_model,
        "count": len(results),
        "keys": [r["key"] for r in results],
    }
    (destination / "_index.json").write_text(
        json.dumps(summary_index, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    on_progress(f"整理阶段完成: {len(results)} 条源")
    return results


def summarized_to_chunks(summarized: list[dict]) -> list[dict]:
    """把 summarized 记录转成可 embed 的 chunks。

    每条源产出 2 类 chunk:
    - summary chunk:整段 summary 作为一条 chunk
    - key_facts chunk:每个事实独立一条 chunk
    这样检索可按"摘要相关性"和"具体事实命中"双粒度召回。
    """
    chunks: list[dict] = []
    for r in summarized:
        base_meta = {
            "source": "summarized",
            "section": r["key"],
            "url": r["url"],
            "kind": r["kind"],
            "fetched_at": r["fetched_at"],
        }
        chunks.append({
            **base_meta,
            "global_id": f"summarized_{r['key']}_summary",
            "text": r["summary"],
            "chunk_type": "summary",
        })
        for i, fact in enumerate(r["key_facts"]):
            chunks.append({
                **base_meta,
                "global_id": f"summarized_{r['key']}_fact_{i}",
                "text": fact,
                "chunk_type": "fact",
            })
    return chunks


if __name__ == "__main__":
    from ..config import load_settings as _load
    settings = _load()
    client = LLMClient(settings)
    out = summarize_scraped(client, settings, on_progress=print)
    print(f"\n整理完成: {len(out)} 条源")
    for r in out:
        print(f"- {r['label']}: {len(r['summary'])} 字摘要, {len(r['key_facts'])} facts")
