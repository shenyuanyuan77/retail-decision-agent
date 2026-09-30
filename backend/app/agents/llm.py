# -*- coding: utf-8 -*-
"""LLM 叙述层（OpenAI 兼容，可选）。

原则：大模型只做"解释与叙述"，不做数值计算；
     所有数字必须来自事实表（工具返回）；
     若叙述中出现事实表之外的数字 → 判定为编造，回退模板叙述（治理保障）。
未配置 LLM_BASE_URL/LLM_API_KEY 时自动使用模板叙述器，系统全功能可用。
"""
import json
import re

from ..core import config


def _facts_numbers(facts: dict) -> set[str]:
    """提取事实表中所有数值的字符串表示（用于防编造校验）。"""
    nums: set[str] = set()

    def walk(v):
        if isinstance(v, bool):
            return
        if isinstance(v, (int, float)):
            s = f"{v:g}"
            nums.add(s)
            nums.add(f"{v:.1f}")
            nums.add(f"{v:.2f}")
            # 绝对值形态：叙述中"下降95%"对应事实 -95.0 不算编造
            nums.add(f"{abs(v):g}")
            if isinstance(v, float) and v == int(v):
                nums.add(str(int(v)))
        elif isinstance(v, str):
            if re.fullmatch(r"-?\d+(\.\d+)?", v):
                nums.add(v.rstrip("0").rstrip(".") if "." in v else v)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                walk(x)

    walk(facts)
    return nums


def _narrative_numbers_ok(text: str, facts: dict) -> bool:
    allowed = _facts_numbers(facts)
    for m in re.findall(r"\d+(?:\.\d+)?", text):
        if m in allowed or m.rstrip("0").rstrip(".") in allowed or m.lstrip("0") in allowed:
            continue
        # 日期/编号类（含 - 或长度>4 的连续数字串）跳过
        return False
    return True


class TemplateNarrator:
    """离线模板叙述器：直接引用事实，天然不编造。"""

    def generate(self, prompt: str, facts: dict, template: str = "") -> str:
        if template:
            return template
        return json.dumps(facts, ensure_ascii=False, indent=2)


class OpenAICompatNarrator:
    """OpenAI 兼容接口叙述器（可选启用）。"""

    def __init__(self):
        import httpx
        self._httpx = httpx
        self.base_url = config.LLM_BASE_URL.rstrip("/")
        self.api_key = config.LLM_API_KEY
        self.model = config.LLM_MODEL

    def generate(self, prompt: str, facts: dict, template: str = "") -> str:
        try:
            r = self._httpx.post(
                f"{self.base_url}/chat/completions",
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": (
                            "你是零售经营分析助手。只做解释与叙述，禁止计算。"
                            "只能引用给定事实 JSON 中的数字，不得出现任何事实之外的数字。"
                            "输出 80 字以内的中文结论。")},
                        {"role": "user", "content": f"{prompt}\n事实：{json.dumps(facts, ensure_ascii=False)}"},
                    ],
                    "temperature": 0.2,
                },
                timeout=20,
            )
            r.raise_for_status()
            text = r.json()["choices"][0]["message"]["content"].strip()
            if _narrative_numbers_ok(text, facts):
                return text
            return template or json.dumps(facts, ensure_ascii=False, indent=2)
        except Exception:
            return template or json.dumps(facts, ensure_ascii=False, indent=2)


_narrator: TemplateNarrator | OpenAICompatNarrator | None = None


def get_narrator():
    global _narrator
    if _narrator is None:
        if config.LLM_BASE_URL and config.LLM_API_KEY:
            _narrator = OpenAICompatNarrator()
        else:
            _narrator = TemplateNarrator()
    return _narrator


def narrate(prompt: str, facts: dict, template: str = "") -> str:
    return get_narrator().generate(prompt, facts, template)
