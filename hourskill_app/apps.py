from django.apps import AppConfig


class HourskillAppConfig(AppConfig):
    """Application configuration that wires signals on startup."""

    name = "hourskill_app"

    def ready(self):
        """Import signal handlers so Django registers them once the app is ready."""
        import hourskill_app.signals  # noqa: F401