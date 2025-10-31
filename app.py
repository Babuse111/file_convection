import os
import sys
import re
import io
import time 
import pandas as pd
import tabula
import uuid
import pdfplumber
from datetime import datetime
from pathlib import Path
from typing import List, Tuple
from flask import Flask, render_template, request, redirect, url_for, flash, send_from_directory, jsonify
from werkzeug.utils import secure_filename
from dotenv import load_dotenv

# --- Java Configuration and Initialization ---
def get_jar_files(lib_path: Path) -> List[str]:
    """Get all JAR files from the lib directory."""
    return [str(f) for f in lib_path.glob('*.jar') if f.is_file()]

def configure_java() -> bool:
    """Configure Java environment for the application."""
    java_home_str = os.getenv('JAVA_HOME')
    if not java_home_str:
        print("Error: JAVA_HOME environment variable is not set.")
        return False

    java_home = Path(java_home_str)
    if not java_home.exists():
        print(f"Error: Java installation not found at {java_home}")
        return False

    # Add both bin and lib directories to PATH
    java_bin = str(java_home / 'bin')
    java_lib = str(java_home / 'lib')
    
    paths = os.environ.get('PATH', '').split(os.pathsep)
    if java_bin not in paths:
        paths.insert(0, java_bin)
    if java_lib not in paths:
        paths.insert(0, java_lib)
    
    os.environ['PATH'] = os.pathsep.join(paths)

    # Configure classpath with required JAR files
    lib_path = Path(__file__).parent / 'lib'
    jar_files = get_jar_files(lib_path)
    
    if not jar_files:
        print("Warning: No JAR files found in lib directory.")
        
    os.environ['CLASSPATH'] = os.pathsep.join(jar_files)
    
    # Dynamically import jpype and start JVM if not started
    global jpype
    import jpype
    import jpype.imports
    
    if not jpype.isJVMStarted():
        try:
            # On Linux, libjvm.so should be found automatically if JAVA_HOME is correct
            jvm_path = jpype.getDefaultJVMPath()
            if not Path(jvm_path).exists():
                # Fallback for Render/Debian-based systems
                debian_jvm_path = '/usr/lib/jvm/default-java/lib/server/libjvm.so'
                if Path(debian_jvm_path).exists():
                    jvm_path = debian_jvm_path
                else:
                    print("Error: libjvm.so not found at default or fallback paths.")
                    return False
            
            jpype.startJVM(jvm_path, convertStrings=False)
            print(f"JVM started successfully from {jvm_path}.")
        except Exception as e:
            print(f"Failed to start JVM: {e}")
            return False
            
    return True

# Initialize Java before other imports
configure_java()

# Initialize Flask app
app = Flask(__name__)
load_dotenv()

# Configure secret key
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-secret-key-here')

# Setup paths
BASE_DIR = Path(__file__).parent
UPLOADS = Path(os.getenv('UPLOAD_DIR', BASE_DIR / "uploads"))
OUTPUTS = Path(os.getenv('OUTPUT_DIR', BASE_DIR / "outputs"))

# Ensure directories exist
UPLOADS.mkdir(exist_ok=True, parents=True)
OUTPUTS.mkdir(exist_ok=True, parents=True)

def cleanup_old_files(directory: Path, max_age_hours: int = 24):
    """Remove files older than max_age_hours from the specified directory."""
    current_time = time.time()
    
    for file_path in directory.glob('*.*'):
        try:
            if current_time - file_path.stat().st_mtime > (max_age_hours * 3600):
                file_path.unlink(missing_ok=True)
        except (PermissionError, OSError) as e:
            print(f"Warning: Could not delete old file {file_path}: {e}")

# --- Utility and Helper Functions ---

