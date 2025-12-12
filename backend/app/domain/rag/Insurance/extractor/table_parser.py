from typing import List, Optional


def parse_table_to_markdown(tables: Optional[List[List[List[str]]]]) -> List[str]:
    md_list: List[str] = []
    if not tables:
        return md_list
    for table in tables:
        if not table:
            continue
        table = [[cell if cell is not None else "" for cell in row] for row in table]
        header = table[0]
        body = table[1:] if len(table) > 1 else []
        md = "| " + " | ".join(header) + " |\n"
        md += "| " + " | ".join("---" for _ in header) + " |\n"
        for row in body:
            md += "| " + " | ".join(row) + " |\n"
        md_list.append(md)
    return md_list
