class EventBus:
    def __init__(self):
        self._subscribers = {}

    def subscribe(self, event_type, callback):
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(callback)

    def emit(self, event_type, data):
        for callback in self._subscribers.get(event_type, []):
            callback(data)

event_bus = EventBus()
