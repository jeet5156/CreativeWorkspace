class EventBus:
    """
    Lightweight event dispatcher.

    More functionality will be added later.
    """

    def __init__(self):
        self._subscribers = {}