# Import the required Module
import pandas as pd
import os
import re
from datetime import datetime

# Try to import and test tabula
TABULA_AVAILABLE = False
try:
    import tabula
    # Test if Java is actually available
    test_result = None
    try:
        # Try a simple tabula operation to test Java
        import tempfile
        # This will fail immediately if Java is not available
        os.environ["TABULA_JAVA"] = "subprocess"
        TABULA_AVAILABLE = True
        print("✅ Tabula-py with Java is available")
    except Exception as java_error:
        print(f"❌ Java not available for tabula: {java_error}")
        TABULA_AVAILABLE = False
except ImportError as import_error:
    print(f"❌ Tabula-py not installed: {import_error}")
    TABULA_AVAILABLE = False

# Import pdfplumber as backup
try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
    print("✅ PDFplumber is available")
except ImportError:
    PDFPLUMBER_AVAILABLE = False
    print("❌ PDFplumber not available")

def extract_tables_from_pdf(pdf_path):
    """Extract tables from PDF using available method"""
    print(f"Processing PDF: {pdf_path}")
    print(f"Tabula available: {TABULA_AVAILABLE}, PDFplumber available: {PDFPLUMBER_AVAILABLE}")
    
    # Force use of pdfplumber on Render (where Java might not be available)
    if os.environ.get('RENDER'):
        print("Running on Render - using PDFplumber")
        if PDFPLUMBER_AVAILABLE:
            return extract_with_pdfplumber(pdf_path)
        else:
            raise Exception("No PDF processing method available on Render")
    
    # For local development, try tabula first if Java is available
    if TABULA_AVAILABLE:
        try:
            print("Trying tabula-py...")
            return tabula.read_pdf(pdf_path, pages='all', multiple_tables=True, lattice=True, pandas_options={'header': None})
        except Exception as e:
            print(f"Tabula failed: {e}")
            if PDFPLUMBER_AVAILABLE:
                print("Falling back to PDFplumber...")
                return extract_with_pdfplumber(pdf_path)
            else:
                raise Exception(f"Tabula failed and no backup available: {e}")
    elif PDFPLUMBER_AVAILABLE:
        print("Using PDFplumber...")
        return extract_with_pdfplumber(pdf_path)
    else:
        raise Exception("No PDF processing library available")

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
    
    # Remove any whitespace and common formatting
    amount_str = re.sub(r'\s+', '', amount_str)
    
    # Handle negative amounts in parentheses
    if amount_str.startswith('(') and amount_str.endswith(')'):
        amount_str = '-' + amount_str[1:-1]
    
    # Remove currency symbols and commas
    amount_str = re.sub(r'[R$€£¥,]', '', amount_str)
    
    # Extract numeric value
    match = re.search(r'-?\d+\.?\d*', amount_str)
    if match:
        try:
            return float(match.group())
        except ValueError:
            return None
    return None

def detect_bank_type(df_list):
    """Detect bank type from the extracted data"""
    all_text = ""
    for df in df_list:
        all_text += df.to_string().lower()
    
    if 'fnb' in all_text or 'first national' in all_text:
        return 'fnb'
    elif 'standard bank' in all_text or 'standard' in all_text:
        return 'standard'
    elif 'absa' in all_text:
        return 'absa'
    else:
        return 'unknown'

def extract_transaction_data(df_list, bank_type="auto"):
    """Extract and clean transaction data from the PDF data"""
    print(f"Extracting transaction data for {len(df_list)} tables")
    
    if bank_type == "auto":
        bank_type = detect_bank_type(df_list)
        print(f"Detected bank type: {bank_type}")
    
    all_transactions = []
    
    for i, df in enumerate(df_list):
        print(f"Processing table {i + 1}/{len(df_list)}")
        
        if df.empty:
            continue
            
        # Convert all columns to string for easier processing
        df = df.astype(str)
        
        # Look for date patterns in each row
        for idx, row in df.iterrows():
            row_text = ' '.join(row.values)
            
            # Look for date pattern
            date_match = re.search(r'(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4})', row_text)
            if date_match:
                date_str = date_match.group(1)
                
                # Extract description (text between date and amount)
                description_match = re.search(r'\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\s+(.+?)\s+[\d\-\.,]+\s*$', row_text)
                description = description_match.group(1).strip() if description_match else "Unknown Transaction"
                
                # Extract amount (last number in the row)
                amounts = re.findall(r'[\d\-\.,]+', row_text)
                amount = None
                if amounts:
                    for amt in reversed(amounts):  # Check from the end
                        cleaned_amt = clean_amount(amt)
                        if cleaned_amt is not None:
                            amount = cleaned_amt
                            break
                
                if amount is not None:
                    # Categorize transaction
                    category = categorize_transaction(description)
                    
                    all_transactions.append({
                        'Date': date_str,
                        'Description': description,
                        'Category': category,
                        'Amount': amount,
                        'Balance': '',  # We'll calculate running balance if needed
                        'Bank': bank_type.upper()
                    })
    
    print(f"Extracted {len(all_transactions)} transactions")
    
    if not all_transactions:
        # If no transactions found, create a sample row to show the structure
        all_transactions.append({
            'Date': 'No transactions found',
            'Description': 'Please check the PDF format',
            'Category': 'Error',
            'Amount': 0.0,
            'Balance': '',
            'Bank': bank_type.upper()
        })
    
    return pd.DataFrame(all_transactions)

