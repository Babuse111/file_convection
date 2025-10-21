# PDF to CSV Converter Web Application

A Flask-based web application that converts multiple PDF files to CSV format with automatic header deduplication.

## Features

- 📄 **Multiple PDF Upload**: Upload multiple PDF files at once
- 🔄 **Smart Processing**: Automatically removes duplicate headers across pages
- 📦 **Batch Download**: Download individual CSV files or get all in a zip file
- 🎯 **Organized Output**: Files saved in `pdf2csv_output` folder with timestamp batches
- 🌐 **Modern UI**: Beautiful, responsive Bootstrap interface
- ☁️ **Cloud Ready**: Configured for Render.com deployment

## Local Development

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python app.py
```

3. Open your browser to `http://localhost:5000`

## Deployment to Render

1. Push your code to GitHub
2. Connect your GitHub repository to Render
3. The app will automatically deploy using the `render.yaml` configuration

## File Structure

```
pdf2csv1/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── Procfile              # Render deployment config
├── render.yaml           # Render service configuration
├── templates/
│   ├── index.html        # Upload page
│   └── results.html      # Results page
├── uploads/              # Temporary upload storage
└── pdf2csv_output/       # Converted CSV files
    └── batch_YYYYMMDD_HHMMSS/  # Timestamped batches
```

## How It Works

1. Users upload multiple PDF files through the web interface
2. Each PDF is processed using tabula-py with subprocess mode
3. Duplicate headers are automatically detected and removed
4. All pages from each PDF are combined into a single CSV
5. Files are organized in timestamped batch folders
6. Users can download individual files or a zip containing all conversions

## Requirements

- Python 3.8+
- Java (required by tabula-py)
- Flask and dependencies (see requirements.txt)
