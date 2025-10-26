FROM python:3.11-slim

# install Java (OpenJDK) and minimal system deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends openjdk-17-jre-headless libfontconfig && \
    rm -rf /var/lib/apt/lists/*

ENV JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64

WORKDIR /app
COPY . /app

RUN python -m pip install --upgrade pip setuptools wheel
RUN pip install -r requirements.txt

EXPOSE 5001
CMD ["python", "app.py"]