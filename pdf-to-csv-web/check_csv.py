# python
import pandas as pd
from pathlib import Path

path = Path(r"C:\Users\User\OneDrive\Documents\file_convection\BMMASSOCIATES_1820345112_Standard_Csv_Format (3).csv")

# read metadata
with path.open(encoding="utf-8") as f:
    acc_line = f.readline().strip()
    opening_line = f.readline().strip()

account_number = acc_line.split(",", 1)[1].strip()
opening_balance = float(opening_line.split(",", 1)[1].strip())

# load data table (skip metadata rows)
df = pd.read_csv(path, skiprows=2, parse_dates=['Date'], dayfirst=True, low_memory=False)

# cleanup
if 'Details' in df.columns:
    df['Details'] = df['Details'].astype(str).str.strip()
for col in ['Debit','Credit','Balance']:
    if col in df.columns:
        df[col] = pd.to_numeric(df[col], errors='coerce')

df = df.sort_values('Date').reset_index(drop=True)

# validate running balance
df['calc_balance'] = opening_balance - df['Debit'].fillna(0).cumsum() + df['Credit'].fillna(0).cumsum()
mismatches = df[df['Balance'].notna() & ((df['Balance'] - df['calc_balance']).abs() > 0.01)]

# summary
print("Account:", account_number)
print("Opening balance:", opening_balance)
print("Rows:", len(df))
print("Columns:", df.columns.tolist())
print("Nulls per column:\n", df.isnull().sum())
print("Duplicate rows:", df.duplicated().sum())
print("Balance mismatches:", len(mismatches))
if len(mismatches):
    print(mismatches[['Date','Details','Debit','Credit','Balance','calc_balance']].head(20).to_string(index=False))

# save cleaned outputs
out_csv = path.with_name(path.stem + "_cleaned.csv")
out_xlsx = path.with_name(path.stem + "_cleaned.xlsx")
df.to_csv(out_csv, index=False)
df.to_excel(out_xlsx, index=False)
print("Saved:", out_csv, out_xlsx)