def clean_sa_amount(amount_str: str) -> float:
    """
    Cleans a South African amount string (e.g., '1.234,56', '167,88-', '126.383.51 Cr') 
    and returns a float.
    """
    if pd.isna(amount_str) or not amount_str:
        return 0.0
    
    s = str(amount_str).strip().replace('R', '').replace(' ', '')
    is_negative = s.endswith('-') or 'Dr' in s.upper() or s.startswith('-')
    
    # 1. Handle thousands/decimal separator replacement
    if ',' in s and s.count('.') > 0 and s.find(',') > s.rfind('.'):
        # Format: 1.234,56 (dot is thousands, comma is decimal)
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s and s.count('.') == 0:
        # Format: 167,88- (comma is decimal)
        s = s.replace(',', '.')
    elif s.count('.') > 1:
        # Format: 126.383.51 (dots are thousands, last dot is decimal) - often FNB
        parts = s.split('.')
        decimal_part = parts[-1]
        integer_part = ''.join(parts[:-1])
        s = integer_part + '.' + decimal_part
        
    # Remove negative indicators and credit/debit words for float conversion
    s_cleaned = s.replace('-', '').replace('Cr', '').replace('Dr', '').strip()
    
    try:
        amount = float(s_cleaned)
        return -amount if is_negative else amount
    except ValueError:
        return 0.0

def standardize_date(date_str: str, statement_year: int) -> str:
    """Converts various date formats (e.g., '05 08', '24/02/2023') to 'YYYY/MM/DD'."""
    if pd.isna(date_str) or not date_str:
        return ''
    
    date_str = str(date_str).strip()
    
    # List of possible date formats to try
    formats = [
        '%d/%m/%Y',            # FNB/Capitec/ABSA: 24/02/2023
        '%d %b %Y',            # 24 Feb 2023
        '%d %B %Y',            # 24 February 2023
    ]
    
    # Handle DD MM format (Standard Bank) - assumed year is statement_year
    # Example: '05 08' -> May 08
    if re.match(r'^\d{2}\s+\d{2}$', date_str):
        try:
            # Standard Bank's 'MM DD' is usually 'DD MM' but in their table it appears to be DD/MM without year.
            # We try parsing as Day/Month (DD MM) first, then insert the year.
            # Use '05 08' -> 05 May
            dt = datetime.strptime(f"{date_str} {statement_year}", '%d %m %Y')
            return dt.strftime('%Y/%m/%d')
        except ValueError:
            pass # Failed to parse as DD MM YYYY

    for fmt in formats:
        try:
            dt = datetime.strptime(date_str, fmt)
            return dt.strftime('%Y/%m/%d')
        except ValueError:
            continue
            
    # Handle DD MON (no year) - assumed year is statement_year
    try:
        # Tries to parse '24 Feb' as '24 Feb YYYY'
        dt = pd.to_datetime(f"{date_str} {statement_year}", format='%d %b %Y', errors='coerce')
        if not pd.isna(dt):
            return dt.strftime('%Y/%m/%d')
    except Exception:
        pass

    # Handle ABSA's DD/MM/YYYY
    try:
        dt = pd.to_datetime(date_str, format='%d/%m/%Y', errors='coerce')
        if not pd.isna(dt):
            return dt.strftime('%Y/%m/%d')
    except Exception:
        pass
        
    return ''


def create_final_csv_content(account_number: str, opening_balance: float, period: str, df: pd.DataFrame) -> str:
    """Generates the final CSV string including metadata header and transaction data."""
    
    # 1. Prepare metadata header
    # Ensure no extra commas are introduced in the header line
    csv_content = f'Account Number:,{account_number}\n'
    # Format opening balance to two decimal places
    csv_content += f'Opening Balance:,{opening_balance:.2f}\n'
    csv_content += f'Statement Period:,{period}\n' # Add period to the metadata header
    
    # 2. Add transaction data
    csv_buffer = io.StringIO()
    
    COLUMNS = ['Period', 'Date', 'Details', 'Debit', 'Credit', 'Balance', 'Cheque']
    
    # Ensure all required columns are present
    for col in COLUMNS:
        if col not in df.columns:
            if col in ['Debit', 'Credit', 'Balance']:
                df[col] = 0.0
            else:
                df[col] = ''
    
    # Insert Period (it should be the same for all rows in a single statement)
    df['Period'] = period
    
    # Standardize the 'Details' column to string
    df['Details'] = df['Details'].astype(str)

    # Reorder and select final columns
    df_final = df[COLUMNS].copy()

    # Format numeric columns to 2 decimals as strings
    for col in ['Debit', 'Credit', 'Balance']:
        df_final[col] = pd.to_numeric(df_final[col], errors='coerce').fillna(0)
        df_final[col] = df_final[col].apply(lambda x: f"{x:.2f}")

    # Write DataFrame to buffer
    df_final.to_csv(csv_buffer, index=False, header=True, lineterminator='\n')
    
    csv_content += csv_buffer.getvalue()
    
    return csv_content

