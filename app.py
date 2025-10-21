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

def extract_transaction_data(df_list, bank_type="auto"):
    """Extract and clean transaction data from the messy PDF data"""
    # Import the improved extraction function from pdf_cleaner
    import pdf_cleaner
    return pdf_cleaner.extract_transaction_data(df_list, bank_type)

def process_pdf_to_csv(pdf_path, output_folder, bank_type="auto"):
    """Convert PDF to CSV and return the output file path - Enhanced for ABSA"""
    try:
        # Ensure output folder exists
        os.makedirs(output_folder, exist_ok=True)
        
        # Import pdf_cleaner module for enhanced PDF processing
        import pdf_cleaner
        
        # Get filename without extension
        filename = os.path.splitext(os.path.basename(pdf_path))[0]
        csv_path = os.path.join(output_folder, f"{filename}.csv")
        
        print(f"Processing PDF: {pdf_path}")
        print(f"Bank type: {bank_type}")
        
        # Use the enhanced extraction method from pdf_cleaner (supports ABSA better)
        df_list = pdf_cleaner.extract_tables_from_pdf(pdf_path)
        
        if not df_list:
            # This should not happen with the new enhanced extraction
            raise Exception("No data could be extracted from PDF")
        
        print(f"Found {len(df_list)} data sources in PDF")
        
        # Extract and clean transaction data
        transactions_df = extract_transaction_data(df_list, bank_type)
        
        if transactions_df.empty:
            raise Exception("No transaction data could be extracted")
        
        # Sort by date if possible
        try:
            transactions_df['Date'] = pd.to_datetime(transactions_df['Date'], format='%d/%m/%Y', errors='coerce')
            transactions_df = transactions_df.sort_values('Date')
            transactions_df['Date'] = transactions_df['Date'].dt.strftime('%d/%m/%Y')
        except:
            print("Could not sort by date, keeping original order")
        
        # Remove duplicates
        transactions_df = transactions_df.drop_duplicates()
        
        # Save to CSV with proper formatting
        transactions_df.to_csv(csv_path, index=False)
        
        print(f"Saved CSV to: {csv_path}")
        print(f"Extracted {len(transactions_df)} transactions")
        
        return csv_path, len(transactions_df)
        
    except Exception as e:
        print(f"Error in process_pdf_to_csv: {str(e)}")
        raise Exception(f"Error processing PDF: {str(e)}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_files():
    if 'pdf_files' not in request.files:
        flash('No files selected')
        return redirect(request.url)
    
    files = request.files.getlist('pdf_files')
    bank_type = request.form.get('bank_type', 'auto')
    
    if not files or all(file.filename == '' for file in files):
        flash('No files selected')
        return redirect(request.url)
    
    results = []
    failed_files = []
    
    # Clear previous uploads and outputs
    for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER]:
        if os.path.exists(folder):
            shutil.rmtree(folder)
        os.makedirs(folder, exist_ok=True)
    
    for file in files:
        if file and allowed_file(file.filename):
            try:
                # Save uploaded file
                filename = secure_filename(file.filename)
                upload_path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(upload_path)
                
                # Process PDF to CSV using enhanced extraction
                csv_path, row_count = process_pdf_to_csv(upload_path, OUTPUT_FOLDER, bank_type)
                csv_filename = os.path.basename(csv_path)
                
                results.append({
                    'pdf_name': filename,
                    'csv_name': csv_filename,
                    'csv_path': csv_path,
                    'row_count': row_count
                })
                
            except Exception as e:
                failed_files.append({
                    'filename': file.filename,
                    'error': str(e)
                })
    
    if not results and failed_files:
        # If all files failed, show error page
        return render_template('index.html', error=f"All files failed to process. First error: {failed_files[0]['error']}")
    
    # Create ZIP file if multiple CSVs
    zip_path = None
    if len(results) > 1:
        zip_filename = f"bank_statements_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        zip_path = os.path.join(OUTPUT_FOLDER, zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for result in results:
                zipf.write(result['csv_path'], result['csv_name'])
    
    return render_template('results.html', 
                         results=results, 
                         failed_files=failed_files,
                         zip_filename=os.path.basename(zip_path) if zip_path else None,
                         bank_type=bank_type.title())

@app.route('/download/<filename>')
def download_file(filename):
    return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'message': 'Enhanced HNF PDF Converter is running'})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
