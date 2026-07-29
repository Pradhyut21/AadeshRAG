import re
import fitz  # PyMuPDF

CLAUSE_PATTERN = re.compile(
    r'(?=(\n|^)(?:'
    r'[0-9]+[\.\)]|'
    r'[०-९]+[\.\)]|'
    r'\([0-9]+\)|'
    r'\([०-९]+\)|'
    r'ANNEXURE\s*[-–—]?\s*[I|V|X|0-9]+|'
    r'अनेक्सचर\s*[-–—]?\s*[I|V|X|0-9|०-९]+|'
    r'प्रकरण\s*[:\.]?|'
    r'शर्तें\s*[:\.]?|'
    r'पात्रता\s*[:\.]?|'
    r'उद्देश्य\s*[:\.]?'
    r'))',
    re.IGNORECASE
)

ANNEXURE_HEADER = re.compile(
    r'^(?:ANNEXURE\s*[-–—]?\s*[I|V|X|0-9]+|अनेक्सचर\s*[-–—]?\s*[I|V|X|0-9|०-९]+)',
    re.IGNORECASE
)

def clean_ocr_text(text: str) -> str:
    """Clean extracted text by removing null bytes, normalizing whitespace and clause numbering."""
    text = text.replace('\x00', '').replace('\0', '')
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'(\d+)\s+[\.]\s+', r'\1. ', text)
    text = re.sub(r'([०-९]+)\s+[\.]\s+', r'\1. ', text)
    return text.strip()

def parse_pdf_to_chunks(pdf_path: str, max_chunk_chars: int = 500) -> list:
    """
    Clause-aware PDF chunker that splits on numbered clauses (1., 2., 3. ...)
    and forces standalone chunk boundaries on ANNEXURE-I / ANNEXURE-II sections.
    """
    doc = fitz.open(pdf_path)
    chunks = []
    chunk_counter = 0

    for page_num in range(len(doc)):
        page_text = clean_ocr_text(doc[page_num].get_text("text"))
        splits = CLAUSE_PATTERN.split(page_text)
        clauses = [clean_ocr_text(s) for s in splits if s and s.strip()]

        current_chunk = ""
        clause_ref = None

        for clause in clauses:
            is_annexure = bool(ANNEXURE_HEADER.search(clause))
            match = re.match(r'^([0-9०-९]+[\.\)]|\([0-9०-९]+\)|ANNEXURE\s*[-–—]?\s*[I|V|X|0-9]+|अनेक्सचर\s*[-–—]?\s*[I|V|X|0-9]+)', clause, re.I)
            if match:
                clause_ref = match.group(1)

            if is_annexure:
                if current_chunk.strip():
                    chunks.append({
                        "id": f"chunk_{chunk_counter}",
                        "text": current_chunk.strip(),
                        "page": page_num + 1,
                        "clause": clause_ref or "general"
                    })
                    chunk_counter += 1
                    current_chunk = ""
                chunks.append({
                    "id": f"chunk_{chunk_counter}",
                    "text": clause.strip(),
                    "page": page_num + 1,
                    "clause": clause_ref or "annexure"
                })
                chunk_counter += 1
                continue

            if len(current_chunk) + len(clause) <= max_chunk_chars:
                current_chunk = (current_chunk + "\n\n" + clause).strip() if current_chunk else clause
            else:
                if current_chunk.strip():
                    chunks.append({
                        "id": f"chunk_{chunk_counter}",
                        "text": current_chunk.strip(),
                        "page": page_num + 1,
                        "clause": clause_ref or "general"
                    })
                    chunk_counter += 1
                current_chunk = clause

        if current_chunk.strip():
            chunks.append({
                "id": f"chunk_{chunk_counter}",
                "text": current_chunk.strip(),
                "page": page_num + 1,
                "clause": clause_ref or "general"
            })
            chunk_counter += 1

    return chunks
