# Debug script to examine PDF structure
import tabula
import pandas as pd
import os
import re
from datetime import datetime

# Set environment variable to force subprocess mode
os.environ["TABULA_JAVA"] = "subprocess"

def debug_pdf_structure(pdf_path):
    print(f"\n=== DEBUGGING {pdf_path} ===")
    
    try:
        # Read PDF
        df_list = tabula.read_pdf(pdf_path, pages='all', force_subprocess=True)
        print(f"Found {len(df_list)} tables")
        
        for i, df in enumerate(df_list[:5]):  # Show first 5 tables
            print(f"\n--- Table {i+1} ---")
            print(f"Shape: {df.shape}")
            print(f"Columns: {df.columns.tolist()}")
            print("Sample data:")
            print(df.head(3))
            
            # Show some raw text data
            df_str = df.astype(str)
            for idx, row in df_str.head(3).iterrows():
                row_text = ' '.join([str(cell) for cell in row if str(cell) != 'nan'])
                if len(row_text) > 10:
                    print(f"Row {idx}: {row_text[:100]}...")
                    
    except Exception as e:
        print(f"Error: {e}")

def clean_amount(amount_str):
    """Clean and convert amount string to float"""
    if pd.isna(amount_str) or amount_str == '' or str(amount_str).lower() == 'nan':
        return None
    
    # Convert to string and clean
    amount = str(amount_str).strip()
    # Remove spaces and currency symbols
    amount = re.sub(r'[R\s]', '', amount)
    # Handle negative amounts in parentheses
    if amount.startswith('(') and amount.endswith(')'):
        amount = '-' + amount[1:-1]
    
    try:
        return float(amount.replace(',', ''))
    except:
        return None

def parse_date(date_str):
    """Parse date string to standard format"""
    if pd.isna(date_str) or date_str == '' or str(date_str).lower() == 'nan':
        return None
    
    date_str = str(date_str).strip()
    
    # Try different date formats
    date_formats = [
        '%d/%m/%Y',
        '%d-%m-%Y',
        '%Y-%m-%d',
        '%d %m %Y',
        '%d.%m.%Y'
    ]
    
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
    
    # Define category mappings
    categories = {
        'Transfer': ['transfer', 'payment received', 'cash sent', 'immediate payment', 'external payment'],
        'Groceries': ['shoprite', 'checkers', 'pick n pay', 'woolworths', 'boxer', 'superspar', 'spar'],
        'Fuel': ['engen', 'shell', 'total', 'garage', 'fuel'],
        'Cash': ['cash withdrawal', 'cash deposit', 'atm'],
        'Cellphone': ['vodacom', 'mtn', 'telkom', 'cellphone'],
        'Banking': ['account admin fee', 'atm', 'balance enquiry'],
        'Insurance': ['capfuneral', 'funeral cover'],
        'Utilities': ['electricity', 'dstv'],
        'Other': ['betting', 'lotto', 'powerball']
    }
    
    for category, keywords in categories.items():
        if any(keyword in desc for keyword in keywords):
            return category
    
    return "Other"

