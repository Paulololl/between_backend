All instructions are in this Notion link:

https://www.notion.so/MASTER-NOTES-1ba140a2fb9480ae9b1bf90bfd473312?pvs=4

# Set up your .env with the .env.sample file. MAKE A .env COPY

# Make sure that the Docker is up whether on the app or CLI:
docker compose up

# Alternative if you want to use the same terminal for other stuff while docker is up:
docker compose up -d

# Runserver command (for HTTPS):
python manage.py runserver_plus localhost:8000 --cert mkcert/localhost.pem --key mkcert/localhost-key.pem


# Runserver command on anything via mkcert-wsl (for HTTPS):
python manage.py runserver_plus 0.0.0.0:8000 --cert mkcert-wsl/localhost.pem --key mkcert-wsl/localhost-key.pem


# Shut down docker either on app or CLI:
docker compose down