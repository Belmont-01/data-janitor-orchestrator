# 🧹 Data Janitor & Orchestrator

> A multi-agent AI pipeline that transforms messy, unstructured files into clean structured data and professional business reports — automatically.

**Built by RYAN KYALO** · © 2026 · [MIT License](./LICENSE)

---

## What It Does

Most real-world data is messy — inconsistent formats, missing values, scanned PDFs, chaotic spreadsheets. This project solves that with a three-agent AI pipeline:

```
Your File → 🧹 Janitor → 🔍 Researcher → ✍️ Writer → Clean JSON + Report
```

| Agent | Role |
|-------|------|
| **Janitor** | Reads raw files, fixes formatting issues, outputs clean structured JSON |
| **Researcher** | Analyzes the clean data for patterns, trends, and anomalies |
| **Writer** | Produces a professional business summary report in markdown |

---

## Supported File Types

- **CSV** — messy spreadsheets with inconsistent formatting
- **PDF** — text-based PDFs and reports
- **Excel (.xlsx / .xls)** — multi-sheet workbooks
- **Text (.txt)** — raw unstructured text data

---

## Tech Stack

- **Python 3.12**
- **CrewAI** — multi-agent orchestration
- **Google Gemini 2.0 Flash** — the LLM powering all agents
- **Flask** — web server and REST API
- **pandas / pdfplumber / openpyxl** — file extraction
- **HTML / CSS / JS** — drag-and-drop frontend UI

---

## Project Structure

```
project-x/
├── app.py                  # Flask web server
├── main.py                 # Terminal runner (no UI)
├── errors.py               # Custom error handling
├── templates/
│   └── index.html          # Drag-and-drop web UI
├── agents/
│   ├── llm_config.py       # Shared LLM configuration
│   ├── janitor.py          # ETL Agent
│   ├── researcher.py       # Analysis Agent
│   └── writer.py           # Report Writer Agent
├── orchestrator/
│   └── boss.py             # Orchestrator (sequential pipeline)
├── data/
│   ├── raw/                # Place input files here
│   └── clean/              # Outputs: output.json + report.md
├── requirements.txt
└── .env                    # Your API keys (never committed)
```

---

## Getting Started

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/data-janitor-orchestrator.git
cd data-janitor-orchestrator
```

### 2. Create a virtual environment
```bash
python -m venv .venv
.venv\Scripts\Activate.ps1   # Windows
source .venv/bin/activate     # Mac/Linux
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up your API key
Create a `.env` file in the root of the project:
```
GOOGLE_API_KEY=your_gemini_api_key_here
```
Get a free Gemini API key at [aistudio.google.com](https://aistudio.google.com)

### 5. Run the web app
```bash
python app.py
```
Then open **http://localhost:5000** in your browser.

### 6. Or run from the terminal
```bash
python main.py
```

---

## How to Use

1. Open `http://localhost:5000`
2. Drag and drop a CSV, PDF, Excel, or TXT file onto the upload area
3. Click **Run Pipeline**
4. Watch the agents work in the live log
5. View your clean JSON and business report in the results panel

---

## Error Handling

The pipeline handles all common failure modes gracefully:

| Error Type | What It Means | What Happens |
|------------|--------------|--------------|
| `FileIngestionError` | File not found, empty, or unsupported type | Clear message + suggested fix |
| `APIError` | Gemini API quota or key issue | Prompts you to check your key |
| `InvalidOutputError` | LLM returned malformed output | Raw output saved for inspection |
| `AgentTimeoutError` | Agent took too long to respond | Suggests reducing file size |

---

## Roadmap

- [ ] Support for scanned PDFs (OCR via pytesseract)
- [ ] Deploy to the web (Railway / Render)
- [ ] Download buttons for JSON and report outputs
- [ ] Support for multiple files in one run
- [ ] Authentication for multi-user deployment

---

## License

Copyright (c) 2026 [RYAN KYALO]

This project is licensed under the MIT License — see [LICENSE](./LICENSE) for details.

You are free to use, modify, and distribute this software, but you must include
the original copyright notice and give credit to the original author.
