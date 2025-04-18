from django.contrib import admin

from .models import (Application, Endorsement, Notification)


model_to_register = [Application, Endorsement, Notification]

for model in model_to_register:
    admin.site.register(model)