# --- Core Logic for Bank Statement Conversion ---

def process_bank_statement_to_csv(pdf_path: Path, bank_type: str) -> str:
    """Process bank statement based on selected bank type."""
    # List of supported banks
    supported_banks = {
        'CAPITEC': process_capitec_statement,
        'FNB': process_fnb_statement,
        'ABSA': process_absa_statement,
        'STANDARD': process_standard_statement,
    }

    processor = supported_banks.get(bank_type)
    
    if processor:
        return processor(pdf_path)
    else:
        raise ValueError(f"Unsupported bank type: {bank_type}")


def process_fnb_statement(pdf_path: Path) -> str:
    """
    Process FNB bank statements.
    """
    print("Processing FNB statement...")
    
    try:
        # --- Metadata Extraction ---
        with pdfplumber.open(pdf_path) as pdf:
            text = pdf.pages[0].extract_text()
            
            # Extract account number
            account_matches = [
                re.search(r'(?:Account Number|Acc No|Trust Account)[^:\d]*?(\d{8,15})', text, re.IGNORECASE),
                re.search(r'Account\s*(?:Number|No)[:\s]*(\d+)', text, re.IGNORECASE),
            ]
            account_number = next((m.group(1) for m in account_matches if m), 'N/A')
            
            # Extract balance
            balance_matches = [
                re.search(r'(?:Opening Balance|Balance Brought Forward)[^R]*R?\s*([\d\s,\.]+)\s*(?:Cr|Dr)?', text, re.IGNORECASE),
                re.search(r'Opening Balance\s*:\s*R?\s*([\d,\.]+)', text, re.IGNORECASE),
            ]
            balance_str = next((m.group(1) for m in balance_matches if m), '0.00')
            opening_balance = clean_sa_amount(balance_str)

            # Extract period and year
            period_match = re.search(r'Statement Period:\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4}\s+to\s+\d{1,2}\s+[A-Za-z]+\s+\d{4})', text, re.IGNORECASE)
            period = period_match.group(1) if period_match else 'N/A'
            
            year_match = re.search(r'to\s+\d{1,2}\s+[A-Za-z]+\s+(\d{4})', period)
            statement_year = int(year_match.group(1)) if year_match else datetime.now().year


        # --- Transaction Extraction ---
        tables = tabula.read_pdf(
            str(pdf_path),
            pages='all',
            multiple_tables=True,
            lattice=False, # Better for FNB's non-grid text
            guess=True,
            silent=True
        )
        
        df_transactions = pd.DataFrame(columns=['Date', 'Details', 'Debit', 'Credit', 'Balance'])
        
        for table in tables:
            table = table.dropna(how='all')
            
            # Identify the date column
            date_col_index = -1
            date_pattern = r'\d{2}/\d{2}/\d{4}|\d{2}\s+[A-Za-z]{3}|\d{1,2}\s+\d{4}' # DD/MM/YYYY or DD MMM

            for i, col in enumerate(table.columns):
                date_matches = table[col].astype(str).str.contains(date_pattern, na=False, regex=True)
                # Check for at least 2 date matches to confirm the column
                if date_matches.sum() >= 2:
                    date_col_index = i
                    break

            if date_col_index == -1 or len(table.columns) < 4:
                continue

            try:
                # Assuming standard FNB structure after date: Date | Details | Amount | Balance
                date_col_name = table.columns[date_col_index]
                
                # Check column indices for robustness
                if date_col_index + 1 >= len(table.columns) or date_col_index + 2 >= len(table.columns) or date_col_index + 3 >= len(table.columns):
                    # Fallback to last two columns as Amount and Balance
                    amount_col_name = table.columns[-2]
                    balance_col_name = table.columns[-1]
                    details_col_name = table.columns[date_col_index + 1] if date_col_index + 1 < len(table.columns) else table.columns[0]
                else:
                    details_col_name = table.columns[date_col_index + 1] 
                    amount_col_name = table.columns[date_col_index + 2] # Usually Amount is next
                    balance_col_name = table.columns[date_col_index + 3] # Usually Balance is last

                df = table[[date_col_name, details_col_name, amount_col_name, balance_col_name]].copy()
                df.columns = ['Date', 'Details', 'Amount_Str', 'Balance_Str']
                
                df = df.dropna(subset=['Date'])
                
                df['Amount'] = df['Amount_Str'].astype(str).apply(clean_sa_amount)
                
                # Split amount into Credit/Debit
                df['Credit'] = df['Amount'].apply(lambda x: abs(x) if x > 0 else 0.0)
                df['Debit'] = df['Amount'].apply(lambda x: abs(x) if x < 0 else 0.0)
                
                df['Balance'] = df['Balance_Str'].astype(str).apply(clean_sa_amount)

                # Standardize Date
                df['Date'] = df['Date'].astype(str).apply(lambda x: standardize_date(x, statement_year))
                
                df_transactions = pd.concat([df_transactions, df], ignore_index=True)

            except Exception as e:
                print(f"Error processing FNB table: {e}")
                continue


        # Sort transactions by date
        df_transactions = df_transactions.dropna(subset=['Date'])
        # Drop rows where the date could not be parsed (e.g., header rows that sneaked in)
        df_transactions = df_transactions[df_transactions['Date'] != '']
        
        df_transactions['SortDate'] = pd.to_datetime(df_transactions['Date'], errors='coerce')
        df_transactions = df_transactions.sort_values('SortDate')
        df_transactions = df_transactions.drop(columns=['SortDate'])
        
        return create_final_csv_content(
            account_number=account_number,
            opening_balance=opening_balance,
            period=period,
            df=df_transactions
        )
        
    except Exception as e:
        print(f"Error processing FNB statement: {str(e)}")
        raise Exception(f"Failed to process FNB statement. Please ensure the PDF is not an image scan: {str(e)}")


