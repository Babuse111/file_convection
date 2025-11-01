#!/bin/sh

# This script starts the Gunicorn server.
# Using a shell script is a more robust way to launch the server,
# especially when dealing with environment variables and complex commands.

gunicorn --preload --workers 1 --bind "0.0.0.0:$PORT" --timeout 180 wsgi:app
