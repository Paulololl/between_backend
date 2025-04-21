from django.urls import path
from .views import LightcastSkillsAPIView

urlpatterns = [
    path('skills/', LightcastSkillsAPIView.as_view(), name="lightcast_skills")
]