def process_absa_statement(pdf_path: Path) -> str:
    """
    Process ABSA bank statements using a flexible stream-based approach to handle 
    broken column lines and stitching the multi-column description fields.
    """
    print("Processing ABSA statement with V3 logic...")
    
    try:
        # --- Metadata Extraction ---
        with pdfplumber.open(pdf_path) as pdf:
            text = pdf.pages[0].extract_text()
            
            account_match = re.search(r'Cheque Account Number:\s*([\d-]+)', text, re.IGNORECASE)
            account_number = account_match.group(1).replace('-', '') if account_match else 'N/A'
            
            # The balance can be e.g., '167,88-'
            balance_match = re.search(r'Balance Brought Forward\s*R?\s*([\d,.]+)(-)?', text, re.IGNORECASE)
            balance_str = f"{balance_match.group(1)}{balance_match.group(2) or ''}" if balance_match else '0,00'
            opening_balance = clean_sa_amount(balance_str)
            
            period_match = re.search(r'Cheque account statement\s*(\d{1,2}\s+[A-Za-z]{3}\s+\d{4}\s+to\s+\d{1,2}\s+[A-Za-z]{3}\s+\d{4})', text, re.IGNORECASE)
            period = period_match.group(1) if period_match else 'N/A'
            
            year_match = re.search(r'to\s+\d{1,2}\s+[A-Za-z]{3}\s+(\d{4})', period)
            statement_year = int(year_match.group(1)) if year_match else datetime.now().year

        # --- Transaction Extraction ---
        # Use stream=True (and lattice=False) for better handling of broken column lines
        # This is the key change that made the ABSA transactions appear
        tables = tabula.read_pdf(
            str(pdf_path),
            pages='all',
            multiple_tables=True,
            lattice=False, 
            stream=True, 
            guess=True,
            silent=True
        )
        
        df_transactions = pd.DataFrame(columns=['Date', 'Details', 'Debit', 'Credit', 'Balance'])
        
        for table in tables:
            # Drop rows where all values are NaN
            table = table.dropna(how='all')
            if table.empty or len(table.columns) < 4:
                continue

            try:
                # Rename all columns by index for predictable access
                original_cols = [str(col) for col in range(len(table.columns))]
                table.columns = original_cols
                
                # We expect columns: Date, [Details...], Amount, Balance
                
                # 1. Identify key columns by position (still the most reliable for fixed layouts)
                date_col = original_cols[0]
                amount_col = original_cols[-2] # Second to last column for the transaction amount
                balance_col = original_cols[-1] # Last column for the running balance
                
                # 2. Identify all columns between Date and Amount as Details columns
                details_cols = original_cols[1:-2]
                
                # Fallback for 4-column structure (Date, Details, Amount, Balance)
                if not details_cols:
                    details_cols = [original_cols[1]] 

                # 3. Combine Details columns first into a new 'Details' column
                table['Details_Combined'] = table[details_cols].astype(str).fillna('').agg(' '.join, axis=1).str.strip()
                
                # 4. Select the final 4 columns: Date, Details (newly created), Amount, Balance
                df = table[[date_col, 'Details_Combined', amount_col, balance_col]].copy()
                
                # 5. Rename to standard processing names
                df.columns = ['Date', 'Details', 'Amount_Str', 'Balance_Str']

                # 6. Drop rows where the Date is clearly missing or null
                df = df.dropna(subset=['Date'])
                
                # --- Advanced Transaction Filtering and Cleaning ---
                
                # Process Date first to identify valid transaction rows
                df['Date'] = df['Date'].astype(str).apply(lambda x: standardize_date(x, statement_year))
                
                # Filter out all rows where the date could not be parsed (likely headers, footers, or junk)
                df = df[df['Date'] != ''].copy()

                if df.empty:
                    continue
                
                # Process Amount
                df['Amount'] = df['Amount_Str'].astype(str).apply(clean_sa_amount)
                
                # Split amount into Credit/Debit
                df['Credit'] = df['Amount'].apply(lambda x: abs(x) if x > 0 else 0.0)
                df['Debit'] = df['Amount'].apply(lambda x: abs(x) if x < 0 else 0.0)
                
                # Process Balance column
                df['Balance'] = df['Balance_Str'].astype(str).apply(clean_sa_amount)

                # 10. Select required columns and concatenate
                final_cols = ['Date', 'Details', 'Debit', 'Credit', 'Balance']
                df_transactions = pd.concat([df_transactions, df[final_cols]], ignore_index=True)
            
            except Exception as e:
                # Detailed print for debugging, but hidden from final user error message
                print(f"Error processing ABSA table: {e}") 
                continue

        # Final cleanup and formatting
        df_transactions = df_transactions.dropna(subset=['Date'])
        # Drop rows where the date could not be parsed
        df_transactions = df_transactions[df_transactions['Date'] != '']
        
        df_transactions['SortDate'] = pd.to_datetime(df_transactions['Date'], errors='coerce')
        df_transactions = df_transactions.sort_values('SortDate').drop(columns=['SortDate'])

        return create_final_csv_content(account_number, opening_balance, period, df_transactions)
        
    except Exception as e:
        print(f"Error processing ABSA statement: {str(e)}")
        # Re-raise with a more generic error for the user
        raise Exception(f"Failed to process ABSA statement. This often happens if the PDF is an image scan. Error: {str(e)}")

