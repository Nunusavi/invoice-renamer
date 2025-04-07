import os
import re
import zipfile
from datetime import datetime
from flask import Flask, render_template, request, send_file, jsonify
from werkzeug.utils import secure_filename
from PyPDF2 import PdfReader
from io import BytesIO

app = Flask(__name__)
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Regex patterns to extract invoice info
DATE_PATTERN = r'(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})'
ORDER_PATTERN = r'Order\s*(?:No|Number)[:\s]*([A-Z0-9-]+)'
INVOICE_PATTERN = r'Invoice\s*(?:No|Number)[:\s]*([A-Z0-9-]+)'
COMPANY_PATTERN = r'(?:From|Supplier|Company)[:\s]*([A-Za-z0-9 &.,]+)'

def extract_invoice_info(text):
    date_match = re.search(DATE_PATTERN, text)
    order_match = re.search(ORDER_PATTERN, text)
    invoice_match = re.search(INVOICE_PATTERN, text)
    company_match = re.search(COMPANY_PATTERN, text)

    try:
        date_raw = date_match.group(1)
        invoice_date = datetime.strptime(date_raw.replace('/', '-'), "%d-%m-%Y").strftime("%d-%m-%Y")
    except:
        invoice_date = "unknown-date"

    order_or_invoice = order_match.group(1) if order_match else (invoice_match.group(1) if invoice_match else "unknown-id")
    company = company_match.group(1).strip().replace(" ", "_") if company_match else "UnknownCompany"

    return invoice_date, company, order_or_invoice

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/process', methods=['POST'])
def process():
    files = request.files.getlist('files')
    renamed_files = []
    zip_buffer = BytesIO()

    for file in files:
        if file.filename.endswith('.pdf'):
            filename = secure_filename(file.filename)
            filepath = os.path.join(UPLOAD_FOLDER, filename)
            file.save(filepath)

            try:
                reader = PdfReader(filepath)
                text = ''.join(page.extract_text() or "" for page in reader.pages)

                date, company, ref_number = extract_invoice_info(text)
                new_filename = f"{date}_{company}_{ref_number}.pdf"
                new_path = os.path.join(UPLOAD_FOLDER, new_filename)
                os.rename(filepath, new_path)

                renamed_files.append((filename, new_filename, new_path))

            except Exception as e:
                print(f"Error processing {filename}: {e}")
                continue

    if len(renamed_files) >= 5:
        with zipfile.ZipFile(zip_buffer, 'w') as zipf:
            for _, new_name, path in renamed_files:
                zipf.write(path, new_name)
        zip_buffer.seek(0)
        return send_file(zip_buffer, as_attachment=True, download_name="renamed_invoices.zip", mimetype='application/zip')
    else:
        response = [{"original": orig, "renamed": renamed} for orig, renamed, _ in renamed_files]
        return jsonify(response)

@app.route('/download/<filename>')
def download_file(filename):
    file_path = os.path.join(UPLOAD_FOLDER, filename)
    return send_file(file_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)
