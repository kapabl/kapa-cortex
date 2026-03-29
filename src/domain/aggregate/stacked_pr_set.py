"""Aggregate root: a set of proposed stacked PRs."""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx

from src.domain.entity.proposed_pr import ProposedPR
from src.domain.entity.changed_file import ChangedFile
from src.domain.event import DependencyCycleDetected


@dataclass
class StackedPRSet:
    """
    Aggregate root — owns the full set of proposed PRs,
    their dependency graph, and the domain events produced
    during analysis.
    """

    prs: list[ProposedPR] = field(default_factory=list)
    graph: nx.DiGraph = field(default_factory=nx.DiGraph)
    files: list[ChangedFile] = field(default_factory=list)
    branch: str = ""
    base: str = ""
    events: list = field(default_factory=list)

    @property
    def file_count(self) -> int:
        return len(self.files)

    @property
    def pr_count(self) -> int:
        return len(self.prs)

    @property
    def edge_count(self) -> int:
        return self.graph.number_of_edges()

    def record_cycle(self, files_in_cycle: list[str]) -> None:
        """Record that a dependency cycle was detected and broken."""
        self.events.append(DependencyCycleDetected(files_in_cycle))

    def get_pr(self, index: int) -> ProposedPR | None:
        return next((p for p in self.prs if p.index == index), None)
