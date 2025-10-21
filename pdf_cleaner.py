# Import the required Module - JAVA-FREE VERSION
import pandas as pd
import os
import re
from datetime import datetime

# Only import pdfplumber - no Java required
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
    print("✅ PDFplumber is available (no Java required)")
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    print("❌ PDFplumber not available - please install: pip install pdfplumber")

def extract_tables_from_pdf(pdf_path):
    """Extract tables from PDF using PDFplumber only - NO JAVA REQUIRED"""
    print(f"Processing PDF: {pdf_path}")
    
    if not PDFPLUMBER_AVAILABLE:
        raise Exception("PDFplumber not available. Please install: pip install pdfplumber")
    
    print("Using PDFplumber (no Java required)...")
    return extract_with_pdfplumber(pdf_path)

def extract_with_pdfplumber(pdf_path):
    """Extract data from PDF using pdfplumber (no Java required)"""
    print("Using PDFplumber to extract data...")
    all_tables = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                print(f"Processing page {page_num + 1}")
                
                # Extract tables from the page
                tables = page.extract_tables()
                for table in tables:
                    if table and len(table) > 1:  # If table has data
                        # Convert to DataFrame
                        df = pd.DataFrame(table[1:], columns=table[0] if table[0] else None)
                        if not df.empty:
                            all_tables.append(df)
                
                # Extract text and parse for transactions
                text = page.extract_text()
                if text:
                    # Split text into lines and look for transaction patterns
                    lines = text.split('\n')
                    transaction_rows = []
                    
                    for line in lines:
                        # Look for date patterns (DD/MM/YYYY or DD-MM-YYYY)
                        date_match = re.search(r'\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}', line)
                        # Look for amount patterns (numbers with 2 decimal places)
                        amount_match = re.search(r'\d+\.\d{2}', line)
                        
                        if date_match and amount_match:
                            # Split the line and try to extract structured data
                            parts = re.split(r'\s{2,}', line.strip())  # Split on multiple spaces
                            if len(parts) >= 3:  # Date, description, amount
                                transaction_rows.append(parts)
                    
                    if transaction_rows:
                        # Create DataFrame from extracted transactions
                        max_cols = max(len(row) for row in transaction_rows)
                        # Pad rows to have the same number of columns
                        padded_rows = [row + [''] * (max_cols - len(row)) for row in transaction_rows]
                        df = pd.DataFrame(padded_rows)
                        if not df.empty:
                            all_tables.append(df)
        
        print(f"Extracted {len(all_tables)} tables using PDFplumber")
        return all_tables
        
    except Exception as e:
        print(f"PDFplumber extraction failed: {e}")
        raise Exception(f"Failed to extract data with PDFplumber: {e}")

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

def clean_date(date_str):
    """Clean and standardize date format"""
    if pd.isna(date_str) or date_str == '':
        return None
    
    date_str = str(date_str).strip()
    
    # Handle FNB format "13 Dec" - assume current year or previous year
    month_names = {
        'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04', 'May': '05', 'Jun': '06',
        'Jul': '07', 'Aug': '08', 'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
    }
    
    # Try FNB format: "13 Dec"
    fnb_match = re.search(r'(\d{1,2})\s+(\w{3})', date_str)
    if fnb_match:
        day = fnb_match.group(1).zfill(2)
        month_abbr = fnb_match.group(2)
        if month_abbr in month_names:
            month = month_names[month_abbr]
            # Use 2024 as default year for FNB statements
            return f"{day}/{month}/2024"
    
    # Remove any non-date characters at the beginning
    date_str = re.sub(r'^[^\d/]*', '', date_str)
    
    # Extract date pattern (dd/mm/yyyy or d/mm/yyyy)
    date_match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', date_str)
    if date_match:
        return date_match.group(1)
    
    return None

