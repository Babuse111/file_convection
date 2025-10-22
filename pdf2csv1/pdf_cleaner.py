# Import the required Module
import pandas as pd
import os
import re
from datetime import datetime

# Try both extraction methods
try:
    import tabula
    TABULA_AVAILABLE = True
    os.environ["TABULA_JAVA"] = "subprocess"
except ImportError:
    TABULA_AVAILABLE = False

try:
    import pdfplumber
    PDFPLUMBER_AVAILABLE = True
except ImportError:
    PDFPLUMBER_AVAILABLE = False

def clean_amount(amount_str):
    """Clean and convert amount strings to float"""
    if pd.isna(amount_str) or amount_str == '' or str(amount_str).lower() == 'nan':
        return None
    
    # Convert to string and clean
    amount_str = str(amount_str).strip()
    
    # Remove currency symbols
    amount_str = re.sub(r'[R$€£]', '', amount_str)
    
    # Handle negative amounts in parentheses
    if '(' in amount_str and ')' in amount_str:
        amount_str = '-' + re.sub(r'[()]', '', amount_str)
    
    # Remove spaces and commas
    amount_str = re.sub(r'[\s,]', '', amount_str)
    
    try:
        return float(amount_str) if amount_str else None
    except:
        return None

def parse_date(date_str):
    """Parse date string to DD/MM/YYYY format"""
    if pd.isna(date_str) or date_str == '' or str(date_str).lower() == 'nan':
        return None
    
    date_str = str(date_str).strip()
    
    # Handle different date formats
    date_formats = [
        '%d/%m/%Y', '%d-%m-%Y', '%Y-%m-%d', '%d %m %Y', '%d.%m.%Y',
        '%d/%m/%y', '%d-%m-%y', '%y-%m-%d'
    ]
    
    # Handle "13 Dec" format (assume 2023/2024)
    month_names = {
        'jan': '01', 'feb': '02', 'mar': '03', 'apr': '04', 'may': '05', 'jun': '06',
        'jul': '07', 'aug': '08', 'sep': '09', 'oct': '10', 'nov': '11', 'dec': '12'
    }
    
    month_match = re.search(r'(\d{1,2})\s+(\w{3})', date_str.lower())
    if month_match:
        day = month_match.group(1).zfill(2)
        month_abbr = month_match.group(2)
        if month_abbr in month_names:
            return f"{day}/{month_names[month_abbr]}/2023"
    
    # Try standard formats
    for fmt in date_formats:
        try:
            parsed_date = datetime.strptime(date_str, fmt)
            return parsed_date.strftime('%d/%m/%Y')
        except:
            continue
    
    return date_str

def categorize_transaction(description):
    """Categorize transaction based on description"""
    if pd.isna(description):
        return "Other"
    
    desc = str(description).lower()
    
    categories = {
        'Transfer': ['transfer', 'payment received', 'cash sent', 'immediate payment', 'external payment', 'eft'],
        'Groceries': ['shoprite', 'checkers', 'pick n pay', 'woolworths', 'boxer', 'superspar', 'spar'],
        'Fuel': ['engen', 'shell', 'total', 'garage', 'fuel', 'bp', 'sasol'],
        'Cash': ['cash withdrawal', 'cash deposit', 'atm'],
        'Cellphone': ['vodacom', 'mtn', 'telkom', 'cellphone', 'airtime'],
        'Banking': ['account admin fee', 'atm', 'balance enquiry', 'service fee', 'notification fee'],
        'Insurance': ['capfuneral', 'funeral cover', 'insurance'],
        'Utilities': ['electricity', 'dstv', 'municipal', 'rates'],
        'Other': ['betting', 'lotto', 'powerball', 'daily lotto']
    }
    
    for category, keywords in categories.items():
        if any(keyword in desc for keyword in keywords):
            return category
    
    return "Other"

def extract_with_tabula(pdf_path):
    """Extract using tabula-py"""
    if not TABULA_AVAILABLE:
        return []
    
    try:
        df_list = tabula.read_pdf(
            pdf_path, 
            pages='all', 
            multiple_tables=True,
            force_subprocess=True
        )
        return df_list
    except Exception as e:
        print(f"Tabula extraction failed: {e}")
        return []

def extract_with_pdfplumber(pdf_path):
    """Extract using pdfplumber"""
    if not PDFPLUMBER_AVAILABLE:
        return []
    
    try:
        all_tables = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                # Extract tables
                tables = page.extract_tables()
                for table in tables:
                    if table and len(table) > 1:
                        df = pd.DataFrame(table[1:], columns=table[0] if table[0] else None)
                        if not df.empty:
                            all_tables.append(df)
                
                # Also extract from text
                text = page.extract_text()
                if text:
                    text_df = extract_from_text(text)
                    if not text_df.empty:
                        all_tables.append(text_df)
        
        return all_tables
    except Exception as e:
        print(f"PDFplumber extraction failed: {e}")
        return []

