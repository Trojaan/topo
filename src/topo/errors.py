from __future__ import annotations


class ContextAlreadyExistsError(Exception):
    pass


class PackageIntegrityError(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


class ProposalDecisionError(Exception):
    def __init__(self, code: str, path: str, reason: str) -> None:
        self.code = code
        self.path = path
        self.reason = reason
        super().__init__(reason)


class StaleGenerationError(Exception):
    def __init__(self, actual_generation: str) -> None:
        self.actual_generation = actual_generation
        super().__init__(actual_generation)
