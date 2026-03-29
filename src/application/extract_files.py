"""Use case: extract a subset of files into a new PR branch."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import networkx as nx

from src.domain.entity.changed_file import ChangedFile
from src.domain.value_object.extraction_rule import ExtractionRule
from src.domain.service.file_matcher import match_files
from src.domain.service.prompt_parser import parse_prompt
from src.domain.port.llm_service import LLMService


@dataclass
class ExtractionResult:
    prompt: str
    rules: list[ExtractionRule]
    matched_files: list[ChangedFile]
    dep_files: list[ChangedFile]
    all_files: list[ChangedFile]
    branch_name: str
    base_branch: str
    source_branch: str
    commands: list[str] = field(default_factory=list)


class ExtractFilesUseCase:
    """Orchestrates prompt-driven file extraction."""

    def __init__(self, llm: LLMService):
        self._llm = llm

    def execute(
        self,
        prompt: str,
        all_files: list[ChangedFile],
        graph: nx.DiGraph,
        source_branch: str,
        base_branch: str,
        branch_name: str | None = None,
        include_deps: bool = True,
    ) -> ExtractionResult:
        rules = parse_prompt(prompt)
        matched = match_files(all_files, rules)

        if not matched and self._llm.available:
            matched = self._llm_match(prompt, all_files)

        resolved = self._resolve_deps(matched, all_files, graph, include_deps)
        matched_paths = {file.path for file in matched}
        dep_files = [file for file in resolved if file.path not in matched_paths]

        if not branch_name:
            slug = re.sub(r"[^a-z0-9]+", "-", prompt.lower())[:40].strip("-")
            branch_name = f"extract/{slug}"

        commands = _build_commands(resolved, source_branch, base_branch, branch_name, prompt)

        return ExtractionResult(
            prompt=prompt, rules=rules,
            matched_files=matched, dep_files=dep_files,
            all_files=resolved, branch_name=branch_name,
            base_branch=base_branch, source_branch=source_branch,
            commands=commands,
        )

    def _llm_match(self, prompt, files):
        from src.infrastructure.llm.ollama_backend import build_extraction_prompt, parse_llm_json
        summaries = [
            {"path": file.path, "status": file.status, "added": file.added, "removed": file.removed}
            for file in files
        ]
        resp = self._llm.query(build_extraction_prompt(prompt, summaries), json_mode=True)
        data = parse_llm_json(resp)
        if data and isinstance(data, dict):
            paths = set(data.get("matched", []))
            return [file for file in files if file.path in paths]
        return []

    def _resolve_deps(self, matched, all_files, graph, include_deps):
        if not include_deps:
            return matched
        matched_paths = {file.path for file in matched}
        all_map = {file.path: file for file in all_files}
        deps: set[str] = set()
        for file in matched:
            if file.path in graph:
                for _, dep in nx.dfs_edges(graph, file.path):
                    if dep not in matched_paths and dep in all_map:
                        deps.add(dep)
        result_paths = matched_paths | deps
        return [file for file in all_files if file.path in result_paths]


def _build_commands(files, source, base, branch, prompt):
    cmds = [f"git checkout -b {branch} {base}"]
    checkout = [file.path for file in files if file.status != "D"]
    deleted = [file.path for file in files if file.status == "D"]
    for i in range(0, len(checkout), 20):
        batch = checkout[i:i+20]
        args = " ".join(f'"{path}"' for path in batch)
        cmds.append(f"git checkout {source} -- {args}")
    if deleted:
        args = " ".join(f'"{path}"' for path in deleted)
        cmds.append(f"git rm {args}")
    cmds.append("git add -A")
    msg = f"Extract: {prompt}"
    cmds.append(f"git commit -m '{msg}'")
    cmds.append(f"git push -u origin {branch}")
    cmds.append(f"git checkout {source}")
    return cmds
