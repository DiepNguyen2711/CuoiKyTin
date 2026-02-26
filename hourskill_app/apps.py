from django.apps import AppConfig

class HourskillAppConfig(AppConfig):
    name = "hourskill_app"

    # Thêm 2 dòng này để đánh thức Signals
    def ready(self):
        import hourskill_app.signals