def extract_from_text(text):
    """Extract transactions from plain text"""
    lines = text.split('\n')
    transactions = []
    
    for line in lines:
        line = line.strip()
        if len(line) < 10:
            continue
        
        # Look for date patterns
        date_match = re.search(r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})', line)
        if not date_match:
            date_match = re.search(r'(\d{1,2}\s+\w{3})', line)
        
        if date_match:
            date_str = date_match.group(1)
            
            # Look for amounts
            amounts = re.findall(r'[\d,]+\.\d{2}', line)
            if amounts:
                # Extract description
                desc = line
                desc = re.sub(r'\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}', '', desc)
                desc = re.sub(r'\d{1,2}\s+\w{3}', '', desc)
                desc = re.sub(r'[\d,]+\.\d{2}', '', desc)
                desc = re.sub(r'\s+', ' ', desc).strip()
                
                if len(desc) > 2:
                    transactions.append([date_str, desc, amounts[-1]])
    
    if transactions:
        return pd.DataFrame(transactions, columns=['Date', 'Description', 'Amount'])
    
    return pd.DataFrame()

def extract_transaction_data(df_list, bank_type="auto"):
    """Extract transaction data and format for CSV output"""
    print(f"Processing {len(df_list)} tables/data sources")
    
    all_transactions = []
    
    for i, df in enumerate(df_list):
        if df.empty:
            continue
        
        print(f"Processing table {i+1} with shape {df.shape}")
        
        # Convert to string for processing
        df = df.astype(str)
        
        # Process each row
        for idx, row in df.iterrows():
            row_text = ' '.join([str(cell) for cell in row if str(cell) != 'nan'])
            
            if len(row_text) < 10:
                continue
            
            # Extract date
            date_val = None
            date_match = re.search(r'(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4})', row_text)
            if not date_match:
                date_match = re.search(r'(\d{1,2}\s+\w{3})', row_text)
            
            if date_match:
                date_val = parse_date(date_match.group(1))
            
            if not date_val:
                continue
            
            # Extract description
            description = ""
            # Remove date from text
            desc_text = row_text
            desc_text = re.sub(r'\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}', '', desc_text)
            desc_text = re.sub(r'\d{1,2}\s+\w{3}', '', desc_text)
            
            # Remove amounts to isolate description
            desc_text = re.sub(r'[\d,]+\.\d{2}', '', desc_text)
            desc_text = re.sub(r'\s+', ' ', desc_text).strip()
            
            if len(desc_text) > 2:
                description = desc_text
            
            # Extract amounts
            amounts = re.findall(r'[\d,]+\.\d{2}', row_text)
            amount_val = None
            balance_val = None
            
            if amounts:
                # Clean amounts
                cleaned_amounts = []
                for amt in amounts:
                    cleaned = clean_amount(amt)
                    if cleaned is not None:
                        cleaned_amounts.append(cleaned)
                
                if cleaned_amounts:
                    amount_val = cleaned_amounts[0]
                    if len(cleaned_amounts) > 1:
                        balance_val = cleaned_amounts[-1]
            
            # Only add if we have meaningful data
            if date_val and description and amount_val is not None:
                transaction = {
                    'Date': date_val,
                    'Description': description,
                    'Category': categorize_transaction(description),
                    'Amount': amount_val,
                    'Balance': balance_val if balance_val else ''
                }
                all_transactions.append(transaction)
    
    print(f"Extracted {len(all_transactions)} transactions")
    
    # If no transactions found, try alternative extraction
    if not all_transactions and df_list:
        print("Trying alternative extraction method...")
        for df in df_list:
            # Look for any rows with date and amount patterns
            for idx, row in df.iterrows():
                row_values = [str(val) for val in row if str(val) != 'nan']
                
                # Find date and amount in any position
                date_found = None
                amount_found = None
                desc_parts = []
                
                for val in row_values:
                    # Check for date
                    if re.search(r'\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}', val) or re.search(r'\d{1,2}\s+\w{3}', val):
                        date_found = parse_date(val)
                    # Check for amount
                    elif re.search(r'[\d,]+\.\d{2}', val):
                        amount_found = clean_amount(val)
                    # Collect description parts
                    elif len(val) > 2 and not re.search(r'^\d+$', val):
                        desc_parts.append(val)
                
                if date_found and amount_found and desc_parts:
                    description = ' '.join(desc_parts)
                    transaction = {
                        'Date': date_found,
                        'Description': description,
                        'Category': categorize_transaction(description),
                        'Amount': amount_found,
                        'Balance': ''
                    }
                    all_transactions.append(transaction)
    
    return all_transactions

def process_pdf(pdf_path):
    """Main function to process PDF and return transaction data"""
    print(f"Processing PDF: {pdf_path}")
    
    # Try both extraction methods
    df_list = []
    
    # First try tabula
    if TABULA_AVAILABLE:
        print("Trying tabula extraction...")
        df_list = extract_with_tabula(pdf_path)
    
    # If tabula fails or not available, try pdfplumber
    if not df_list and PDFPLUMBER_AVAILABLE:
        print("Trying pdfplumber extraction...")
        df_list = extract_with_pdfplumber(pdf_path)
    
    if not df_list:
        raise Exception("No extraction method available or PDF could not be processed")
    
    # Extract transactions
    transactions = extract_transaction_data(df_list)
    
    if not transactions:
        # Create a basic structure if nothing found
        transactions = [{
            'Date': 'No data found',
            'Description': 'PDF format may not be supported',
            'Category': 'Error',
            'Amount': 0.0,
            'Balance': ''
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
