# Enhanced Debug script - JAVA-FREE VERSION with ABSA support
import os
import pandas as pd

# Import the enhanced pdf_cleaner
import pdf_cleaner

def debug_pdf_structure(pdf_path):
    print(f"\n{'='*60}")
    print(f"DEBUGGING: {os.path.basename(pdf_path)}")
    print(f"Using enhanced PDFplumber extraction (no Java required)")
    print(f"{'='*60}")
    
    try:
        # Use the enhanced extraction from pdf_cleaner
        df_list = pdf_cleaner.extract_tables_from_pdf(pdf_path)
        print(f"\n📊 Found {len(df_list)} data sources using enhanced extraction")
        
        for i, df in enumerate(df_list[:10]):  # Show first 10 sources
            print(f"\n--- Data Source {i+1} ---")
            print(f"Shape: {df.shape}")
            print(f"Columns: {df.columns.tolist()}")
            print("Sample data:")
            print(df.head(3))
            print()
            
            # Show some raw text data
            df_str = df.astype(str)
            for idx, row in df_str.head(3).iterrows():
                row_text = ' '.join([str(cell) for cell in row if str(cell) != 'nan'])
                if len(row_text) > 10:
                    print(f"Row {idx}: {row_text[:100]}...")
        
        # Test transaction extraction
        print(f"\n{'='*40}")
        print("TESTING TRANSACTION EXTRACTION")
        print(f"{'='*40}")
        
        transactions_df = pdf_cleaner.extract_transaction_data(df_list, "auto")
        print(f"\n📋 Extracted {len(transactions_df)} transactions")
        
        if not transactions_df.empty:
            print("\nSample transactions:")
            print(transactions_df.head())
            
            if 'Category' in transactions_df.columns:
                print("\nTransaction categories:")
                print(transactions_df['Category'].value_counts())
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    print("🚀 Enhanced PDF Debug Tool")
    print("Java-free version with ABSA support using PDFplumber")
    print("🔍 Testing enhanced extraction methods...")
    
    # Test files to debug
    test_files = [
        "FNB.pdf",
        "ABSA.pdf", 
        "account_statement (2) (2).pdf",  # Standard Bank
    ]
    
    for filename in test_files:
        file_path = os.path.join(script_dir, filename)
        if os.path.exists(file_path):
            debug_pdf_structure(file_path)
        else:
            print(f"\n❌ File not found: {filename}")
    
    print(f"\n{'='*60}")
    print("✅ Enhanced debug completed - No Java required!")
    print("All extraction methods tested with ABSA compatibility")
    print(f"{'='*60}")
