from django.apps import AppConfig


class BatchConfig(AppConfig):
    name = 'batch'

    def ready(self):
        # Wire the DeveloperProfile refresh signal. Importing here (not
        # at module top) is the standard Django idiom — `ready()` runs
        # exactly once per process after apps are loaded.
        from . import signals  # noqa: F401
