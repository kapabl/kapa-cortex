"""Repository: execution plan persistence interface."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.entity.execution_plan import ExecutionPlan


class PlanRepository(ABC):
    """Interface for persisting execution plans."""

    @abstractmethod
    def save(self, plan: ExecutionPlan) -> None: ...

    @abstractmethod
    def load(self) -> ExecutionPlan: ...
