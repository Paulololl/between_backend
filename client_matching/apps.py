from django.apps import AppConfig

from client_matching.utils import get_sentence_model


class ClientMatchingConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'client_matching'

    def ready(self):
        get_sentence_model()

