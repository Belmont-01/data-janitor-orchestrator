import os
import json
import pandas as pd
import pdfplumber
import pytesseract
from PIL import Image
from pdf2image import convert_from_path
from crewai import Agent, Task, Crew
from agents.llm_config import llm
from errors import FileIngestionError, APIError, InvalidOutputError, AgentTimeoutError

# Point pytesseract to Tesseract installation on Windows
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


# -------------------------------------------------------------------
# STEP 1: File extraction with error handling
# -------------------------------------------------------------------

def extract_from_csv(filepath: str) -> str:
    """Read a CSV and return it as a plain string for the LLM to analyze."""
    try:
        df = pd.read_csv(filepath)
        if df.empty:
            raise FileIngestionError(f"The CSV file is empty: {filepath}")
        return df.to_string(index=False)
    except FileNotFoundError:
        raise FileIngestionError(
            f"CSV file not found: '{filepath}'\n"
            f"Check that the file exists and the path is correct."
        )
    except pd.errors.ParserError as e:
        raise FileIngestionError(f"Could not parse CSV file '{filepath}': {e}")


def is_scanned_pdf(filepath: str) -> bool:
    """
    Check if a PDF is scanned (image-only) or text-based.
    Returns True if scanned, False if text-based.
    A PDF is considered scanned if fewer than 10 characters are extractable per page.
    """
    try:
        with pdfplumber.open(filepath) as pdf:
            total_text = ""
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    total_text += text
            avg_chars = len(total_text) / max(len(pdf.pages), 1)
            return avg_chars < 10  # Less than 10 chars per page = scanned
    except Exception:
        return True  # If we can't read it, assume scanned and try OCR


def extract_from_pdf_text(filepath: str) -> str:
    """Extract text from a standard (non-scanned) PDF using pdfplumber."""
    text = ""
    with pdfplumber.open(filepath) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"
    return text.strip()


def extract_from_pdf_ocr(filepath: str) -> str:
    """
    Extract text from a scanned PDF using OCR.
    Converts each page to an image, then runs Tesseract on it.
    """
    print("🔍 Scanned PDF detected — running OCR (this may take a moment)...")
    try:
        pages = convert_from_path(
            filepath,
            dpi=300,  # Higher DPI = better OCR accuracy
            poppler_path=r"C:\poppler\Library\bin"
        )
    except Exception as e:
        raise FileIngestionError(
            f"Could not convert PDF pages to images: {e}\n"
            f"Make sure Poppler is installed and added to your PATH.\n"
            f"Download from: github.com/oschwartz10612/poppler-windows/releases"
        )

    text = ""
    for i, page_image in enumerate(pages):
        print(f"   OCR processing page {i + 1} of {len(pages)}...")
        page_text = pytesseract.image_to_string(page_image, lang="eng")
        if page_text:
            text += page_text + "\n"

    if not text.strip():
        raise FileIngestionError(
            f"OCR could not extract any text from: '{filepath}'\n"
            f"The PDF may be too low resolution or in an unsupported language."
        )

    print(f"✅ OCR complete — extracted {len(text)} characters.")
    return text.strip()


def extract_from_pdf(filepath: str) -> str:
    """
    Smart PDF extractor — automatically detects whether the PDF is
    text-based or scanned, and uses the right method for each.
    """
    try:
        if is_scanned_pdf(filepath):
            return extract_from_pdf_ocr(filepath)
        else:
            text = extract_from_pdf_text(filepath)
            if not text:
                # Fallback to OCR if text extraction returns nothing
                print("⚠️  Text extraction returned empty — falling back to OCR...")
                return extract_from_pdf_ocr(filepath)
            return text
    except FileIngestionError:
        raise
    except FileNotFoundError:
        raise FileIngestionError(
            f"PDF file not found: '{filepath}'\n"
            f"Check that the file exists and the path is correct."
        )
    except Exception as e:
        raise FileIngestionError(f"Could not read PDF '{filepath}': {e}")


def extract_from_excel(filepath: str) -> str:
    """Read an Excel file and return it as a plain string."""
    try:
        df = pd.read_excel(filepath)
        if df.empty:
            raise FileIngestionError(f"The Excel file is empty: {filepath}")
        return df.to_string(index=False)
    except FileNotFoundError:
        raise FileIngestionError(
            f"Excel file not found: '{filepath}'\n"
            f"Check that the file exists and the path is correct."
        )
    except Exception as e:
        raise FileIngestionError(f"Could not read Excel file '{filepath}': {e}")


