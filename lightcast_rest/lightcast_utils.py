import os
import requests
from dotenv import load_dotenv

# importing stuff from .env
load_dotenv()

url = os.getenv("LIGHTCAST_TOKEN_URL")

def get_lightcast_token():
  payload = {
    'client_id': os.getenv("LIGHTCAST_CLIENT_ID"),
    'client_secret': os.getenv('LIGHTCAST_SECRET'),
    'grant_type': 'client_credentials',
    'scope': os.getenv('LIGHTCAST_SCOPE'),
  }

  headers = {
    'Content-Type': 'application/x-www-form-urlencoded'
  }

  response = requests.request("POST", url, data=payload, headers=headers)

  response.raise_for_status()
  return response.json()['access_token']
