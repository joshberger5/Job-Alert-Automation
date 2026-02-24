from abc import ABC, abstractmethod
from typing import Iterable
from domain.events import DomainEvent


class EventPublisher(ABC):

    @abstractmethod
    def publish(self, events: Iterable[DomainEvent]) -> None:
        pass