def extract_from_txt(filepath: str) -> str:
    """Read a plain text file."""
    try:
        with open(filepath, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
        if not text.strip():
            raise FileIngestionError(f"Text file is empty: {filepath}")
        return text
    except FileNotFoundError:
        raise FileIngestionError(
            f"Text file not found: '{filepath}'\n"
            f"Check that the file exists and the path is correct."
        )


def extract_from_json(filepath: str) -> str:
    """Read a JSON file and return it as a formatted string."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if not data:
            raise FileIngestionError(f'JSON file is empty: {filepath}')
        return json.dumps(data, indent=2)
    except FileNotFoundError:
        raise FileIngestionError(
            f"JSON file not found: '{filepath}'"
            f'Check that the file exists and the path is correct.'
        )
    except json.JSONDecodeError as e:
        raise FileIngestionError(f"Could not parse JSON file '{filepath}': {e}")


def extract_raw_text(filepath: str) -> str:
    """Route to the correct extractor based on file extension."""
    if not os.path.exists(filepath):
        raise FileIngestionError(
            f"File not found: '{filepath}'\n"
            f"Check the path in main.py and make sure the file exists."
        )

    ext = os.path.splitext(filepath)[-1].lower()
    extractors = {
        ".csv":  extract_from_csv,
        ".pdf":  extract_from_pdf,
        ".xlsx": extract_from_excel,
        ".xls":  extract_from_excel,
        ".txt":  extract_from_txt,
        ".json": extract_from_json,
    }

    if ext not in extractors:
        raise FileIngestionError(
            f"Unsupported file type: '{ext}'\n"
            f"Supported types: .csv, .pdf, .xlsx, .xls, .txt, .json"
        )

    return extractors[ext](filepath)


# -------------------------------------------------------------------
# STEP 2: Janitor Agent definition
# -------------------------------------------------------------------

janitor = Agent(
    role="Data Cleaning Specialist",
    goal="Analyze raw data and return a clean, structured JSON object.",
    backstory=(
        "You are a meticulous AI data engineer. You receive raw, messy data "
        "extracted from files like CSVs, PDFs, Excel sheets, and scanned documents. "
        "Your job is to identify issues (missing values, inconsistent formatting, "
        "duplicates) and return a clean, structured JSON array where every record "
        "is consistent and well-formed."
    ),
    llm=llm,
    verbose=True
)


# -------------------------------------------------------------------
# STEP 3: Standalone runner (for testing Janitor on its own)
# -------------------------------------------------------------------

def run_janitor(filepath: str, output_path: str = "data/clean/output.json"):
    """Standalone Janitor runner. Useful for testing without the full pipeline."""
    print(f"\n📂 Reading file: {filepath}")

    raw_text = extract_raw_text(filepath)
    print(f"✅ Extracted {len(raw_text)} characters of raw text.")
    print("🤖 Sending to Janitor Agent...\n")

    task = Task(
        description=(
            f"You have been given the following raw data extracted from a file:\n\n"
            f"---\n{raw_text}\n---\n\n"
            "Please do the following:\n"
            "1. Identify any data quality issues (missing fields, bad formatting, duplicates).\n"
            "2. Clean and standardize the data.\n"
            "3. Return ONLY a valid JSON array of cleaned records. "
            "No explanation, no markdown, just raw JSON."
        ),
        expected_output="A valid JSON array of cleaned records.",
        agent=janitor
    )

    try:
        crew = Crew(agents=[janitor], tasks=[task])
        result = crew.kickoff()
    except TimeoutError:
        raise AgentTimeoutError(
            "The Janitor agent timed out. Try reducing the size of your input file, "
            "or increase max_rpm in llm_config.py."
        )
    except Exception as e:
        error_msg = str(e).lower()
        if any(k in error_msg for k in ["404", "api", "quota", "rate limit", "authentication"]):
            raise APIError(
                f"Gemini API error: {e}\n"
                f"Check your GOOGLE_API_KEY in .env and your API quota."
            )
        raise

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    try:
        result_str = str(result).strip()
        result_str = result_str.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        cleaned_data = json.loads(result_str)
        with open(output_path, "w") as f:
            json.dump(cleaned_data, f, indent=2)
        print(f"\n✅ Clean JSON saved to: {output_path}")
    except json.JSONDecodeError:
        raw_output_path = output_path.replace(".json", "_raw.txt")
        with open(raw_output_path, "w") as f:
            f.write(str(result))
        raise InvalidOutputError(
            f"The Janitor returned output that isn't valid JSON.\n"
            f"Raw output saved to: {raw_output_path}\n"
            f"Tip: Open that file and check what the LLM returned."
        )

    return result
