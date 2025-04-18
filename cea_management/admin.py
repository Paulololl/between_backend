from django.contrib import admin

from .models import (SchoolPartnershipList, Department, Program)


model_to_register = [SchoolPartnershipList, Department, Program]

for model in model_to_register:
    admin.site.register(model)