def process_standard_statement(pdf_path: Path) -> str:
    """
    Process Standard Bank statements.
    
    Standard Bank uses a condensed table with Date as DD MM (e.g., '05 08' for 05 May).
    The column structure is: Details, Service Fee, Credits/Debits, Date, Balance.
    """
    print("Processing Standard Bank statement...")
    
    try:
        # --- Metadata Extraction ---
        with pdfplumber.open(pdf_path) as pdf:
            text = pdf.pages[0].extract_text()
            
            account_match = re.search(r'Account Number\s*([\d\s]+)', text, re.IGNORECASE)
            account_number = account_match.group(1).replace(' ', '') if account_match else 'N/A'
            
            # Opening Balance on the first page
            balance_match = re.search(r'OPENING BALANCE\s*R?\s*([\d,.]+)', text, re.IGNORECASE)
            opening_balance = clean_sa_amount(balance_match.group(1) if balance_match else '0,00')
            
            period_match = re.search(r'Statement from\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4}\s+to\s+\d{1,2}\s+[A-Za-z]+\s+\d{4})', text, re.IGNORECASE)
            period = period_match.group(1) if period_match else 'N/A'
            
            year_match = re.search(r'to\s+\d{1,2}\s+[A-Za-z]+\s+(\d{4})', period)
            statement_year = int(year_match.group(1)) if year_match else datetime.now().year

        # --- Transaction Extraction ---
        tables = tabula.read_pdf(
            str(pdf_path),
            pages='all',
            multiple_tables=True,
            lattice=True, # Standard Bank is usually a clean lattice grid
            guess=False, # We rely on explicit column knowledge
            silent=True
        )
        
        df_transactions = pd.DataFrame(columns=['Date', 'Details', 'Debit', 'Credit', 'Balance'])
        
        for table in tables:
            table = table.dropna(how='all')
            if len(table.columns) < 5:
                continue

            try:
                # The expected columns from the Standard Bank PDF snippet are:
                # Col 1: Details
                # Col 2: Service Fee (usually blank for transactions)
                # Col 3: Credits/Debits (Amount)
                # Col 4: Date (in DD MM format)
                # Col 5: Balance
                
                # Standardize column names by index for predictable access
                table.columns = [str(col) for col in range(len(table.columns))]

                # Select the required columns by index
                details_col = table.columns[0]
                amount_col = table.columns[2] # Credits/Debits column
                date_col = table.columns[3]    # Date column (DD MM format)
                balance_col = table.columns[4] # Balance column
                
                df = table[[date_col, details_col, amount_col, balance_col]].copy()
                df.columns = ['Date', 'Details', 'Amount_Str', 'Balance_Str']

            except Exception as e:
                # Fallback in case of structure changes
                print(f"Standard Bank table column error, skipping: {e}")
                continue


            df = df.dropna(subset=['Date'])
            
            # Drop the "OPENING BALANCE" row if it appears in the table data
            df = df[~df['Details'].astype(str).str.contains('OPENING BALANCE', case=False, na=False)].copy()
            
            # Process Amount
            df['Amount'] = df['Amount_Str'].astype(str).apply(clean_sa_amount)
            
            # Filter out non-transaction rows (e.g., table headers/footers)
            df = df[df['Amount'] != 0.0].copy()
            if df.empty:
                continue
            
            # Split amount into Credit/Debit
            df['Credit'] = df['Amount'].apply(lambda x: abs(x) if x > 0 else 0.0)
            df['Debit'] = df['Amount'].apply(lambda x: abs(x) if x < 0 else 0.0)
            
            # Process Balance
            df['Balance'] = df['Balance_Str'].apply(lambda x: clean_sa_amount(str(x)))

            # Standardize Date (using DD MM format e.g., '05 08')
            df['Date'] = df['Date'].astype(str).apply(lambda x: standardize_date(x, statement_year))
            
            df_transactions = pd.concat([df_transactions, df[['Date', 'Details', 'Debit', 'Credit', 'Balance']]], ignore_index=True)

        # Final cleanup and formatting
        df_transactions = df_transactions.dropna(subset=['Date'])
        df_transactions['SortDate'] = pd.to_datetime(df_transactions['Date'], errors='coerce')
        df_transactions = df_transactions.sort_values('SortDate').drop(columns=['SortDate'])
        
        return create_final_csv_content(account_number, opening_balance, period, df_transactions)
        
    except Exception as e:
        print(f"Error processing Standard Bank statement: {str(e)}")
        raise Exception(f"Failed to process Standard Bank statement. Please ensure the PDF is not an image scan: {str(e)}")


