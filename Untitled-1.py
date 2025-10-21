# Import the required Module - JAVA-FREE VERSION
import os
import pandas as pd
import pdfplumber
import re

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))
pdf_path = os.path.join(script_dir, "FNB.pdf")
csv_path = os.path.join(script_dir, "FNB.csv")

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
        
        print(f"Extracted {len(all_tables)} tables using PDFplumber")
        return all_tables
        
    except Exception as e:
        print(f"PDFplumber extraction failed: {e}")
        raise Exception(f"Failed to extract data with PDFplumber: {e}")

# Read a PDF File using PDFplumber (no Java required)
print("Extracting data from PDF using PDFplumber (no Java required)...")
df_list = extract_tables_with_pdfplumber(pdf_path)

# Combine all pages and remove duplicate headers
combined_df = pd.DataFrame()

for i, df in enumerate(df_list):
    if i == 0:
        # Keep the first dataframe with headers
        combined_df = df
    else:
        # For subsequent dataframes, check if first row matches headers
        # If it does, skip it (it's a repeated header)
        if not df.empty and not combined_df.empty:
            try:
                if df.iloc[0].equals(df.columns.to_series().reset_index(drop=True)):
                    df = df.iloc[1:]  # Skip the first row
                elif list(df.iloc[0]) == list(combined_df.columns):
                    df = df.iloc[1:]  # Skip the first row if it matches column names
            except:
                pass  # If comparison fails, just continue
        
        # Reset index and append
        df.reset_index(drop=True, inplace=True)
        combined_df = pd.concat([combined_df, df], ignore_index=True)

# Remove any rows that are identical to the header
if not combined_df.empty:
    try:
        header_values = list(combined_df.columns)
        combined_df = combined_df[~combined_df.apply(lambda row: list(row) == header_values, axis=1)]
    except:
        pass  # If header removal fails, continue

# Save the cleaned data to CSV
combined_df.to_csv(csv_path, index=False)

print("Data extracted successfully using PDFplumber!")
print(f"Shape: {combined_df.shape}")
print("\nFirst few rows:")
print(combined_df.head())
print(f"\nCSV saved as: {csv_path}")
print("✅ No Java required - completely Java-free operation!")