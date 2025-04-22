from django.contrib import admin

from .models import (SchoolPartnershipList, Department, Program, School)


model_to_register = [SchoolPartnershipList, Department, Program, School]

for model in model_to_register:
    admin.site.register(model)


