from typing import Callable, Iterable, Type

from domain.events import DomainEvent


class SimpleEventDispatcher:

    def __init__(self) -> None:
        self._handlers: dict[Type[DomainEvent], list[Callable[[DomainEvent], None]]] = {}

    def register(
        self,
        event_type: Type[DomainEvent],
        handler: Callable[[DomainEvent], None],
    ) -> None:
        if event_type not in self._handlers:
            self._handlers[event_type] = []

        self._handlers[event_type].append(handler)

    def dispatch(self, events: Iterable[DomainEvent]) -> None:
        for event in events:
            handlers = self._handlers.get(type(event), [])
            for handler in handlers:
                handler(event)
