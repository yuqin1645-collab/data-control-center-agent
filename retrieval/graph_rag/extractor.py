"""实体/关系抽取: 从文本抽取 (实体, 关系, 实体) 三元组."""
import json
from typing import List, Tuple
from core.llm import LLMClient


EXTRACT_PROMPT = """你是信息抽取专家. 从下面文本中抽取实体和关系, 输出 JSON.

文本:
{text}

要求:
1. 抽取实体 (人、公司、产品、地点、概念等) 和它们之间的关系
2. 关系要具体 (如: 供货、投资、隶属、合作、生产), 不要用 "相关" 这种泛词
3. 输出格式:
{{
  "entities": ["实体1", "实体2", ...],
  "triples": [["实体1", "关系", "实体2"], ...]
}}
4. 没有明确关系就输出空数组, 不要编造"""


def extract_triples(text: str, llm: LLMClient = None) -> Tuple[List[str], List[Tuple[str, str, str]]]:
    """从一段文本抽取实体和三元组."""
    llm = llm or LLMClient.get()
    # 长文本截断
    if len(text) > 2000:
        text = text[:2000]
    prompt = EXTRACT_PROMPT.format(text=text)
    result = llm.chat_json([{"role": "user", "content": prompt}], temperature=0.0, max_tokens=1024)
    entities = result.get("entities", [])
    triples = [tuple(t) for t in result.get("triples", []) if len(t) == 3]
    return entities, triples


def extract_entities_from_query(query: str, llm: LLMClient = None) -> List[str]:
    """从用户问题中抽取查询实体 (作为图检索的种子)."""
    llm = llm or LLMClient.get()
    prompt = f"""从下面问题中抽取要查询的实体 (人名、公司名、产品名、地点等), 输出 JSON 数组.

问题: {query}

输出格式: {{"entities": ["实体1", "实体2"]}}
没有明确实体就输出空数组."""
    result = llm.chat_json([{"role": "user", "content": prompt}], temperature=0.0, max_tokens=256)
    return result.get("entities", [])
