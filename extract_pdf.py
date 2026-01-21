import pdfplumber
import sys

pdf_path = "bala_report.pdf"

try:
    with pdfplumber.open(pdf_path) as pdf:
        print(f"Total pages: {len(pdf.pages)}\n")
        print("="*80)
        
        for i, page in enumerate(pdf.pages, 1):
            text = page.extract_text()
            print(f"\n--- PAGE {i} ---\n")
            print(text)
            print("\n" + "="*80)
            
except Exception as e:
    print(f"Error reading PDF: {e}")
    sys.exit(1)
