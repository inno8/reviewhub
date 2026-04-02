from django.apps import AppConfig


class EvaluationsConfig(AppConfig):
    name = 'evaluations'
    default_auto_field = 'django.db.models.BigAutoField'
    
    def ready(self):
        """Import signals when app is ready."""
        import evaluations.signals
