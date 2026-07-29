import re
import fitz  # PyMuPDF
from typing import List, Dict, Any

# Pattern for detecting clause headers and section boundaries
CLAUSE_PATTERN = re.compile(
    r'(?=(\n|^)(?:'
    r'[0-9]+[\.\)]|'                  # 1. or 1)
    r'[०-९]+[\.\)]|'                  # Devanagari 1. or 1)
    r'\([0-9]+\)|'                    # (1)
    r'\([०-९]+\)|'                    # Devanagari (1)
    r'ANNEXURE\s*[-–—]?\s*[I|V|X|0-9]+|' # ANNEXURE-I
    r'अनेक्सचर\s*[-–—]?\s*[I|V|X|0-9|०-९]+|' # अनेक्सचर-I
    r'प्रकरण\s*[:\.]?|'               # प्रकरण:
    r'शर्तें\s*[:\.]?|'                # शर्तें:
    r'पात्रता\s*[:\.]?|'               # पात्रता:
    r'उद्देश्य\s*[:\.]?'               # उद्देश्य:
    r'))',
    re.IGNORECASE
)

ANNEXURE_HEADER = re.compile(
    r'^(?:ANNEXURE\s*[-–—]?\s*[I|V|X|0-9]+|अनेक्सचर\s*[-–—]?\s*[I|V|X|0-9|०-९]+)',
    re.IGNORECASE
)

def extract_text_by_pages(pdf_path: str) -> List[Dict[str, Any]]:
    """Extract page-wise text from PDF using PyMuPDF."""
    doc = fitz.open(pdf_path)
    pages = []
    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text("text")
        if text.strip():
            pages.append({"page": page_num + 1, "text": text})
    return pages

def clean_ocr_text(text: str) -> str:
    """Normalize common Hindi OCR artifacts and formatting irregularities."""
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r'(\d+)\s+[\.]\s+', r'\1. ', text)
    text = re.sub(r'([०-९]+)\s+[\.]\s+', r'\1. ', text)
    return text.strip()

def split_into_clauses(text: str) -> List[str]:
    """Split page/document text into clause blocks."""
    cleaned = clean_ocr_text(text)
    splits = CLAUSE_PATTERN.split(cleaned)
    blocks = [s.strip() for s in splits if s and s.strip()]
    
    merged_blocks = []
    for b in blocks:
        # Merge tiny fragments (<30 chars) ONLY if they are not Annexure headers
        is_annexure = bool(ANNEXURE_HEADER.search(b))
        if merged_blocks and len(b) < 30 and not CLAUSE_PATTERN.match(b) and not is_annexure:
            merged_blocks[-1] += "\n" + b
        else:
            merged_blocks.append(b)
    return merged_blocks if merged_blocks else [cleaned]

def chunk_text(
    pages: List[Dict[str, Any]], 
    max_chunk_chars: int = 500, 
    overlap_chars: int = 100
) -> List[Dict[str, Any]]:
    """
    Chunk extracted pages respecting clause structure AND forcing standalone chunks for Annexures.
    Target ~200-300 tokens (approx 400-600 chars) per clause chunk.
    """
    chunks = []
    chunk_id_counter = 0

    for page_data in pages:
        page_num = page_data["page"]
        page_text = page_data["text"]
        clauses = split_into_clauses(page_text)

        current_chunk = ""
        clause_ref = None

        for clause in clauses:
            is_annexure = bool(ANNEXURE_HEADER.search(clause))

            match = re.match(
                r'^([0-9०-९]+[\.\)]|\([0-9०-९]+\)|ANNEXURE\s*[-–—]?\s*[I|V|X|0-9]+|अनेक्सचर\s*[-–—]?\s*[I|V|X|0-9]+)',
                clause,
                re.I
            )
            if match:
                clause_ref = match.group(1)

            # FORCE NEW CHUNK if clause is an Annexure or if adding it exceeds max_chunk_chars
            if is_annexure:
                # Flush existing accumulated chunk first
                if current_chunk.strip():
                    chunks.append({
                        "id": f"chunk_{chunk_id_counter}",
                        "text": current_chunk.strip(),
                        "page": page_num,
                        "clause": clause_ref or "general"
                    })
                    chunk_id_counter += 1
                    current_chunk = ""

                # Push Annexure as an isolated standalone chunk
                chunks.append({
                    "id": f"chunk_{chunk_id_counter}",
                    "text": clause.strip(),
                    "page": page_num,
                    "clause": clause_ref or "annexure"
                })
                chunk_id_counter += 1
                continue

            if len(current_chunk) + len(clause) <= max_chunk_chars:
                if current_chunk:
                    current_chunk += "\n\n" + clause
                else:
                    current_chunk = clause
            else:
                if current_chunk.strip():
                    chunks.append({
                        "id": f"chunk_{chunk_id_counter}",
                        "text": current_chunk.strip(),
                        "page": page_num,
                        "clause": clause_ref or "general"
                    })
                    chunk_id_counter += 1
                current_chunk = clause

        if current_chunk.strip():
            chunks.append({
                "id": f"chunk_{chunk_id_counter}",
                "text": current_chunk.strip(),
                "page": page_num,
                "clause": clause_ref or "general"
            })
            chunk_id_counter += 1

    return chunks

def parse_pdf_to_chunks(pdf_path: str) -> List[Dict[str, Any]]:
    """Main entry point to parse a PDF file into isolated clause and annexure chunks."""
    pages = extract_text_by_pages(pdf_path)
    if not pages:
        return []
    return chunk_text(pages)
