#!/bin/bash
# Install Java if not available
if ! command -v java &> /dev/null; then
    echo "Installing Java..."
    apt-get update
    apt-get install -y openjdk-11-jdk
fi

# Install Python dependencies
pip install -r requirements.txt

echo "Build completed successfully!"
