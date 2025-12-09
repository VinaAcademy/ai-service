import re
from io import BytesIO

import pandas as pd
import requests
from docx import Document
from langchain_community.document_loaders import PyPDFLoader


def detect_file_type(file_bytes: bytes) -> str:
    """Detect DOCX or PDF from bytes"""
    if file_bytes.startswith(b"%PDF-"):
        return "pdf"
    elif file_bytes.startswith(b"PK"):
        # DOCX is a zip archive with [Content_Types].xml
        return "docx"
    else:
        raise ValueError("Unsupported file type")


def load_document_to_dataframe(url: str) -> pd.DataFrame:
    """Load DOCX or PDF from URL and chunk into DataFrame"""
    r = requests.get(url)
    r.raise_for_status()
    file_bytes = r.content
    file_type = detect_file_type(file_bytes)

    rows = []

    if file_type == "docx":
        file_like = BytesIO(file_bytes)
        doc = Document(file_like)
        lines = [para.text.strip() for para in doc.paragraphs if para.text.strip()]

        # Chunk like DOCX
        current_chapter = None
        current_section = None
        current_subsection = None
        buffer = []

        def save_content():
            nonlocal buffer, current_chapter, current_section, current_subsection
            text = "\n".join(buffer).strip()
            if text:
                rows.append(
                    [
                        current_chapter or "",
                        current_section or "",
                        current_subsection or "",
                        text,
                    ]
                )
            buffer.clear()

        for line in lines:
            line = line.strip()
            if not line:
                continue
            if line.upper().startswith("CHƯƠNG"):
                save_content()
                current_chapter = line
                current_section = None
                current_subsection = None
                continue
            if re.match(r"^\d+(\.\d+)*\.", line):
                level = len(line.split(".")[:-1])
                save_content()
                if level <= 2:
                    current_section = line
                    current_subsection = None
                else:
                    current_subsection = line
                continue
            buffer.append(line)
        save_content()

    elif file_type == "pdf":
        # Save temp PDF to file
        pdf_path = "temp.pdf"
        with open(pdf_path, "wb") as f:
            f.write(file_bytes)
        loader = PyPDFLoader(pdf_path)
        pages = loader.load()
        for page in pages:
            text = page.page_content.strip()
            if text:
                rows.append(["", "", "", text])

    df = pd.DataFrame(rows, columns=["Chapter", "Section", "Sub_section", "Content"])
    return df
