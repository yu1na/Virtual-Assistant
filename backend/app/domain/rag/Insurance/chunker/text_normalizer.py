import re
from typing import Dict, Any, List


def normalize(text: str, mode: str = "default") -> str:
    # preserve tables: lines containing '|' or starting with '*'
    lines = text.splitlines()
    out_lines: List[str] = []
    for ln in lines:
        if "|" in ln or ln.strip().startswith("*"):
            out_lines.append(ln)
        else:
            s = ln.replace("\t", " ")
            s = re.sub(r"\s+", " ", s)
            out_lines.append(s.strip())
    # prevent collapsing blank lines completely
    normalized = "\n".join(out_lines)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized


def normalize_pages(pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = []
    for p in pages:
        content = p.get("content", "")
        mode = p.get("mode", "text")
        normalized.append({
            "page": p.get("page"),
            "content": normalize(content, mode),
            "tables_markdown": p.get("tables_markdown", []),
        })
    return normalized