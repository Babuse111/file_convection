# Use the official Python 3.11 slim image as a baseFROM python:3.11-slim

FROM python:3.11-slim

# install Java (OpenJDK) and minimal system deps

# Set environment variables to prevent interactive prompts during buildRUN apt-get update && \

ENV DEBIAN_FRONTEND=noninteractive    apt-get install -y --no-install-recommends openjdk-17-jre-headless libfontconfig && \

    rm -rf /var/lib/apt/lists/*

# Install OpenJDK 17 (for JPype/tabula-py) and clean up apt cache

# This runs as root inside the Docker build environmentENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

RUN apt-get update && \

    apt-get install -y --no-install-recommends openjdk-17-jre-headless && \WORKDIR /app

    rm -rf /var/lib/apt/lists/*COPY . /app



# Set the JAVA_HOME environment variable for JPype to find the JVMRUN python -m pip install --upgrade pip setuptools wheel

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64RUN pip install -r requirements.txt



# Set the working directory in the containerEXPOSE 5001

WORKDIR /appCMD ["python", "app.py"]

# Copy the entire project into the working directory
COPY . .

# Create the logs directory so the application can write to it
RUN mkdir -p logs

# Upgrade pip and install Python dependencies from requirements.txt
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Expose the port Render will run the service on.
# Render provides the PORT environment variable, which gunicorn will use.
EXPOSE 10000

# Command to run the application using the Gunicorn production server.
# This uses the 'wsgi:app' entry point.
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "wsgi:app"]
