# Production startup script for Flask application

# Create required directories
Write-Host "📁 Creating required directories..."
New-Item -ItemType Directory -Force -Path "uploads" | Out-Null
New-Item -ItemType Directory -Force -Path "outputs" | Out-Null
New-Item -ItemType Directory -Force -Path "logs" | Out-Null

# Set production environment variables
Write-Host "⚙️ Configuring environment..."
$env:FLASK_ENV = "production"
$env:FLASK_DEBUG = "0"
$env:PORT = "8000"
$env:THREADS = "4"

# Start production server
Write-Host "🚀 Starting production server..."
poetry run python wsgi.py
