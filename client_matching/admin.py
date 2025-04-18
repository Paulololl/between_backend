from django.contrib import admin

from .models import (HardSkillsTagList, SoftSkillsTagList, InternshipPosting, InternshipRecommendation,
                     Report, MinQualification, Benefit, Advertisement, RequiredHardSkill,
                     RequiredSoftSkill, KeyTask, PersonInCharge)


model_to_register = [HardSkillsTagList, SoftSkillsTagList, InternshipPosting, InternshipRecommendation,
                     Report, MinQualification, Benefit, Advertisement, RequiredHardSkill,
                     RequiredSoftSkill, KeyTask, PersonInCharge]

for model in model_to_register:
    admin.site.register(model)