def categorize_transaction(description):
    """Categorize transaction based on description"""
    description_lower = description.lower()
    
    # Define categories and their keywords
    categories = {
        'Groceries': ['woolworths', 'pick n pay', 'checkers', 'spar', 'shoprite', 'makro'],
        'Fuel': ['shell', 'bp', 'sasol', 'engen', 'total', 'fuel'],
        'Banking': ['bank charge', 'atm', 'card fee', 'service fee', 'monthly fee'],
        'Utilities': ['electricity', 'water', 'municipal', 'rates', 'eskom'],
        'Insurance': ['insurance', 'assurance', 'cover', 'premium'],
        'Investment': ['investment', 'unit trust', 'shares', 'dividend'],
        'Transfer': ['transfer', 'payment', 'eft', 'online'],
        'Cash': ['cash withdrawal', 'atm withdrawal', 'cash'],
        'Debit Order': ['debit order', 'stop order', 'recurring'],
        'Salary': ['salary', 'wages', 'income', 'remuneration'],
        'Interest': ['interest', 'credit interest']
    }
    
    for category, keywords in categories.items():
        if any(keyword in description_lower for keyword in keywords):
            return category
    
    return 'Other'

def process_pdf_to_clean_csv(pdf_path, csv_path, bank_type="auto"):
    """Convert PDF to properly structured CSV"""
    try:
        print(f"Processing PDF: {pdf_path}")
        print(f"Bank Type: {bank_type}")
        
        # Read PDF file using subprocess mode
        df_list = tabula.read_pdf(pdf_path, pages='all', force_subprocess=True)
        
        print(f"Extracted {len(df_list)} tables from PDF")
        
        # Extract and clean transaction data
        transactions = extract_transaction_data(df_list, bank_type)
        
        print(f"Found {len(transactions)} transactions")
        
        if not transactions:
            print("No transactions found!")
            return
        
        # Create DataFrame with proper structure
        df = pd.DataFrame(transactions)
        
        # Sort by date
        try:
            df['Date'] = pd.to_datetime(df['Date'], format='%d/%m/%Y', errors='coerce')
            df = df.sort_values('Date')
            df['Date'] = df['Date'].dt.strftime('%d/%m/%Y')
        except Exception as e:
            print(f"Date sorting failed: {e}")
            pass
        
        # Remove duplicates
        df = df.drop_duplicates()
        
        # Save to CSV with proper formatting
        df.to_csv(csv_path, index=False)
        
        print(f"✅ Successfully created clean CSV: {csv_path}")
        print(f"📊 Total transactions: {len(df)}")
        print("\n📋 Sample of cleaned data:")
        print(df.head(10).to_string(index=False))
        
        return len(df)
        
    except Exception as e:
        print(f"❌ Error processing PDF: {str(e)}")
        raise

# Main execution
if __name__ == "__main__":
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Test with FNB
    fnb_path = os.path.join(script_dir, "FNB.pdf")
    fnb_csv = os.path.join(script_dir, "FNB_cleaned.csv")
    
    if os.path.exists(fnb_path):
        print("=== Testing FNB Statement ===")
        process_pdf_to_clean_csv(fnb_path, fnb_csv, "fnb")
    
    # Test with Standard Bank (original)
    standard_path = os.path.join(script_dir, "account_statement (2) (2).pdf")
    standard_csv = os.path.join(script_dir, "account_statement_cleaned.csv")
    
    if os.path.exists(standard_path):
        print("\n=== Testing Standard Bank Statement ===")
        process_pdf_to_clean_csv(standard_path, standard_csv, "standard bank")
