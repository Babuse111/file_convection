# Debug script to examine PDF structure - JAVA-FREE VERSION
import pdfplumber
import pandas as pd
import os
import re

def debug_pdf_structure(pdf_path):
    print(f"\n=== DEBUGGING {pdf_path} (using PDFplumber - no Java required) ===")
    
    try:
        # Use PDFplumber instead of tabula
        df_list = extract_tables_with_pdfplumber(pdf_path)
        print(f"Found {len(df_list)} tables using PDFplumber")
        
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
                    
        # Also debug raw text extraction
        debug_raw_text(pdf_path)
                    
    except Exception as e:
        print(f"Error: {e}")

def extract_tables_with_pdfplumber(pdf_path):
    """Extract tables from PDF using pdfplumber (no Java required)"""
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
        
        return all_tables
        
    except Exception as e:
        print(f"PDFplumber extraction failed: {e}")
        return []

def debug_raw_text(pdf_path):
    """Debug raw text extraction from PDF"""
    print(f"\n=== RAW TEXT ANALYSIS ===")
    
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page_num, page in enumerate(pdf.pages[:2]):  # First 2 pages
                print(f"\n--- Page {page_num + 1} Raw Text ---")
                text = page.extract_text()
                if text:
                    lines = text.split('\n')
                    print(f"Total lines: {len(lines)}")
                    
                    # Show lines with dates
                    date_lines = []
                    for i, line in enumerate(lines):
                        if re.search(r'\d{1,2}[\/\-]\d{1,2}[\/\-]\d{2,4}', line):
                            date_lines.append((i, line))
                    
                    print(f"Lines with dates: {len(date_lines)}")
                    for line_num, line in date_lines[:10]:  # First 10 date lines
                        print(f"Line {line_num}: {line[:100]}...")
                    
                    # Show lines with amounts
                    amount_lines = []
                    for i, line in enumerate(lines):
                        if re.search(r'\d+\.\d{2}', line):
                            amount_lines.append((i, line))
                    
                    print(f"Lines with amounts: {len(amount_lines)}")
                    for line_num, line in amount_lines[:5]:  # First 5 amount lines
                        print(f"Line {line_num}: {line[:100]}...")
                        
    except Exception as e:
        print(f"Raw text analysis failed: {e}")

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    print("🚀 PDF Debug Tool - Java-free version using PDFplumber")
    print("=" * 50)
    
    # Debug FNB
    fnb_path = os.path.join(script_dir, "FNB.pdf") 
    if os.path.exists(fnb_path):
        debug_pdf_structure(fnb_path)
    else:
        print(f"FNB.pdf not found at: {fnb_path}")
    
    # Debug Standard Bank  
    standard_path = os.path.join(script_dir, "account_statement (2) (2).pdf")
    if os.path.exists(standard_path):
        debug_pdf_structure(standard_path)
    else:
        print(f"Standard Bank PDF not found at: {standard_path}")
    
    # Debug ABSA (if exists)
    absa_path = os.path.join(script_dir, "ABSA.pdf")
    if os.path.exists(absa_path):
        debug_pdf_structure(absa_path)
    else:
        print(f"ABSA.pdf not found at: {absa_path}")
    
    print("\n✅ Debug completed - No Java required!")
