import os
import json
import tempfile
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv, find_dotenv
from errors import PipelineError, FileIngestionError, APIError, InvalidOutputError, AgentTimeoutError

load_dotenv(find_dotenv())

# Fix working directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from orchestrator.boss import run_pipeline

app = Flask(__name__)

ALLOWED_EXTENSIONS = {".csv", ".pdf", ".xlsx", ".xls", ".txt"}


def allowed_file(filename: str) -> bool:
    ext = os.path.splitext(filename)[-1].lower()
    return ext in ALLOWED_EXTENSIONS


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload():
    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file provided."}), 400

    file = request.files["file"]

    if not file.filename:
        return jsonify({"success": False, "error": "No file selected."}), 400

    if not allowed_file(file.filename):
        ext = os.path.splitext(file.filename)[-1].lower()
        return jsonify({
            "success": False,
            "error": f"Unsupported file type: '{ext}'. Supported: .csv, .pdf, .xlsx, .txt"
        }), 400

    # Save uploaded file to a temp location
    suffix = os.path.splitext(file.filename)[-1].lower()
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        file.save(tmp.name)
        tmp_path = tmp.name

    output_dir = "data/clean"

    try:
        run_pipeline(tmp_path, output_dir)

        # Read outputs
        json_path = os.path.join(output_dir, "output.json")
        report_path = os.path.join(output_dir, "report.md")

        clean_json = None
        report_text = None

        if os.path.exists(json_path):
            with open(json_path, "r") as f:
                clean_json = json.load(f)

        if os.path.exists(report_path):
            with open(report_path, "r") as f:
                report_text = f.read()

        return jsonify({
            "success": True,
            "filename": file.filename,
            "clean_json": clean_json,
            "report": report_text
        })

    except FileIngestionError as e:
        return jsonify({"success": False, "error": f"File Error: {e}"}), 422
    except APIError as e:
        return jsonify({"success": False, "error": f"API Error: {e}"}), 502
    except InvalidOutputError as e:
        return jsonify({"success": False, "error": f"Output Error: {e}"}), 500
    except AgentTimeoutError as e:
        return jsonify({"success": False, "error": f"Timeout: {e}"}), 504
    except PipelineError as e:
        return jsonify({"success": False, "error": f"Pipeline Error: {e}"}), 500
    except Exception as e:
        return jsonify({"success": False, "error": f"Unexpected error: {e}"}), 500
    finally:
        # Always clean up the temp file
        if os.path.exists(tmp_path):
            os.remove(tmp_path)


if __name__ == "__main__":
    os.makedirs("data/clean", exist_ok=True)
    os.makedirs("templates", exist_ok=True)
    app.run(debug=True, port=5000)
