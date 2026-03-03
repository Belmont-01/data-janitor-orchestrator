#!/usr/bin/env bash
# Install system dependencies for OCR
apt-get update && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    libgl1

# Install Python dependencies
pip install -r requirements.txt
