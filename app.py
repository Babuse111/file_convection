from flask import Flask, render_template, request, redirect, url_for, send_from_directory, abort
from markupsafe import Markup
import pandas as pd
from pathlib import Path
import os
import io
import csv
import re

app = Flask(__name__, template_folder="templates")
BASE = Path(r"C:\Users\User\OneDrive\Documents\file_convection")
CSV_PATH = BASE / "BMMASSOCIATES_1820345112_Standard_Csv_Format (3).csv"
UPLOADS = BASE / "uploads"
OUTPUTS = BASE / "outputs"
UPLOADS.mkdir(exist_ok=True)
OUTPUTS.mkdir(exist_ok=True)

def load_data(path: Path):
    # existing loader (unchanged)
    with path.open(encoding="utf-8") as f:
        acc_line = f.readline().strip()
        opening_line = f.readline().strip()
    try:
        account_number = acc_line.split(",", 1)[1].strip()
    except Exception:
        account_number = acc_line
    try:
        opening_balance = float(opening_line.split(",", 1)[1].strip())
    except Exception:
        opening_balance = None

    try:
        df = pd.read_csv(path, skiprows=2, parse_dates=["Date"], dayfirst=True, low_memory=False)
    except Exception:
        df = pd.read_csv(path, skiprows=2, low_memory=False)
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")

    for col in ["Debit", "Credit", "Balance"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    display_cols = [c for c in ["Period", "Date", "Details", "Debit", "Credit", "Balance", "Cheque"] if c in df.columns]
    df = df[display_cols].copy()
    if "Date" in df.columns:
        df = df.sort_values("Date").reset_index(drop=True)

    if opening_balance is not None and "Debit" in df.columns and "Credit" in df.columns:
        df["calc_balance"] = opening_balance - df["Debit"].fillna(0).cumsum() + df["Credit"].fillna(0).cumsum()
        mismatches = df[df["Balance"].notna() & ((df["Balance"] - df["calc_balance"]).abs() > 0.01)]
    else:
        mismatches = df.iloc[0:0]

    df_display = df.copy()
    if "Date" in df_display.columns:
        df_display["Date"] = df_display["Date"].dt.strftime("%d-%m-%Y").fillna("")
    if "Details" in df_display.columns:
        df_display["Details"] = df_display["Details"].astype(str)

    return account_number, opening_balance, df, df_display, mismatches

def extract_text_from_pdf(path: Path) -> str:
    # quick text extraction fallback
    try:
        import pdfplumber
        text = []
        with pdfplumber.open(path) as pdf:
            for p in pdf.pages:
                text.append(p.extract_text() or "")
        return "\n".join(text)
    except Exception:
        return ""

def convert_pdf_to_df(path: Path) -> pd.DataFrame:
    # Try tabula (Java required), then try simple text parsing fallback
    try:
        import tabula
        tables = tabula.read_pdf(str(path), pages="all", multiple_tables=True, lattice=False)
        if tables and len(tables) >= 1:
            df = pd.concat(tables, ignore_index=True, sort=False)
            return df
    except Exception:
        pass

    # fallback: extract text and try to parse CSV-like lines
    text = extract_text_from_pdf(path)
    # try to find header line containing "Period" and subsequent CSV lines
    lines = text.splitlines()
    # attempt to find index where header appears
    header_idx = None
    for i, L in enumerate(lines):
        if "Period" in L and "Date" in L and "Details" in L:
            header_idx = i
            break
    if header_idx is None:
        # last resort: return empty df
        return pd.DataFrame()

    raw_rows = lines[header_idx:]
    # join using comma separation heuristic and parse with csv reader
    cleaned = []
    for r in raw_rows:
        # replace multiple spaces with comma where it looks like columns; naive
        # prefer to keep existing commas
        if r.strip() == "":
            continue
        cleaned.append(r)
    # try csv.reader on cleaned lines
    reader = csv.reader(cleaned)
    rows = list(reader)
    if not rows:
        return pd.DataFrame()
    df = pd.DataFrame(rows[1:], columns=rows[0])
    return df

def write_output_csv(df: pd.DataFrame, account: str, opening: float, out_path: Path):
    # ensure canonical columns
    cols = [c for c in ["Period","Date","Details","Debit","Credit","Balance","Cheque"] if c in df.columns]
    df_out = df[cols].copy()
    # write metadata + table
    with out_path.open("w", encoding="utf-8", newline="") as f:
        f.write(f"Account Number: ,{account}\n")
        f.write(f"Opening Balance:,{opening if opening is not None else ''}\n")
        df_out.to_csv(f, index=False)

@app.route("/", methods=["GET"])
def index():
    if CSV_PATH.exists():
        account_number, opening_balance, df, df_display, mismatches = load_data(CSV_PATH)
        preview_html = Markup(df_display.head(200).to_html(classes="table table-sm table-striped", index=False, escape=False))
        mismatches_html = Markup(mismatches.to_html(classes="table table-sm table-danger", index=False, escape=False)) if len(mismatches) else ""
        summary = {
            "rows": int(len(df)),
            "columns": list(df.columns),
            "nulls": df.isnull().sum().to_dict(),
            "duplicates": int(df.duplicated().sum()),
            "mismatch_count": int(len(mismatches))
        }
    else:
        account_number = ""
        opening_balance = ""
        preview_html = ""
        mismatches_html = ""
        summary = {"rows":0,"columns":[],"nulls":{},"duplicates":0,"mismatch_count":0}
    return render_template("index.html",
                           account=account_number,
                           opening_balance=opening_balance,
                           preview_html=preview_html,
                           mismatches_html=mismatches_html,
                           summary=summary)

@app.route("/upload", methods=["POST"])
def upload():
    f = request.files.get("pdf")
    if not f:
        return redirect(url_for("index"))
    filename = f.filename
    safe = filename.replace(" ", "_")
    save_path = UPLOADS / safe
    f.save(save_path)

    # try convert
    try:
        df = convert_pdf_to_df(save_path)
    except Exception:
        df = pd.DataFrame()  # Ensure df is always defined

    # attempt to discover metadata from PDF text
    text = extract_text_from_pdf(save_path)
    acct = ""
    opening = ""
    m = re.search(r"Account Number[:\s]*([0-9A-Za-z-]+)", text)
    if m:
        acct = m.group(1).strip()
    m2 = re.search(r"Opening Balance[:\s]*([\d,\.]+)", text)
    if m2:
        opening = float(m2.group(1).replace(",",""))

    # if df empty return message
    if df.empty:
        return render_template("index.html", account=acct, opening_balance=opening, preview_html="Could not parse tables from PDF. Try upload a different PDF or install Java + tabula.", mismatches_html="", summary={"rows":0,"columns":[],"nulls":{},"duplicates":0,"mismatch_count":0})

    # try to coerce column names to expected ones if possible
    df.columns = [c.strip() for c in df.columns]
    # if Date present, try to parse
    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"], dayfirst=True, errors="coerce")
    # convert numeric columns heuristically
    for col in ["Debit","Credit","Balance"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col].astype(str).str.replace(",",""), errors="coerce")

    out_name = f"{Path(safe).stem}.csv"
    out_path = OUTPUTS / out_name
    write_output_csv(df, acct or "UNKNOWN", opening or "", out_path)

    return redirect(url_for("download", filename=out_name))

@app.route("/files")
def files_list():
    out_dir = OUTPUTS
    if not out_dir.exists():
        return "No outputs directory", 404
    files = sorted([p.name for p in out_dir.iterdir() if p.is_file()])
    links = ["<li><a href='{}'>{}</a></li>".format(url_for('download', filename=f), f) for f in files]
    return "<h3>Available files</h3><ul>{}</ul>".format("".join(links))

# optional: safer download with 404 if not found
@app.route("/download/<path:filename>")
def download(filename):
    fpath = OUTPUTS / filename
    if not fpath.exists() or not fpath.is_file():
        abort(404)
    return send_from_directory(str(OUTPUTS), filename, as_attachment=True)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5001))
    app.run(debug=True, host="0.0.0.0", port=port)