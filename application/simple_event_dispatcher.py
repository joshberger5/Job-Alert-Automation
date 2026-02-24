class SimpleEventDispatcher:

    def __init__(self):
        self._handlers = {}

    def register(self, event_type, handler):
        if event_type not in self._handlers:
            self._handlers[event_type] = []

        self._handlers[event_type].append(handler)

    def dispatch(self, events):
        for event in events:
            handlers = self._handlers.get(type(event), [])
            for handler in handlers:
                handler(event)