def extract_universal_transactions(df_list):
    """Universal transaction extractor that works with most bank formats"""
    all_transactions = []
    
    for df in df_list:
        # Convert all columns to string for processing
        df = df.astype(str)
        
        # Check if this looks like a proper transaction table
        # Look for date patterns in columns or data
        has_date_data = False
        
        # Check column names for dates
        date_columns = []
        for col in df.columns:
            if re.search(r'\d{1,2}/\d{1,2}/\d{4}', str(col)):
                date_columns.append(col)
                has_date_data = True
        
        # If we have date columns, process them differently
        if date_columns:
            # This is likely a table where dates are column headers
            for col in date_columns:
                col_data = df[col].dropna()
                for idx, value in col_data.items():
                    value_str = str(value)
                    if value_str != 'nan' and len(value_str) > 2:
                        # Extract description and amount from the value
                        # Look for description patterns
                        desc_match = re.search(r'^([A-Za-z][A-Za-z\s]*)', value_str)
                        description = desc_match.group(1).strip() if desc_match else value_str[:20]
                        
                        # Look for amounts
                        amounts = re.findall(r'[-+]?[R]?[\d,]+\.?\d*', value_str)
                        cleaned_amounts = []
                        for amount in amounts:
                            cleaned = clean_amount(amount)
                            if cleaned is not None:
                                cleaned_amounts.append(cleaned)
                        
                        money_in = None
                        money_out = None
                        
                        if cleaned_amounts:
                            if cleaned_amounts[0] < 0:
                                money_out = abs(cleaned_amounts[0])
                            else:
                                money_in = cleaned_amounts[0]
                        
                        if description and (money_in or money_out):
                            all_transactions.append({
                                'Date': col,
                                'Description': description,
                                'Category': categorize_transaction(description),
                                'Money In': money_in,
                                'Money Out': money_out,
                                'Fee*': None,
                                'Balance': None
                            })
        
        # Also check for rows with date patterns
        for index, row in df.iterrows():
            row_cells = [str(cell).strip() for cell in row if str(cell) != 'nan' and str(cell).strip() != '']
            if not row_cells:
                continue
                
            row_text = ' '.join(row_cells)
            
            # Skip header-like rows but be less restrictive
            if len(row_text) < 8:
                continue
                
            # Look for date patterns
            date_patterns = [
                r'(\d{1,2}/\d{1,2}/\d{4})',     # dd/mm/yyyy
                r'(\d{4}/\d{1,2}/\d{1,2})',     # yyyy/mm/dd
                r'(\d{1,2}\s+\w{3})',           # dd Mon (FNB format)
                r'(\d{1,2}-\d{1,2}-\d{4})',     # dd-mm-yyyy
            ]
            
            date = None
            for pattern in date_patterns:
                date_match = re.search(pattern, row_text)
                if date_match:
                    raw_date = date_match.group(1)
                    date = clean_date(raw_date)
                    if date:
                        break
            
            if not date:
                continue
            
            # Extract description
            description = ''
            
            # Method 1: Look for text between date and amount
            after_date = re.split(r'\d{1,2}[/\-]\d{1,2}[/\-]\d{4}|\d{4}[/\-]\d{1,2}[/\-]\d{1,2}|\d{1,2}\s+\w{3}', row_text)
            if len(after_date) > 1:
                desc_part = after_date[1].strip()
                # Find description before first amount
                parts = desc_part.split()
                desc_words = []
                for word in parts:
                    # Stop at first amount-like word
                    if re.match(r'^[-+]?[R]?[\d,]+', word) or re.match(r'^\d+\.\d+', word):
                        break
                    if re.match(r'^[A-Za-z]', word):  # Keep alphabetic words
                        desc_words.append(word)
                description = ' '.join(desc_words)
            
            # Method 2: If no description found, try to extract from row cells
            if not description:
                for cell in row_cells:
                    if len(cell) > 3 and re.match(r'^[A-Za-z]', cell) and not re.search(r'\d', cell):
                        description = cell
                        break
            
            # Clean description
            description = re.sub(r'\s+', ' ', description).strip()
            
            # Extract amounts
            amounts = re.findall(r'[-+]?[R]?[\d,]+\.?\d*', row_text)
            
            cleaned_amounts = []
            for amount in amounts:
                cleaned = clean_amount(amount)
                if cleaned is not None and abs(cleaned) > 0.01:
                    cleaned_amounts.append(cleaned)
            
            money_in = None
            money_out = None
            balance = None
            
            if cleaned_amounts:
                # Simple logic: negative = out, positive = in
                for amount in cleaned_amounts:
                    if amount < 0:
                        money_out = abs(amount)
                    else:
                        money_in = amount
                        
                # Last amount could be balance
                if len(cleaned_amounts) > 1:
                    balance = cleaned_amounts[-1]
            
            # Only add if we have meaningful data
            if date and description and len(description) > 1:
                category = categorize_transaction(description)
                
                all_transactions.append({
                    'Date': date,
                    'Description': description,
                    'Category': category,
                    'Money In': money_in,
                    'Money Out': money_out,
                    'Fee*': None,
                    'Balance': balance
                })
    
    return all_transactions

