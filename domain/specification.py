from abc import ABC, abstractmethod


class Specification(ABC):

    @abstractmethod
    def is_satisfied_by(self, candidate) -> bool:
        pass

    def __and__(self, other):
        return AndSpecification(self, other)


class AndSpecification(Specification):

    def __init__(self, left, right):
        self.left = left
        self.right = right

    def is_satisfied_by(self, candidate) -> bool:
        return (
            self.left.is_satisfied_by(candidate) and
            self.right.is_satisfied_by(candidate)
        )