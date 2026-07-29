import os
import json
import glob
import sys
from pdf_parser import parse_pdf_to_chunks
from config import settings

def main():
    print("=" * 70)
    print(" HINDI GOVERNMENT CIRCULAR CHUNK INSPECTOR")
    print("=" * 70)

    pdf_files = []
    if os.path.exists(settings.DATA_DIR):
        pdf_files.extend(glob.glob(os.path.join(settings.DATA_DIR, "**", "*.pdf"), recursive=True))
        pdf_files.extend(glob.glob(os.path.join(settings.DATA_DIR, "*.pdf")))
    pdf_files.extend(glob.glob("*.pdf"))

    pdf_files = sorted(list(set(pdf_files)))

    if not pdf_files:
        print("ERROR: No PDF files found to inspect.")
        sys.exit(1)

    pdf_to_inspect = pdf_files[0]
    print(f"Parsing PDF: {pdf_to_inspect}\n")
    chunks = parse_pdf_to_chunks(pdf_to_inspect)

    print(f"Total Chunks Extracted: {len(chunks)}")
    print("=" * 70)

    for i, c in enumerate(chunks):
        print(f"CHUNK {i+1}/{len(chunks)} | ID: {c.get('id')} | Page: {c.get('page')} | Clause: {c.get('clause')}")
        print(f"Character Length: {len(c.get('text', ''))}")
        snippet = c.get("text", "")
        # Print representation safely for Windows console stdout
        print(f"Text Representation:\n{ascii(snippet)}")
        print("-" * 70)

if __name__ == "__main__":
    main()
