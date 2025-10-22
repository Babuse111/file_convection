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
    """Extract tables from PDF using PDFplumber only - Enhanced for ABSA format"""
    print(f"Processing PDF: {pdf_path}")
    
    if not PDFPLUMBER_AVAILABLE:
        raise Exception("PDFplumber not available. Please install: pip install pdfplumber")
    
    print("Using PDFplumber (no Java required)...")
    return extract_with_pdfplumber_enhanced(pdf_path)

def extract_with_pdfplumber_enhanced(pdf_path):
    """Enhanced PDFplumber extraction - works better with ABSA format"""
    print("Using enhanced PDFplumber extraction...")
    all_tables = []
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages):
                print(f"Processing page {page_num + 1}")
                
                # Method 1: Try to extract structured tables
                tables = page.extract_tables()
                print(f"  Found {len(tables)} structured tables on page {page_num + 1}")
                
                for table in tables:
                    if table and len(table) > 1:  # If table has data
                        # Convert to DataFrame
                        df = pd.DataFrame(table[1:], columns=table[0] if table[0] else None)
                        if not df.empty:
                            print(f"    Added table with shape: {df.shape}")
                            all_tables.append(df)
                
                # Method 2: Extract text and create tables from transaction patterns
                text = page.extract_text()
                if text:
                    print(f"  Extracting text-based transactions from page {page_num + 1}")
                    text_based_df = extract_transactions_from_text(text, page_num + 1)
                    if not text_based_df.empty:
                        print(f"    Added text-based table with shape: {text_based_df.shape}")
                        all_tables.append(text_based_df)
                
                # Method 3: Try different table extraction settings for ABSA
                if not tables:  # If no tables found with default settings
                    print(f"  Trying alternative table extraction for page {page_num + 1}")
                    
                    # Try with different table settings
                    alt_tables = page.extract_tables(table_settings={
                        "vertical_strategy": "lines_strict",
                        "horizontal_strategy": "lines_strict",
                        "min_words_vertical": 1,
                        "min_words_horizontal": 1
                    })
                    
                    for table in alt_tables:
                        if table and len(table) > 0:
                            df = pd.DataFrame(table)
                            if not df.empty:
                                print(f"    Added alternative table with shape: {df.shape}")
                                all_tables.append(df)
        
        print(f"Total extracted tables: {len(all_tables)}")
        
        # If still no tables found, create a basic structure from text
        if not all_tables:
            print("No structured tables found, creating basic text-based extraction")
            basic_df = create_basic_transaction_table(pdf_path)
            if not basic_df.empty:
                all_tables.append(basic_df)
        
        return all_tables
        
    except Exception as e:
        print(f"PDFplumber extraction failed: {e}")
        raise Exception(f"Failed to extract data with PDFplumber: {e}")

def extract_transactions_from_text(text, page_num):
    """Extract transactions from plain text - works well for ABSA format"""
    print(f"    Parsing text for transactions on page {page_num}")
    
    lines = text.split('\n')
    transaction_rows = []
    
    for line in lines:
        line = line.strip()
        if len(line) < 10:  # Skip very short lines
            continue
            
        # Enhanced date patterns for different formats
        date_patterns = [
            r'(\d{1,2}/\d{1,2}/\d{4})',     # dd/mm/yyyy
            r'(\d{4}/\d{1,2}/\d{1,2})',     # yyyy/mm/dd
            r'(\d{1,2}-\d{1,2}-\d{4})',     # dd-mm-yyyy
            r'(\d{1,2}\s+\w{3}\s+\d{4})',   # dd Mon yyyy
            r'(\d{1,2}\s+\w{3})',           # dd Mon (current year)
        ]
        
        # Enhanced amount patterns
        amount_patterns = [
            r'(R\s*\d+[\d,]*\.?\d*)',       # R123.45 or R1,234.56
            r'(\d+[\d,]*\.\d{2})',          # 123.45 or 1,234.56
            r'(\d+\.\d{2})',                # Simple 123.45
        ]
        
        date_found = None
        for pattern in date_patterns:
            date_match = re.search(pattern, line)
            if date_match:
                date_found = date_match.group(1)
                break
        
        amount_found = None
        for pattern in amount_patterns:
            amounts = re.findall(pattern, line)
            if amounts:
                amount_found = amounts[-1]  # Take the last amount found
                break
        
        if date_found and amount_found:
            # Extract description (text between date and amount)
            # Remove date and amount from line to get description
            desc_line = line
            desc_line = re.sub(r'\d{1,2}[/\-]\d{1,2}[/\-]\d{4}', '', desc_line)
            desc_line = re.sub(r'\d{4}[/\-]\d{1,2}[/\-]\d{1,2}', '', desc_line)
            desc_line = re.sub(r'\d{1,2}\s+\w{3}(\s+\d{4})?', '', desc_line)
            desc_line = re.sub(r'R\s*\d+[\d,]*\.?\d*', '', desc_line)
            desc_line = re.sub(r'\d+[\d,]*\.\d{2}', '', desc_line)
            desc_line = re.sub(r'\s+', ' ', desc_line).strip()
            
            if len(desc_line) > 2:  # Valid description
                # Split the line into components
                parts = [date_found, desc_line, amount_found]
                transaction_rows.append(parts)
    
    if transaction_rows:
        # Create DataFrame from extracted transactions
        df = pd.DataFrame(transaction_rows, columns=['Date', 'Description', 'Amount'])
        print(f"    Extracted {len(df)} transactions from text")
        return df
    
    return pd.DataFrame()

