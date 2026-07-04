"""Wiki RAG: Wikipedia API 检索外部通用知识."""
import os
import yaml
import wikipedia
from retrieval.base import BaseRetriever

with open("config/settings.yaml", "r", encoding="utf-8") as f:
    SETTINGS = yaml.safe_load(f)

CFG = SETTINGS["wiki_rag"]

# 默认中文
wikipedia.set_lang("zh")


class WikiRAGRetriever(BaseRetriever):
    path_name = "wiki_rag"

    def __init__(self):
        self.max_results = CFG["max_results"]
        self.summary_chars = CFG["summary_chars"]
        lang = "zh"
        # 从 data_sources 配置读
        try:
            with open("config/data_sources.yaml", "r", encoding="utf-8") as f:
                for src in yaml.safe_load(f)["sources"]:
                    if src["type"] == "wiki":
                        lang = src["config"].get("language", "zh")
                        break
        except Exception:
            pass
        wikipedia.set_lang(lang)

    def retrieve(self, query: str, user: dict = None) -> dict:
        # 1. 搜索相关条目
        try:
            titles = wikipedia.search(query, results=self.max_results)
        except Exception as e:
            return {"context": f"(Wiki 搜索失败: {e})", "raw": None, "meta": {"path": self.path_name}}

        if not titles:
            return {"context": "(Wiki 无相关条目)", "raw": None, "meta": {"path": self.path_name}}

        # 2. 取摘要
        passages = []
        used_titles = []
        for title in titles:
            try:
                summary = wikipedia.summary(title, sentences=5)
                if len(summary) > self.summary_chars:
                    summary = summary[:self.summary_chars] + "..."
                passages.append(f"【{title}】{summary}")
                used_titles.append(title)
            except wikipedia.exceptions.DisambiguationError as e:
                # 歧义, 取第一个选项
                if e.options:
                    try:
                        summary = wikipedia.summary(e.options[0], sentences=5)
                        passages.append(f"【{e.options[0]}】{summary[:self.summary_chars]}")
                        used_titles.append(e.options[0])
                    except Exception:
                        continue
            except Exception:
                continue
            if len(passages) >= self.max_results:
                break

        if not passages:
            return {"context": "(Wiki 条目无法获取摘要)", "raw": None, "meta": {"path": self.path_name}}

        context = "\n---\n".join(passages)
        return {
            "context": context,
            "raw": {"titles": used_titles, "passages": passages},
            "meta": {"path": self.path_name, "title_count": len(used_titles)},
        }
