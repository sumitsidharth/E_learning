from django.apps import AppConfig


class EduverseConfig(AppConfig):
    name = 'Eduverse'
    
    def ready(self):
        import Eduverse.signals
