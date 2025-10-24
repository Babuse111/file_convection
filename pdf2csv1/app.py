from flask import Flask, request, render_template, send_from_directory, flash, redirect, url_for, jsonify
import os
import pandas as pd
from werkzeug.utils import secure_filename
import zipfile
from datetime import datetime
import shutil
import re

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'

# Configuration
UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'pdf2csv_output'
ALLOWED_EXTENSIONS = {'pdf'}

# Create necessary directories
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(OUTPUT_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def process_pdf_to_csv(pdf_path, output_folder, bank_type="auto"):
    """Convert PDF to CSV and return the output file path, row count and DataFrame"""
    try:
        os.makedirs(output_folder, exist_ok=True)
        filename = os.path.splitext(os.path.basename(pdf_path))[0]
        csv_path = os.path.join(output_folder, f"{filename}.csv")

        # Use pdf_cleaner to extract transactions (may return list[dict] or DataFrame)
        transactions = pdf_cleaner.process_pdf(pdf_path)

        # Normalize to DataFrame (always ensure df is defined)
        if isinstance(transactions, pd.DataFrame):
            df = transactions.copy()
        else:
            df = pd.DataFrame(transactions)

        # If nothing extracted, raise so caller can mark as failed
        if df.empty:
            raise Exception("No transactions found in PDF")

        # Drop columns that are completely empty (don't force specific columns)
        df = df.dropna(axis=1, how='all')

        # Preserve full digits/format for Amount if present (store as string)
        if 'Amount' in df.columns:
            df['Amount'] = df['Amount'].astype(str)

        # Save CSV exactly as extracted
        df.to_csv(csv_path, index=False)

        return csv_path, len(df), df

    except Exception as e:
        raise Exception(f"Error processing PDF: {str(e)}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    if 'files[]' not in request.files:
        flash('No file selected')
        return redirect(request.url)

    files = request.files.getlist('files[]')
    bank_type = request.form.get('bank_type', 'auto')

    if not files or files[0].filename == '':
        flash('No file selected')
        return redirect(url_for('index'))

    successful_uploads = []
    failed_uploads = []

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_output_folder = os.path.join(app.config['OUTPUT_FOLDER'], f"batch_{timestamp}")
    os.makedirs(batch_output_folder, exist_ok=True)

    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            try:
                # Save uploaded file
                file.save(upload_path)

                # Process PDF -> CSV
                csv_path, row_count, df = process_pdf_to_csv(upload_path, batch_output_folder, bank_type=bank_type)

                # Build preview (safe fallback)
                try:
                    preview_rows = df.head(5).fillna('').to_dict(orient='records')
                    columns = df.columns.tolist()
                except Exception:
                    preview_rows = []
                    columns = []

                successful_uploads.append({
                    'pdf_name': filename,
                    'csv_name': os.path.basename(csv_path),
                    'row_count': row_count,
                    'columns': columns,
                    'preview_rows': preview_rows
                })

            except Exception as e:
                failed_uploads.append({
                    'filename': filename,
                    'error': str(e)
                })
            finally:
                # Clean up uploaded file if it exists
                try:
                    if os.path.exists(upload_path):
                        os.remove(upload_path)
                except Exception:
                    pass
        else:
            failed_uploads.append({
                'filename': file.filename if file else 'unknown',
                'error': 'Invalid file type. Only PDF files are allowed.'
            })

    # Create a zip file with all CSV outputs (if any)
    zip_filename = None
    if successful_uploads:
        zip_filename = f"csv_outputs_{timestamp}.zip"
        zip_path = os.path.join(app.config['OUTPUT_FOLDER'], zip_filename)
        try:
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for info in successful_uploads:
                    csv_file_path = os.path.join(batch_output_folder, info['csv_name'])
                    if os.path.exists(csv_file_path):
                        zipf.write(csv_file_path, info['csv_name'])
        except Exception as e:
            # If zip creation fails, mark as non-fatal but include message in failed_uploads
            failed_uploads.append({
                'filename': zip_filename,
                'error': f"ZIP creation failed: {str(e)}"
            })
            zip_filename = None

    return render_template('results.html',
                           results=successful_uploads,
                           failed_files=failed_uploads,
                           batch_folder=f"batch_{timestamp}",
                           zip_filename=zip_filename,
                           bank_type=bank_type)

@app.route('/download/<path:filename>')
def download_file(filename):
    file_path = os.path.join(app.config['OUTPUT_FOLDER'], filename)
    if os.path.exists(file_path):
        return send_from_directory(app.config['OUTPUT_FOLDER'], filename, as_attachment=True)
    else:
        flash(f'File not found: {filename}')
        return redirect(url_for('index'))

@app.route('/download_batch/<batch_folder>/<filename>')
def download_batch_file(batch_folder, filename):
    batch_path = os.path.join(app.config['OUTPUT_FOLDER'], batch_folder)
    file_path = os.path.join(batch_path, filename)
    if os.path.exists(file_path):
        return send_from_directory(batch_path, filename, as_attachment=True)
    else:
        flash(f'File not found: {filename} in batch {batch_folder}')
        return redirect(url_for('index'))

@app.route('/clear_outputs')
def clear_outputs():
    """Clear all output files"""
    try:
        if os.path.exists(app.config['OUTPUT_FOLDER']):
            shutil.rmtree(app.config['OUTPUT_FOLDER'])
        os.makedirs(app.config['OUTPUT_FOLDER'], exist_ok=True)
        flash('All output files cleared successfully!')
    except Exception as e:
        flash(f'Error clearing files: {str(e)}')
    return redirect(url_for('index'))

@app.route('/debug')
def debug_info():
    """Debug route to check folder structure"""
    debug_info = {
        'upload_folder': app.config['UPLOAD_FOLDER'],
        'output_folder': app.config['OUTPUT_FOLDER'],
        'upload_exists': os.path.exists(app.config['UPLOAD_FOLDER']),
        'output_exists': os.path.exists(app.config['OUTPUT_FOLDER']),
        'current_dir': os.getcwd(),
        'output_contents': []
    }
    
    if os.path.exists(app.config['OUTPUT_FOLDER']):
        try:
            debug_info['output_contents'] = os.listdir(app.config['OUTPUT_FOLDER'])
        except:
            debug_info['output_contents'] = ['Error reading directory']
    
    return jsonify(debug_info)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)), debug=False)