def create_basic_transaction_table(pdf_path):
    """Create a basic transaction table when no structured data is found"""
    print("Creating basic transaction structure from PDF text")
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            all_text = ""
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    all_text += page_text + "\n"
        
        # Look for any transaction-like patterns in the entire text
        lines = all_text.split('\n')
        transactions = []
        
        for line in lines:
            line = line.strip()
            if len(line) > 15:  # Reasonable line length
                # Look for lines that might be transactions
                if re.search(r'\d{1,2}[/\-]\d{1,2}[/\-]\d{4}', line) and re.search(r'\d+\.\d{2}', line):
                    # Extract components
                    date_match = re.search(r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{4})', line)
                    amount_matches = re.findall(r'(\d+\.\d{2})', line)
                    
                    if date_match and amount_matches:
                        date = date_match.group(1)
                        amount = amount_matches[-1]  # Last amount
                        
                        # Description is everything else
                        desc = line.replace(date, '').replace(amount, '')
                        desc = re.sub(r'\s+', ' ', desc).strip()
                        
                        if len(desc) > 2:
                            transactions.append({
                                'Date': date,
                                'Description': desc,
                                'Amount': amount
                            })
        
        if transactions:
            df = pd.DataFrame(transactions)
            print(f"Created basic table with {len(df)} transactions")
            return df
            
    except Exception as e:
        print(f"Basic extraction failed: {e}")
    
    return pd.DataFrame()

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
    """Extract and clean transaction data from the PDF data - Only Date, Description, Amount"""
    print(f"Extracting transaction data for {len(df_list)} tables")
    
    all_transactions = []
    
    for i, df in enumerate(df_list):
        print(f"Processing table {i + 1}/{len(df_list)} - Shape: {df.shape}")
        
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
                description_match = re.search(r'\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}\s+(.+?)\s+[\d\-\.,R]+\s*$', row_text)
                description = description_match.group(1).strip() if description_match else "Unknown Transaction"
                
                # Extract amount (first valid amount found)
                amounts = re.findall(r'[\d\-\.,]+', row_text)
                amount = None
                
                if amounts:
                    for amt in amounts:  # Check all amounts
                        cleaned_amt = clean_amount(amt)
                        if cleaned_amt is not None:
                            amount = cleaned_amt
                            break  # Take the first valid amount
                
                if amount is not None:
                    all_transactions.append({
                        'Date': date_str,
                        'Description': description,
                        'Amount': amount
                    })
    
    print(f"Extracted {len(all_transactions)} transactions")
    
    if not all_transactions:
        # If no transactions found, create a sample row to show the structure
        all_transactions.append({
            'Date': 'No transactions found',
            'Description': 'PDF format may not be supported',
            'Amount': 0.0
        })
    
    return pd.DataFrame(all_transactions)

def process_pdf(pdf_path):
    """Main function to process PDF and return transaction data"""
    print(f"Processing PDF: {pdf_path}")
    
    # Extract tables using PDFplumber
    df_list = extract_tables_from_pdf(pdf_path)
    
    if not df_list:
        raise Exception("No extraction method available or PDF could not be processed")
    
    # Extract transactions
    transactions_df = extract_transaction_data(df_list)
    
    # Convert DataFrame to list of dictionaries for consistency
    if isinstance(transactions_df, pd.DataFrame):
        transactions = transactions_df.to_dict('records')
    else:
        transactions = transactions_df
    
    if not transactions:
        # Create a basic structure if nothing found
        transactions = [{
            'Date': 'No data found',
            'Description': 'PDF format may not be supported',
            'Amount': 0.0
        }]
    
    return transactions

# Main execution
if __name__ == "__main__":
    # Get the directory where this script is located
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Test with FNB
    fnb_path = os.path.join(script_dir, "FNB.pdf")
    fnb_csv = os.path.join(script_dir, "FNB_cleaned.csv")
    
    if os.path.exists(fnb_path):
        print("=== Testing FNB Statement ===")
        transactions = process_pdf(fnb_path)
        
        # Create DataFrame and save
        df = pd.DataFrame(transactions)
        df.to_csv(fnb_csv, index=False)
        print(f"Saved {len(df)} transactions to {fnb_csv}")
    else:
        print("FNB.pdf not found in the script directory")
