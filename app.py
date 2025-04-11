import os
import re
import shutil
import zipfile
import tempfile
from datetime import datetime
from flask import Flask, request, send_file, render_template
from PyPDF2 import PdfReader
import pandas as pd

app = Flask(__name__)

UPLOAD_FOLDER = tempfile.mkdtemp()


def extract_text(file_path):
    try:
        with open(file_path, 'rb') as f:
            reader = PdfReader(f)
            return "".join(page.extract_text() or '' for page in reader.pages)
    except Exception as e:
        print(f"Error extracting text from {file_path}: {e}")
        return ""

def extract_pdf_metadata(file_path):
    text = extract_text(file_path)

    order_number_match = re.search(r'Order #\s*(\S+)', text)
    order_number = order_number_match.group(1) if order_number_match else "UnknownOrder"

    sold_by_match = re.search(r'Sold by\s*([^\s]+\s+[^\s]+)', text)
    sold_by = sold_by_match.group(1).strip() if sold_by_match else "UnknownCompany"

    invoice_date_match = re.search(r'Order date\s*(.*)', text)
    if invoice_date_match:
        try:
            invoice_date = pd.to_datetime(invoice_date_match.group(1).strip()).strftime('%d-%m-%Y')
        except ValueError:
            invoice_date = "UnknownDate"
    else:
        invoice_date = "UnknownDate"

    return invoice_date, sold_by, order_number

def rename_file(original_path, output_folder, used_names):
    invoice_date, sold_by, order_number = extract_pdf_metadata(original_path)
    base_name = f"{invoice_date} {order_number} {sold_by}.pdf"

    part = 1
    new_name = base_name
    while new_name in used_names:
        part += 1
        new_name = f"{invoice_date} {order_number} {sold_by} part {part}.pdf"

    used_names.add(new_name)
    new_path = os.path.join(output_folder, new_name)
    shutil.copy2(original_path, new_path)
    return new_path

@app.route('/', methods=['GET', 'POST'])
def upload_files():
    if request.method == 'POST':
        files = request.files.getlist('pdfs')
        if not files:
            return 'No files uploaded.'

        output_dir = tempfile.mkdtemp()
        used_names = set()
        result_files = []

        for file in files:
            filename = file.filename
            file_path = os.path.join(UPLOAD_FOLDER, filename)
            file.save(file_path)
            new_file = rename_file(file_path, output_dir, used_names)
            result_files.append(new_file)

        if len(result_files) >= 5:
            zip_path = os.path.join(UPLOAD_FOLDER, f"renamed_pdfs_{datetime.now().strftime('%Y%m%d%H%M%S')}.zip")
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for f in result_files:
                    zipf.write(f, os.path.basename(f))
            return send_file(zip_path, as_attachment=True)
        elif len(result_files) == 1:
            return send_file(result_files[0], as_attachment=True)
        else:
            zip_path = os.path.join(UPLOAD_FOLDER, f"bundle_{datetime.now().strftime('%Y%m%d%H%M%S')}.zip")
            with zipfile.ZipFile(zip_path, 'w') as zipf:
                for f in result_files:
                    zipf.write(f, os.path.basename(f))
            return send_file(zip_path, as_attachment=True)

    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
