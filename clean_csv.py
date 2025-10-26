import argparse
from pathlib import Path
import pandas as pd

CSV = Path(r"C:\Users\User\OneDrive\Documents\file_convection\BMMASSOCIATES_1820345112_Standard_Csv_Format (3).csv")

def load_metadata(path):
    with path.open(encoding="utf-8") as f:
        acc = f.readline().strip()
        opening = f.readline().strip()
    try:
        account_number = acc.split(",",1)[1].strip()
    except Exception:
        account_number = acc
    try:
        opening_balance = float(opening.split(",",1)[1].strip())
    except Exception:
        opening_balance = None
    return account_number, opening_balance

def main(fix=False):
    account, opening = load_metadata(CSV)
    print("Account:", account)
    print("Opening balance:", opening)

    df = pd.read_csv(CSV, skiprows=2, parse_dates=["Date"], dayfirst=True, low_memory=False)
    for col in ["Debit","Credit","Balance"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    print("Rows:", len(df))
    dup_before = df.duplicated().sum()
    print("Duplicate rows:", dup_before)

    # drop exact duplicates
    df = df.drop_duplicates().reset_index(drop=True)
    dup_after = dup_before - df.duplicated().sum()
    print("Duplicates removed:", dup_before - df.duplicated().sum())

    # sort and calc running balance
    if "Date" in df.columns:
        df = df.sort_values("Date").reset_index(drop=True)
    df["calc_balance"] = opening - df["Debit"].fillna(0).cumsum() + df["Credit"].fillna(0).cumsum()

    # report missing counts
    print("Nulls per column:\n", df.isnull().sum())

    # mismatches
    mismatches = df[df["Balance"].notna() & ((df["Balance"] - df["calc_balance"]).abs() > 0.01)]
    print("Balance mismatches:", len(mismatches))
    if len(mismatches):
        print(mismatches.head(10).to_string(index=False))

    # optionally fix Balance column to calc_balance
    out_csv = CSV.with_name(CSV.stem + ("_cleaned_fixed.csv" if fix else "_cleaned.csv"))
    out_xlsx = CSV.with_name(CSV.stem + ("_cleaned_fixed.xlsx" if fix else "_cleaned.xlsx"))
    if fix:
        df["Balance"] = df["calc_balance"].round(2)

    df.to_csv(out_csv, index=False)
    df.to_excel(out_xlsx, index=False)
    print("Saved:", out_csv, out_xlsx)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--fix", action="store_true", help="Replace Balance with calculated running balance")
    args = parser.parse_args()
    main(fix=args.fix)