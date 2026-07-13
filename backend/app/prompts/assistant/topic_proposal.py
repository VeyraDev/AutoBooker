"""Topic proposal prompts for external search results."""

from __future__ import annotations

import json
from typing import Any


def build_topic_proposal_user_prompt(search_result: dict[str, Any]) -> str:
    works = search_result.get("works") or []
    work_lines = []
    for w in works[:12]:
        if not isinstance(w, dict):
            continue
        title = w.get("title") or ""
        year = w.get("year") or ""
        source = w.get("source") or ""
        work_lines.append(f"- {title} ({year}) [{source}]")
    directions = search_result.get("research_directions") or []
    return f"""研究者：{search_result.get("person")}
检索词：{search_result.get("query")}
来源说明：{search_result.get("source_scope")}
研究方向线索：
{chr(10).join(f"- {d}" for d in directions) if directions else "（无）"}

代表性作品：
{chr(10).join(work_lines) if work_lines else "（无）"}

请基于以上公开检索结果，提出 2-4 个可写成专业书稿的主题。"""


TOPIC_PROPOSAL_SYSTEM = """你是学术出版选题顾问。根据公开检索到的研究者作品与方向，提出可成书主题。

只输出 JSON：
{
  "topics": [
    {
      "title": "书稿主题标题",
      "rationale": "为什么适合写成书",
      "audience": "目标读者",
      "feasibility": "high|medium|low",
      "risks": ["风险1"]
    }
  ],
  "recommended_index": 0,
  "source_disclaimer": "判断基于哪些公开来源，以及局限性"
}

规则：
- 主题必须能从检索结果中找到依据，不要编造未出现的研究方向。
- 至少 2 个、最多 4 个主题。
- feasibility 要诚实：资料不足时标 low 并说明。
- source_disclaimer 必须提醒用户公开摘要的局限性。"""


def parse_topic_proposal(raw: str) -> dict[str, Any]:
    from app.utils.json_llm import parse_llm_json

    data = parse_llm_json(raw)
    topics = data.get("topics") if isinstance(data.get("topics"), list) else []
    clean_topics = []
    for item in topics:
        if not isinstance(item, dict):
            continue
        title = str(item.get("title") or "").strip()
        if not title:
            continue
        clean_topics.append(
            {
                "title": title,
                "rationale": str(item.get("rationale") or "").strip(),
                "audience": str(item.get("audience") or "").strip(),
                "feasibility": str(item.get("feasibility") or "medium").strip(),
                "risks": [str(x) for x in (item.get("risks") or []) if str(x).strip()],
            }
        )
    rec = data.get("recommended_index")
    try:
        recommended_index = int(rec) if rec is not None else 0
    except (TypeError, ValueError):
        recommended_index = 0
    if clean_topics and recommended_index >= len(clean_topics):
        recommended_index = 0
    return {
        "topics": clean_topics,
        "recommended_index": recommended_index,
        "source_disclaimer": str(data.get("source_disclaimer") or "").strip(),
    }


def format_topics_preview(proposal: dict[str, Any]) -> str:
    lines = []
    for i, t in enumerate(proposal.get("topics") or []):
        mark = "（推荐）" if i == proposal.get("recommended_index") else ""
        lines.append(f"{i + 1}. {t.get('title')}{mark}")
        if t.get("rationale"):
            lines.append(f"   理由：{t['rationale']}")
        if t.get("audience"):
            lines.append(f"   读者：{t['audience']}")
        if t.get("feasibility"):
            lines.append(f"   可写性：{t['feasibility']}")
    disclaimer = proposal.get("source_disclaimer")
    if disclaimer:
        lines.append("")
        lines.append(f"来源说明：{disclaimer}")
    return "\n".join(lines)
