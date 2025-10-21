# Debug script to examine PDF structure
import tabula
import pandas as pd
import os

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

if __name__ == "__main__":
    script_dir = os.path.dirname(os.path.abspath(__file__))
    
    # Debug FNB
    fnb_path = os.path.join(script_dir, "FNB.pdf") 
    if os.path.exists(fnb_path):
        debug_pdf_structure(fnb_path)
    
    # Debug Standard Bank  
    standard_path = os.path.join(script_dir, "account_statement (2) (2).pdf")
    if os.path.exists(standard_path):
        debug_pdf_structure(standard_path)
