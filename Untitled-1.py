# Import the required Module - ENHANCED JAVA-FREE VERSION
import os
import pandas as pd
import pdfplumber
import re

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))
pdf_path = os.path.join(script_dir, "FNB.pdf")
csv_path = os.path.join(script_dir, "FNB.csv")

# Import the enhanced extraction functions
import pdf_cleaner

print("🚀 Enhanced PDF to CSV Converter - Java-free with ABSA support")
print("=" * 60)

# Read a PDF File using enhanced PDFplumber extraction
print(f"Processing: {pdf_path}")
print("Using enhanced extraction methods...")

try:
    # Use the enhanced extraction from pdf_cleaner
    df_list = pdf_cleaner.extract_tables_from_pdf(pdf_path)
    
    print(f"Extracted {len(df_list)} data sources")
    
    # Use the enhanced transaction extraction
    transactions_df = pdf_cleaner.extract_transaction_data(df_list, "auto")
    
    print(f"Found {len(transactions_df)} transactions")
    
    # Sort by date if possible
    try:
        transactions_df['Date'] = pd.to_datetime(transactions_df['Date'], format='%d/%m/%Y', errors='coerce')
        transactions_df = transactions_df.sort_values('Date')
        transactions_df['Date'] = transactions_df['Date'].dt.strftime('%d/%m/%Y')
    except:
        print("Could not sort by date, keeping original order")
    
    # Remove duplicates
    transactions_df = transactions_df.drop_duplicates()
    
    # Save to CSV
    transactions_df.to_csv(csv_path, index=False)
    
    print("\n✅ Data extracted successfully!")
    print(f"📊 Shape: {transactions_df.shape}")
    print(f"💾 CSV saved as: {csv_path}")
    
    print("\n📋 First few transactions:")
    print(transactions_df.head())
    
    print("\n🎯 Transaction categories:")
    if 'Category' in transactions_df.columns:
        print(transactions_df['Category'].value_counts())
    
except Exception as e:
    print(f"❌ Error: {str(e)}")
    print("Please check if the PDF file exists and is readable")

print("\n✅ Processing completed - No Java required!")