def extract_bank_statements(pdf_path):
    """Extract bank statement data and convert to standardized CSV format"""
    print(f"\n=== Processing {pdf_path} ===")
    
    try:
        # Read PDF with multiple extraction strategies
        df_list = tabula.read_pdf(
            pdf_path, 
            pages='all', 
            multiple_tables=True,
            force_subprocess=True,
            lattice=True,
            stream=True
        )
        
        all_transactions = []
        
        for i, df in enumerate(df_list):
            print(f"Processing table {i+1} with shape {df.shape}")
            
            if df.empty:
                continue
            
            # Try to identify columns based on content patterns
            date_col = None
            desc_col = None
            amount_col = None
            balance_col = None
            
            # Find columns by analyzing content
            for col_idx, col in enumerate(df.columns):
                sample_data = df[col].dropna().astype(str).head(10)
                
                # Check for date patterns
                date_pattern = r'\d{1,2}[/-]\d{1,2}[/-]\d{2,4}'
                if any(re.search(date_pattern, str(val)) for val in sample_data):
                    date_col = col
                
                # Check for amount patterns (numbers with decimals)
                amount_pattern = r'[\d,]+\.\d{2}'
                if any(re.search(amount_pattern, str(val)) for val in sample_data):
                    if amount_col is None:
                        amount_col = col
                    else:
                        balance_col = col
                
                # Description column (usually contains text)
                if col_idx > 0 and date_col is not None and col != date_col and col != amount_col and col != balance_col:
                    if desc_col is None:
                        desc_col = col
            
            # Process each row
            for _, row in df.iterrows():
                # Extract date
                date_val = None
                if date_col is not None:
                    date_val = parse_date(row[date_col])
                
                # Extract description
                desc_val = ""
                if desc_col is not None:
                    desc_val = str(row[desc_col]) if not pd.isna(row[desc_col]) else ""
                
                # If no specific description column, combine all text columns
                if not desc_val or desc_val == "nan":
                    text_parts = []
                    for col in df.columns:
                        if col != date_col and col != amount_col and col != balance_col:
                            val = str(row[col]) if not pd.isna(row[col]) else ""
                            if val and val != "nan":
                                text_parts.append(val)
                    desc_val = " ".join(text_parts)
                
                # Extract amounts
                amount_val = None
                balance_val = None
                
                if amount_col is not None:
                    amount_val = clean_amount(row[amount_col])
                
                if balance_col is not None:
                    balance_val = clean_amount(row[balance_col])
                
                # Skip empty rows
                if not date_val and not desc_val:
                    continue
                
                # Determine bank from filename or description
                bank = "Unknown"
                if "fnb" in pdf_path.lower():
                    bank = "FNB"
                elif "standard" in pdf_path.lower():
                    bank = "Standard Bank"
                elif "absa" in pdf_path.lower() or "absa" in desc_val.lower():
                    bank = "ABSA"
                
                # Create transaction record
                transaction = {
                    'Date': date_val,
                    'Description': desc_val,
                    'Category': categorize_transaction(desc_val),
                    'Amount': amount_val,
                    'Balance': balance_val,
                    'Bank': bank
                }
                
                all_transactions.append(transaction)
        
        return all_transactions
        
    except Exception as e:
        print(f"Error processing {pdf_path}: {e}")
        return []

def save_to_csv(transactions, output_file):
    """Save transactions to CSV file"""
    if not transactions:
        print("No transactions to save")
        return
    
    # Create DataFrame
    df = pd.DataFrame(transactions)
    
    # Clean and format data
    df['Date'] = df['Date'].fillna('')
    df['Description'] = df['Description'].fillna('')
    df['Category'] = df['Category'].fillna('Other')
    df['Amount'] = df['Amount'].fillna('')
    df['Balance'] = df['Balance'].fillna('')
    df['Bank'] = df['Bank'].fillna('Unknown')
    
    # Remove completely empty rows
    df = df[~((df['Date'] == '') & (df['Description'] == '') & (df['Amount'] == ''))]
    
    # Save to CSV
    df.to_csv(output_file, index=False)
    print(f"Saved {len(df)} transactions to {output_file}")

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    all_transactions = []
    
    # Process FNB
    fnb_path = os.path.join(script_dir, "FNB.pdf")
    if os.path.exists(fnb_path):
        transactions = extract_bank_statements(fnb_path)
        all_transactions.extend(transactions)
    
    # Process Standard Bank
    standard_path = os.path.join(script_dir, "account_statement (2) (2).pdf")
    if os.path.exists(standard_path):
        transactions = extract_bank_statements(standard_path)
        all_transactions.extend(transactions)
    
    # Save combined results
    if all_transactions:
        output_file = os.path.join(script_dir, "bank_statements.csv")
        save_to_csv(all_transactions, output_file)
    else:
        print("No transactions found to process")
