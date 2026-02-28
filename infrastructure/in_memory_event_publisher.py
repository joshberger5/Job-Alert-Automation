from typing import Iterable

from application.event_publisher import EventPublisher
from application.simple_event_dispatcher import SimpleEventDispatcher
from domain.events import DomainEvent


class InMemoryEventPublisher(EventPublisher):

    def __init__(self, dispatcher: SimpleEventDispatcher) -> None:
        self.dispatcher = dispatcher

    def publish(self, events: Iterable[DomainEvent]) -> None:
        self.dispatcher.dispatch(events)
