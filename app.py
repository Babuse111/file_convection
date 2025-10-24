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
        
        # Ensure we only have the columns we want: Date, Description, Amount
        expected_columns = ['Date', 'Description', 'Amount']
        for col in expected_columns:
            if col not in transactions_df.columns:
                transactions_df[col] = ''
        # Keep only the expected columns in the right order
        transactions_df = transactions_df[expected_columns]
        
        # Do not modify columns, just use what was extracted
        # Optionally, drop completely empty columns
        transactions_df = transactions_df.dropna(axis=1, how='all')
        
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
    print("Upload route called")
    print(f"Request method: {request.method}")
    print(f"Request files: {list(request.files.keys())}")
    print(f"Request form: {dict(request.form)}")
    
    # Check for different possible file field names
    files = None
    file_field_names = ['pdf_files', 'files[]', 'files', 'file']
    
    for field_name in file_field_names:
        if field_name in request.files:
            files = request.files.getlist(field_name)
            print(f"Found files in field: {field_name}")
            break
    
    if not files:
        flash('No files were uploaded. Please select PDF files.')
        return redirect(url_for('index'))
    
    bank_type = request.form.get('bank_type', 'auto')
    print(f"Bank type: {bank_type}")
    
    if all(file.filename == '' for file in files):
        flash('No files selected')
        return redirect(url_for('index'))
    
    results = []
    failed_files = []
    
    # Clear previous uploads and outputs
    for folder in [UPLOAD_FOLDER, OUTPUT_FOLDER]:
        if os.path.exists(folder):
            shutil.rmtree(folder)
        os.makedirs(folder, exist_ok=True)
    
    for file in files:
        if file and file.filename != '' and allowed_file(file.filename):
            try:
                print(f"Processing file: {file.filename}")
                
                # Save uploaded file
                filename = secure_filename(file.filename)
                upload_path = os.path.join(UPLOAD_FOLDER, filename)
                file.save(upload_path)
                
                # Process PDF to CSV using enhanced extraction
                csv_path, row_count = process_pdf_to_csv(upload_path, OUTPUT_FOLDER, bank_type)
                csv_filename = os.path.basename(csv_path)
                
                result_dict = {
                    'pdf_name': filename,
                    'csv_name': os.path.basename(csv_path),
                    'row_count': len(df),
                    'columns': df.columns.tolist(),
                    'preview_rows': df.head(5).to_dict(orient='records')
                }
                
                results.append(result_dict)
                
                print(f"Successfully processed: {filename} -> {csv_filename} ({row_count} transactions)")
                
            except Exception as e:
                print(f"Failed to process {file.filename}: {str(e)}")
                failed_files.append({
                    'filename': file.filename,
                    'error': str(e)
                })
        elif file and file.filename != '':
            failed_files.append({
                'filename': file.filename,
                'error': 'Invalid file type. Only PDF files are allowed.'
            })
    
    if not results and failed_files:
        # If all files failed, show error page with details
        error_msg = f"All files failed to process. Errors: {'; '.join([f'{f['filename']}: {f['error']}' for f in failed_files])}"
        return render_template('index.html', error=error_msg)
    
    # Create ZIP file if multiple CSVs
    zip_path = None
    zip_filename = None
    if len(results) > 1:
        zip_filename = f"bank_statements_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        zip_path = os.path.join(OUTPUT_FOLDER, zip_filename)
        
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            for result in results:
                zipf.write(result['csv_path'], result['csv_name'])
    
    print(f"Rendering results: {len(results)} successful, {len(failed_files)} failed")
    
    return render_template('results.html', 
                         results=results, 
                         failed_files=failed_files,
                         zip_filename=zip_filename,
                         bank_type=bank_type.title())

# Add a simple test route
@app.route('/test')
def test():
    return jsonify({'message': 'Flask app is working', 'routes': [str(rule) for rule in app.url_map.iter_rules()]})

@app.route('/download/<filename>')
def download_file(filename):
    try:
        return send_from_directory(OUTPUT_FOLDER, filename, as_attachment=True)
    except Exception as e:
        flash(f'Error downloading file: {str(e)}')
        return redirect(url_for('index'))

@app.route('/health')
def health_check():
    return jsonify({'status': 'healthy', 'message': 'Enhanced HNF PDF Converter is running'})

# Add error handlers
@app.errorhandler(404)
def not_found_error(error):
    return render_template('index.html', error="Page not found"), 404

@app.errorhandler(405)
def method_not_allowed_error(error):
    return render_template('index.html', error="Method not allowed. Please use the upload form."), 405

@app.errorhandler(500)
def internal_error(error):
    return render_template('index.html', error="Internal server error. Please try again."), 500

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting Flask app on port {port}")
    print(f"Upload folder: {UPLOAD_FOLDER}")
    print(f"Output folder: {OUTPUT_FOLDER}")
    app.run(host='0.0.0.0', port=port, debug=True)  # Enable debug mode to see errors