def categorize_transaction(description):
    """Categorize transactions based on description"""
    category_patterns = {
        'Cash Deposit': ['Cash Deposit', 'ATM Cash Deposit'],
        'Groceries': ['Shoprite', 'Pick n Pay', 'Checkers', 'Boxer', 'Woolworths', 'Spar'],
        'Fuel': ['Shell', 'BP', 'Engen', 'Sasol', 'Caltex'],
        'Clothing & Shoes': ['Clothing', 'Pick n Pay Clothing', 'Pep Stores', 'Mr Price', 'Edgars'],
        'Betting/Lottery': ['Lotto', 'PowerBall', 'Daily Lotto', 'Betway', 'Betting'],
        'Cellphone': ['VODACOM', 'MTN', 'Cell C', 'Telkom Mobile', 'Airtime'],
        'Digital Payments': ['Banking App', 'Immediate Payment', 'EFT', 'Online Payment'],
        'Fees': ['SMS Notification', 'Admin Fee', 'Transaction Fee', 'Service Fee'],
        'Personal Care': ['Clicks', 'Dis-Chem', 'Pharmacy'],
        'Home Improvements': ['BUCO', 'Builders', 'Hardware'],
        'Funeral Cover': ['Capfuneral', 'Funeral'],
        'Savings': ['Stash By Liberty', 'Investment', 'Savings'],
        'Transfer': ['Transfer', 'Round-up'],
        'Other Income': ['Payment Received', 'Salary', 'Income']
    }
    
    for cat, patterns in category_patterns.items():
        if any(pattern.lower() in description.lower() for pattern in patterns):
            return cat
    
    return 'Uncategorised'

def extract_transaction_data(df_list, bank_type="auto"):
    """Extract and clean transaction data based on bank type - JAVA-FREE VERSION"""
    print(f"Extracting transaction data for {len(df_list)} tables")
    
    # Use universal extractor for all banks (works better with PDFplumber)
    transactions = extract_universal_transactions(df_list)
    
    # Convert to DataFrame
    df = pd.DataFrame(transactions)
    
    print(f"Extracted {len(df)} transactions")
    
    if df.empty:
        # If no transactions found, create a sample row to show the structure
        df = pd.DataFrame([{
            'Date': 'No transactions found',
            'Description': 'Please check the PDF format',
            'Category': 'Error',
            'Money In': 0.0,
            'Money Out': 0.0,
            'Fee*': None,
            'Balance': None
        }])
    
    return df

def process_pdf_to_clean_csv(pdf_path, csv_path, bank_type="auto"):
    """Convert PDF to properly structured CSV - JAVA-FREE VERSION"""
    try:
        print(f"Processing PDF: {pdf_path}")
        print(f"Bank Type: {bank_type}")
        
        # Use PDFplumber instead of tabula (no Java required)
        df_list = extract_tables_from_pdf(pdf_path)
        
        print(f"Extracted {len(df_list)} tables from PDF")
        
        # Extract and clean transaction data
        transactions = extract_transaction_data(df_list, bank_type)
        
        print(f"Found {len(transactions)} transactions")
        
        if transactions.empty:
            print("No transactions found!")
            return 0
        
        # Sort by date
        try:
            transactions['Date'] = pd.to_datetime(transactions['Date'], format='%d/%m/%Y', errors='coerce')
            transactions = transactions.sort_values('Date')
            transactions['Date'] = transactions['Date'].dt.strftime('%d/%m/%Y')
        except Exception as e:
            print(f"Date sorting failed: {e}")
            pass
        
        # Remove duplicates
        transactions = transactions.drop_duplicates()
        
        # Save to CSV with proper formatting
        transactions.to_csv(csv_path, index=False)
        
        print(f"✅ Successfully created clean CSV: {csv_path}")
        print(f"📊 Total transactions: {len(transactions)}")
        print("\n📋 Sample of cleaned data:")
        print(transactions.head(10).to_string(index=False))
        
        return len(transactions)
        
    except Exception as e:
        print(f"❌ Error processing PDF: {str(e)}")
        raise

# Test function for local development only - JAVA-FREE
if __name__ == "__main__":
    print("PDF Cleaner - Java-free PDF processing")
    print("This module uses PDFplumber instead of tabula for PDF processing")
    print("No Java installation required!")
