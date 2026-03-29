"""Use case: analyze a branch and propose stacked PRs."""

from __future__ import annotations

import os

import networkx as nx

from src.domain.changed_file import ChangedFile
from src.domain.proposed_pr import ProposedPR
from src.domain.dependency_resolver import build_dependency_edges
from src.domain.file_grouper import partition
from src.domain.merge_order_resolver import compute_pr_dependencies
from src.domain.risk_scorer import compute_risk
from src.domain.merge_strategy_assigner import assign_strategies
from src.domain.test_pair_finder import find_test_pairs
from src.domain.pr_namer import generate_title
from src.domain.ports.git_reader import GitReader
from src.domain.ports.import_parser import ImportParser
from src.domain.ports.symbol_extractor import SymbolExtractor
from src.domain.ports.complexity_analyzer import ComplexityAnalyzer
from src.domain.ports.llm_service import LLMService


class AnalyzeBranchUseCase:
    """Orchestrates the full analysis pipeline."""

    def __init__(
        self,
        git: GitReader,
        parser: ImportParser,
        symbols: SymbolExtractor,
        complexity: ComplexityAnalyzer,
        llm: LLMService,
    ):
        self._git = git
        self._parser = parser
        self._symbols = symbols
        self._complexity = complexity
        self._llm = llm

    def execute(
        self,
        base: str,
        max_files: int = 3,
        max_code_lines: int = 200,
    ) -> AnalysisResult:
        branch = self._git.current_branch()
        base_ref = self._git.resolve_base(base)
        files = self._git.diff_stat(base_ref)

        if not files:
            return AnalysisResult(branch=branch, base=base, files=[], prs=[], graph=nx.DiGraph())

        self._enrich(files)
        imports_by_file = self._parse_imports(files)
        edges = build_dependency_edges(files, imports_by_file)

        G = self._build_graph(files, edges)
        topo = self._topo_sort(G)
        affinity = self._cochange_affinity(files)
        test_pairs = find_test_pairs(files)

        prs = partition(files, topo, test_pairs, affinity, max_files, max_code_lines)

        file_edges = [(s, t) for s, t, _, _ in edges]
        compute_pr_dependencies(prs, file_edges)

        for pr in prs:
            pr.risk_score = compute_risk(pr)
            pr.title = f"PR #{pr.index}: {generate_title(pr.files)}"

        assign_strategies(prs)

        return AnalysisResult(branch=branch, base=base, files=files, prs=prs, graph=G)

    def _enrich(self, files: list[ChangedFile]) -> None:
        paths = [f.path for f in files if not f.is_text_or_docs]
        existing = [p for p in paths if os.path.exists(p)]
        if existing:
            metrics = self._complexity.analyze(existing)
            for f in files:
                if f.path in metrics:
                    f.complexity = metrics[f.path]

        for f in files:
            if f.is_text_or_docs:
                continue
            source = self._git.file_source(f.path)
            if source:
                f.symbols_defined = self._symbols.extract(f.path, source)
                added = "\n".join(
                    line[1:] for line in f.diff_text.splitlines()
                    if line.startswith("+") and not line.startswith("+++")
                )
                f.symbols_used = {s.name for s in self._symbols.extract(f.path, added)}

    def _parse_imports(self, files: list[ChangedFile]) -> dict[str, list]:
        result = {}
        for f in files:
            added_lines = {
                line[1:].strip()
                for line in f.diff_text.splitlines()
                if line.startswith("+") and not line.startswith("+++")
            }
            source = self._git.file_source(f.path)
            if not source:
                source = "\n".join(added_lines)
            all_imports = self._parser.parse(f.path, source)
            result[f.path] = [
                imp for imp in all_imports
                if any(imp.raw in al for al in added_lines) or not added_lines
            ]
        return result

    def _build_graph(self, files, edges):
        G = nx.DiGraph()
        for f in files:
            G.add_node(f.path, file=f)
        for src, tgt, kind, weight in edges:
            G.add_edge(src, tgt, kind=kind, weight=weight)
        while not nx.is_directed_acyclic_graph(G):
            try:
                cycle = nx.find_cycle(G)
                weakest = min(cycle, key=lambda e: G.edges[e[0], e[1]].get("weight", 1.0))
                G.remove_edge(weakest[0], weakest[1])
            except nx.NetworkXNoCycle:
                break
        return G

    def _topo_sort(self, G):
        try:
            return list(nx.topological_sort(G))
        except nx.NetworkXUnfeasible:
            return sorted(G.nodes(), key=lambda n: -G.in_degree(n))

    def _cochange_affinity(self, files):
        paths = [f.path for f in files]
        cochange = self._git.cochange_history(paths)
        if not cochange:
            return {}
        max_count = max(cochange.values()) or 1
        return {pair: count / max_count for pair, count in cochange.items()}


class AnalysisResult:
    """Result of the analyze branch use case."""

    def __init__(self, branch, base, files, prs, graph):
        self.branch = branch
        self.base = base
        self.files = files
        self.prs = prs
        self.graph = graph
