"""Port: plan save/load."""

from __future__ import annotations

from abc import ABC, abstractmethod

from src.domain.execution_plan import ExecutionPlan


class PlanPersistence(ABC):
    """Contract for persisting execution plans. Implemented by infrastructure."""

    @abstractmethod
    def save(self, plan: ExecutionPlan) -> None: ...

    @abstractmethod
    def load(self) -> ExecutionPlan: ...
