"""Entities: execution plan, steps, and PR plans."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.domain.value_object.step_status import StepStatus


@dataclass
class PlanStep:
    """A single executable step in the plan."""

    id: int
    pr_index: int
    phase: str              # "branch", "checkout", "commit", "push", "pr", "cleanup"
    description: str
    commands: list[str]
    status: str = StepStatus.PENDING
    output: str = ""
    executed_at: str = ""
    error: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "pr_index": self.pr_index,
            "phase": self.phase,
            "description": self.description,
            "commands": self.commands,
            "status": self.status,
            "output": self.output,
            "executed_at": self.executed_at,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, d: dict) -> PlanStep:
        return cls(**d)


@dataclass
class PRPlan:
    """Plan for a single stacked PR."""

    index: int
    title: str
    branch_name: str
    base_branch: str
    files: list[str]
    depends_on: list[int]
    merge_strategy: str
    code_lines: int
    risk_score: float

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "title": self.title,
            "branch_name": self.branch_name,
            "base_branch": self.base_branch,
            "files": self.files,
            "depends_on": self.depends_on,
            "merge_strategy": self.merge_strategy,
            "code_lines": self.code_lines,
            "risk_score": self.risk_score,
        }

    @classmethod
    def from_dict(cls, d: dict) -> PRPlan:
        return cls(**d)


@dataclass
class ExecutionPlan:
    """Complete execution plan for a stacked PR set."""

    version: int = 1
    created_at: str = ""
    source_branch: str = ""
    base_branch: str = ""
    repo_root: str = ""
    total_prs: int = 0
    prs: list[PRPlan] = field(default_factory=list)
    steps: list[PlanStep] = field(default_factory=list)
    mermaid: str = ""

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "created_at": self.created_at,
            "source_branch": self.source_branch,
            "base_branch": self.base_branch,
            "repo_root": self.repo_root,
            "total_prs": self.total_prs,
            "prs": [p.to_dict() for p in self.prs],
            "steps": [s.to_dict() for s in self.steps],
            "mermaid": self.mermaid,
        }

    @classmethod
    def from_dict(cls, d: dict) -> ExecutionPlan:
        return cls(
            version=d.get("version", 1),
            created_at=d.get("created_at", ""),
            source_branch=d.get("source_branch", ""),
            base_branch=d.get("base_branch", ""),
            repo_root=d.get("repo_root", ""),
            total_prs=d.get("total_prs", 0),
            prs=[PRPlan.from_dict(p) for p in d.get("prs", [])],
            steps=[PlanStep.from_dict(s) for s in d.get("steps", [])],
            mermaid=d.get("mermaid", ""),
        )
