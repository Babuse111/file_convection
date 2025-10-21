from flask import Flask, request, render_template, send_from_directory, flash, redirect, url_for, jsonify
import os
import tabula
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

def clean_amount(amount_str):
    """Clean and convert amount strings to float"""
    if pd.isna(amount_str) or amount_str == '':
        return None
    
    # Convert to string and clean
    amount_str = str(amount_str).strip()
    
    # Remove 'R' and other currency symbols
    amount_str = re.sub(r'[R$€£]', '', amount_str)
    
    # Handle negative amounts in parentheses or with minus sign
    if '(' in amount_str and ')' in amount_str:
        amount_str = '-' + re.sub(r'[()]', '', amount_str)
    
    # Remove spaces and commas
    amount_str = re.sub(r'[\s,]', '', amount_str)
    
    # Try to convert to float
    try:
        return float(amount_str)
    except:
        return None

def extract_transaction_data(df_list, bank_type="auto"):
    """Extract and clean transaction data from the messy PDF data"""
    # Import the improved extraction function from pdf_cleaner
    import pdf_cleaner
    return pdf_cleaner.extract_transaction_data(df_list, bank_type)

def process_pdf_to_csv(pdf_path, output_folder, bank_type="auto"):
    """Convert PDF to CSV and return the output file path"""
    try:
        # Ensure output folder exists
        os.makedirs(output_folder, exist_ok=True)
        
        # Set environment variable to force subprocess mode
        os.environ["TABULA_JAVA"] = "subprocess"
        
        # Get filename without extension
        filename = os.path.splitext(os.path.basename(pdf_path))[0]
        csv_path = os.path.join(output_folder, f"{filename}.csv")
        
        # Read PDF file using subprocess mode
        df_list = tabula.read_pdf(pdf_path, pages='all', force_subprocess=True)
        
        # Extract and clean transaction data
        transactions = extract_transaction_data(df_list, bank_type)
        
        if not transactions:
            raise Exception("No transactions found in PDF")
        
        # Create DataFrame with proper structure
        df = pd.DataFrame(transactions)
        
        # Sort by date
        try:
            df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y')
            df = df.sort_values('Date')
            df['Date'] = df['Date'].dt.strftime('%d/%m/%Y')
        except:
            pass
        
        # Remove duplicates
        df = df.drop_duplicates()
        
        # Save to CSV with proper formatting
        df.to_csv(csv_path, index=False)
        
        return csv_path, len(df)
    
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
    bank_type = request.form.get('bank_type', 'auto')  # Get selected bank type
    
    if not files or files[0].filename == '':
        flash('No file selected')
        return redirect(url_for('index'))
    
    successful_uploads = []
    failed_uploads = []
    
    # Create a timestamp folder for this batch
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    batch_output_folder = os.path.join(app.config['OUTPUT_FOLDER'], f"batch_{timestamp}")
    os.makedirs(batch_output_folder, exist_ok=True)
    
    for file in files:
        if file and allowed_file(file.filename):
            try:
                filename = secure_filename(file.filename)
                
                # Save uploaded file
                upload_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(upload_path)
                
                # Process PDF to CSV with selected bank type
                csv_path, row_count = process_pdf_to_csv(upload_path, batch_output_folder, bank_type)
                
                successful_uploads.append({
                    'filename': filename,
                    'csv_file': os.path.basename(csv_path),
                    'rows': row_count,
                    'bank_type': bank_type
                })
                
                # Clean up uploaded file
                os.remove(upload_path)
                
            except Exception as e:
                failed_uploads.append({
                    'filename': file.filename,
                    'error': str(e)
                })
                # Clean up uploaded file if it exists
                upload_path = os.path.join(app.config['UPLOAD_FOLDER'], secure_filename(file.filename))
                if os.path.exists(upload_path):
                    os.remove(upload_path)
        else:
            failed_uploads.append({
                'filename': file.filename,
                'error': 'Invalid file type. Only PDF files are allowed.'
            })
    
    # Create a zip file with all CSV outputs
    if successful_uploads:
        zip_filename = f"csv_outputs_{timestamp}.zip"
        zip_path = os.path.join(app.config['OUTPUT_FOLDER'], zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for file_info in successful_uploads:
                csv_file_path = os.path.join(batch_output_folder, file_info['csv_file'])
                zipf.write(csv_file_path, file_info['csv_file'])
    
    return render_template('results.html', 
                         successful_uploads=successful_uploads,
                         failed_uploads=failed_uploads,
                         batch_folder=f"batch_{timestamp}",
                         zip_file=zip_filename if successful_uploads else None,
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
