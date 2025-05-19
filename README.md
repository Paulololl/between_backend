All instructions are in this Notion link:

https://www.notion.so/MASTER-NOTES-1ba140a2fb9480ae9b1bf90bfd473312?pvs=4

# Runserver command (for HTTPS):
python manage.py runserver_plus localhost:8000 --cert mkcert/localhost.pem --key mkcert/localhost-key.pem


# Runserver command on anything via mkcert-wsl (for HTTPS):
python manage.py runserver_plus 0.0.0.0:8000 --cert mkcert-wsl/localhost.pem --key mkcert-wsl/localhost-key.pem