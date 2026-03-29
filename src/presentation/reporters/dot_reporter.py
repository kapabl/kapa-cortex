"""Presentation: Graphviz DOT output."""

from __future__ import annotations


def generate_dot(prs):
    colors = {"squash": "#4CAF50", "merge": "#FF9800", "rebase": "#2196F3"}
    lines = ['digraph stacked_prs {', '  rankdir=BT;', '  node [shape=box, style=rounded];']

    for pr in prs:
        color = colors.get(pr.merge_strategy, "#999")
        file_list = "\\n".join(file.path for file in pr.files[:5])
        if len(pr.files) > 5:
            file_list += f"\\n... +{len(pr.files) - 5} more"
        label = f"{pr.title}\\n{file_list}\\n[{pr.merge_strategy}] risk={pr.risk_score}"
        lines.append(
            f'  pr{pr.index} [label="{label}", fillcolor="{color}", '
            f'style="rounded,filled", fontcolor="white"];'
        )

    for pr in prs:
        for dep in pr.depends_on:
            lines.append(f"  pr{pr.index} -> pr{dep};")

    lines.append("}")
    return "\n".join(lines)
