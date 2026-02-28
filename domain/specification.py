from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar("T")


class Specification(ABC, Generic[T]):

    @abstractmethod
    def is_satisfied_by(self, candidate: T) -> bool:
        pass

    def __and__(self, other: "Specification[T]") -> "AndSpecification[T]":
        return AndSpecification(self, other)


class AndSpecification(Specification[T]):

    def __init__(self, left: Specification[T], right: Specification[T]) -> None:
        self.left = left
        self.right = right

    def is_satisfied_by(self, candidate: T) -> bool:
        return (
            self.left.is_satisfied_by(candidate) and
            self.right.is_satisfied_by(candidate)
        )
