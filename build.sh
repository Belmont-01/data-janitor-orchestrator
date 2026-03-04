#!/usr/bin/env bash
set -e  # Exit immediately if any command fails

echo "==> Installing system dependencies..."
apt-get update -y && apt-get install -y \
    tesseract-ocr \
    tesseract-ocr-eng \
    poppler-utils \
    libgl1-mesa-glx \
    libglib2.0-0

echo "==> Installing Python dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo "==> Creating required directories..."
mkdir -p data/clean data/raw

echo "==> Build complete!"
