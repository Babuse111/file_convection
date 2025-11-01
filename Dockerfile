# Use the official Python 3.11 slim image as a base
FROM python:3.11-slim

# Set environment variables to prevent interactive prompts during build
ENV DEBIAN_FRONTEND=noninteractive

# Install OpenJDK 21 (the version available in the base image)
RUN apt-get update && \
    apt-get install -y --no-install-recommends openjdk-21-jre-headless && \
    rm -rf /var/lib/apt/lists/*

# Set the JAVA_HOME environment variable for the new Java version
ENV JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64

# Set the working directory in the container
WORKDIR /app

# Copy the entire project into the working directory
COPY . .

# Create the logs directory so the application can write to it
RUN mkdir -p logs

# Upgrade pip and install Python dependencies from requirements.txt
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Expose the port Render will run the service on.
EXPOSE 10000

# Command to run the application using Gunicorn.
# We are reverting to the faster configuration without --preload.
CMD gunicorn --bind 0.0.0.0:$PORT --timeout 180 --log-level debug wsgi:app
