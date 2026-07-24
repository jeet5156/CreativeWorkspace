class AppContext:
    """
    Stores shared services used throughout the application.
    """

    def __init__(self):
        self.project_service = None
        self.event_bus = None