def process_capitec_statement(pdf_path: Path) -> str:
    """
    Process Capitec bank statements.
    """
    try:
        # --- Metadata Extraction ---
        with pdfplumber.open(pdf_path) as pdf:
            text = pdf.pages[0].extract_text()
            
            # Extract account number: looks for a long digit string near 'Account' or 'Tax Invoice'
            account_match = re.search(r'(?:Account|Tax Invoice)\s*(\d{8,15})', text, re.IGNORECASE)
            account_number = account_match.group(1).strip() if account_match else 'N/A'
            
            # Extract opening balance
            balance_match = re.search(r'Opening Balance:\s*R?\s*([\d,\.]+)', text, re.IGNORECASE)
            opening_balance = clean_sa_amount(balance_match.group(1) if balance_match else '0.00')

            # Extract period (Look for date ranges, handles multiline extraction from pdfplumber)
            period_match = re.search(r'From Date:\s*([\d\/]+\s*To Date:\s*[\d\/]+)', text.replace('\n', ' '), re.IGNORECASE)
            if period_match:
                period_raw = period_match.group(1).replace('From Date:', '').replace('To Date:', ' to ').replace('/', '-')
                period = period_raw.strip()
            else:
                period_match_alt = re.search(r'Statement period:?\s*(\d{1,2}\s+[A-Za-z]+\s+\d{4}\s+to\s+\d{1,2}\s+[A-Za-z]+\s+\d{4})', text, re.IGNORECASE)
                period = period_match_alt.group(1) if period_match_alt else 'N/A'
            
            # Determine statement year
            year_match = re.search(r'(\d{4})', period.rsplit(' ', 1)[-1]) if period != 'N/A' and 'to' in period else None
            statement_year = int(year_match.group(1)) if year_match else datetime.now().year
        
        # --- Transaction Extraction ---
        # Extract tables with specific settings for Capitec format
        tables = tabula.read_pdf(
            str(pdf_path),
            pages='all',
            multiple_tables=True,
            guess=True, # Allow guessing, but we will fix column mapping manually
            silent=True
        )
        
        columns = ['Date', 'Details', 'Debit', 'Credit', 'Balance']
        df_transactions = pd.DataFrame(columns=columns)
        
        
        # Process each table
        for table in tables:
            table = table.dropna(how='all')
            if table.empty or len(table.columns) < 3:
                continue

            # Capitec columns are inconsistent, but Date is usually the first, 
            # Details the second, and Amount/Balance are the last two.
            try:
                # Rename the columns based on index
                table.columns = [str(col) for col in range(len(table.columns))]
                
                # We need the Date (0), Details (1), Amount (N-1), and Balance (N)
                col_indices = [
                    table.columns[0],  # Date (Index 0)
                    table.columns[1],  # Details (Index 1)
                    table.columns[-2], # Amount (Second to last index)
                    table.columns[-1]  # Balance (Last index)
                ]

                df = table[col_indices].copy()
                df.columns = ['Date', 'Details', 'Amount_Str', 'Balance_Str']

                df = df.dropna(subset=['Date'])
                
                # Process Amount
                df['Amount'] = df['Amount_Str'].astype(str).apply(clean_sa_amount)
                
                # Split amount into Credit/Debit based on sign
                df['Credit'] = df['Amount'].apply(lambda x: abs(x) if x > 0 else 0.0)
                df['Debit'] = df['Amount'].apply(lambda x: abs(x) if x < 0 else 0.0)
                
                # Process Balance
                df['Balance'] = df['Balance_Str'].apply(lambda x: clean_sa_amount(str(x)))

                # Standardize Date
                df['Date'] = df['Date'].astype(str).apply(lambda x: standardize_date(x, statement_year))
                
                # Ensure Details is clean
                df['Details'] = df['Details'].astype(str).str.strip()
                
                # Select only the required columns before concatenation
                final_cols = ['Date', 'Details', 'Debit', 'Credit', 'Balance']
                df_transactions = pd.concat([df_transactions, df[final_cols]], ignore_index=True)
                
            except Exception as e:
                print(f"Error processing Capitec table: {e}")
                continue
        
        # Final cleanup and formatting
        df_transactions = df_transactions.dropna(subset=['Date'])
        df_transactions['SortDate'] = pd.to_datetime(df_transactions['Date'], errors='coerce')
        df_transactions = df_transactions.sort_values('SortDate').drop(columns=['SortDate'])
        
        return create_final_csv_content(
            account_number=account_number,
            opening_balance=opening_balance,
            period=period,
            df=df_transactions
        )
        
    except Exception as e:
        raise Exception(f"Failed to process Capitec statement: {str(e)}")


