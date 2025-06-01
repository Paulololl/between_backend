from django.core.cache import cache
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
import requests
from .lightcast_utils import get_lightcast_token


class LightcastSkillsAPIView(APIView):

  def get(self, request):
    query = request.GET.get('q', '')
    skill_type = request.GET.get('type', '')
    limit = int(request.GET.get('limit', 10)) # default is 10

    cache_key = f"lightcast:{query}:{skill_type}:{limit}"
    cached_result = cache.get(cache_key)
    if cached_result:
      return Response(cached_result, status=status.HTTP_200_OK)

    try:
      access_token = get_lightcast_token()
      api_url = "https://emsiservices.com/skills/versions/latest/skills"

      response = requests.get(
        api_url,

        headers={
          "Authorization": f"Bearer {access_token}"
        },

        params={
          "q": query,
          "typeIds": skill_type,
          "fields": "id, name, type",
          "limit": limit,
        }
      )

      response.raise_for_status()
      cache.set(cache_key, response.json(), timeout=300)
      return Response(response.json(), status=status.HTTP_200_OK)

    except requests.RequestException as e:
      error_msg = str(e)
      if hasattr(e, 'response') and e.response is not None:
        error_msg += f" | Response content: {e.response.text}"
      return Response({"error": error_msg}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)