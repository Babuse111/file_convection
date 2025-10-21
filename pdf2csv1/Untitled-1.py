# Import the required Module
import tabula
import os

# Set environment variable to force subprocess mode (more reliable on Windows)
os.environ["TABULA_JAVA"] = "subprocess"

# Get the directory where this script is located
script_dir = os.path.dirname(os.path.abspath(__file__))
pdf_path = os.path.join(script_dir, "FNB.pdf")
csv_path = os.path.join(script_dir, "FNB.csv")

# Read a PDF File using subprocess mode to avoid Java issues
df_list = tabula.read_pdf(pdf_path, pages='all', force_subprocess=True)

# Combine all pages and remove duplicate headers
import pandas as pd
combined_df = pd.DataFrame()

for i, df in enumerate(df_list):
    if i == 0:
        # Keep the first dataframe with headers
        combined_df = df
    else:
        # For subsequent dataframes, check if first row matches headers
        # If it does, skip it (it's a repeated header)
        if df.iloc[0].equals(df.columns.to_series().reset_index(drop=True)):
            df = df.iloc[1:]  # Skip the first row
        elif list(df.iloc[0]) == list(combined_df.columns):
            df = df.iloc[1:]  # Skip the first row if it matches column names
        
        # Reset index and append
        df.reset_index(drop=True, inplace=True)
        combined_df = pd.concat([combined_df, df], ignore_index=True)

# Remove any rows that are identical to the header
header_values = list(combined_df.columns)
combined_df = combined_df[~combined_df.apply(lambda row: list(row) == header_values, axis=1)]

# Save the cleaned data to CSV
combined_df.to_csv(csv_path, index=False)

print("Data extracted successfully!")
print(f"Shape: {combined_df.shape}")
print("\nFirst few rows:")
print(combined_df.head())
print(f"\nCSV saved as: {csv_path}")