# --- Flask Routes (UPDATED) ---

@app.route('/')
def index():
    """Renders the main upload page with bank selection options."""
    # Define the available bank options to be passed to the template
    bank_options = [
        ('CAPITEC', 'Capitec Bank'),
        ('FNB', 'First National Bank (FNB)'),
        ('ABSA', 'ABSA Bank'),
        ('STANDARD', 'Standard Bank'), 
    ]
    # Pass the bank options to the index.html template
    return render_template('index.html', bank_options=bank_options)

@app.route('/upload', methods=['POST'])
def upload():
    """Handles PDF upload, processes it based on bank type, and triggers download."""
    try:
        if 'pdf' not in request.files:
            flash('No file uploaded', 'error')
            return redirect(url_for('index'))
            
        file = request.files['pdf']
        # Retrieve the selected bank type from the form
        bank_type = request.form.get('bank_type')
        
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(url_for('index'))
            
        if not file.filename.lower().endswith('.pdf'):
            flash('Only PDF files are allowed', 'error')
            return redirect(url_for('index'))
            
        if not bank_type:
            flash('Please select a bank', 'error')
            return redirect(url_for('index'))
            
        # Check for supported banks explicitly
        supported_banks = ['CAPITEC', 'FNB', 'ABSA', 'STANDARD']
        if bank_type not in supported_banks:
            flash(f'Unsupported bank selected: {bank_type}', 'error')
            return redirect(url_for('index'))
        
        # Create unique filename and path
        filename = f"{uuid.uuid4()}_{secure_filename(file.filename)}"
        pdf_path = UPLOADS / filename
        
        # Save uploaded file
        file.save(pdf_path)
        
        try:
            # Process based on selected bank
            csv_content = process_bank_statement_to_csv(pdf_path, bank_type)
            
            # Generate output filename
            out_name = f"processed_{filename.rsplit('.', 1)[0]}.csv"
            out_path = OUTPUTS / out_name
            
            # Write CSV content
            with open(out_path, 'w', encoding='utf-8') as f:
                f.write(csv_content)
            
            # Cleanup uploaded PDF
            pdf_path.unlink(missing_ok=True)
            
            return redirect(url_for('download', filename=out_name))
            
        except Exception as e:
            if pdf_path.exists():
                pdf_path.unlink(missing_ok=True)
            # Ensure the error message is user-friendly
            error_message = str(e) if 'Failed to process' in str(e) else f'Error processing file. Ensure the PDF is clearly legible: {str(e)}'
            flash(error_message, 'error')
            return redirect(url_for('index'))
            
    except Exception as e:
        flash(f'Upload error: {str(e)}', 'error')
        return redirect(url_for('index'))

@app.route('/download/<filename>')
def download(filename):
    """Sends the processed CSV file for download."""
    try:
        return send_from_directory(OUTPUTS, filename, as_attachment=True)
    except Exception as e:
        flash(f'Error downloading file: {str(e)}')
        return redirect(url_for('index'))

@app.route('/health')
def health_check():
    return jsonify({"status": "healthy"}), 200
