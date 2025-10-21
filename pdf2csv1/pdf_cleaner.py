# Import the required Module
import tabula
import pandas as pd
import os
import re
from datetime import datetime

# Set environment variable to force subprocess mode (more reliable on Windows)
os.environ["TABULA_JAVA"] = "subprocess"

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

def extract_fnb_transactions(df_list):
    """Extract transactions specifically for FNB statements"""
    return extract_universal_transactions(df_list)

def extract_standard_bank_transactions(df_list):
    """Extract transactions specifically for Standard Bank statements"""
    return extract_universal_transactions(df_list)

def extract_absa_transactions(df_list):
    """Extract transactions specifically for ABSA statements"""  
    return extract_universal_transactions(df_list)

def extract_capitec_transactions(df_list):
    """Extract transactions specifically for Capitec statements"""
    return extract_universal_transactions(df_list)

def extract_nedbank_transactions(df_list):
    """Extract transactions specifically for Nedbank statements"""
    return extract_universal_transactions(df_list)

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
    """Extract and clean transaction data based on bank type"""
    # All banks now use the universal extractor for better compatibility
    bank_type_lower = bank_type.lower()
    
    if bank_type_lower in ["fnb", "first national bank"]:
        return extract_fnb_transactions(df_list)
    elif bank_type_lower in ["standard bank", "standard"]:
        return extract_standard_bank_transactions(df_list)
    elif bank_type_lower in ["absa", "absa bank"]:
        return extract_absa_transactions(df_list)
    elif bank_type_lower in ["capitec", "capitec bank"]:
        return extract_capitec_transactions(df_list)
    elif bank_type_lower in ["nedbank", "ned bank"]:
        return extract_nedbank_transactions(df_list)
    else:
        # Auto-detect: use universal extractor
        return extract_universal_transactions(df_list)

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
