from application.event_publisher import EventPublisher


class InMemoryEventPublisher(EventPublisher):

    def __init__(self, dispatcher):
        self.dispatcher = dispatcher

    def publish(self, events):
        self.dispatcher.dispatch(events)