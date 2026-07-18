# AI-Assisted Plant Genetic Purity Testing System

An AI-driven computer vision and morphological analysis application designed to predict the genetic purity of germinated plant specimens (classifying them as **Female**, **Hybrid**, or **Male**). 

The system combines a deep convolutional neural network (MobileNet) with traditional computer vision morphological heuristic rules to deliver precise classifications, accompanied by a premium web dashboard interface.

---

## 🚀 Key Features

* **High-Accuracy Classification**: Uses a trained MobileNet model to categorize plant leaves/stems.
* **Morphological Validation**: Pre-filters uploads using OpenCV to reject synthetic drawings, documents (IDs, text sheets), and non-plant backgrounds.
* **Heuristic Rules & Overrides**: Incorporates biological rules (e.g., hypocotyl pigmentation, stem area contours, aspect ratios) to refine predictions.
* **Warmed-up Instant Inference**: Direct in-memory Flask-to-Model prediction pipeline (optimizing response times from ~15s to **under 0.4s**).
* **Interactive Dashboard**: Sleek web interface with drag-and-drop file upload, real-time Chart.js doughnut metrics, and class confidence bars.

---

## 📁 Repository Structure

```text
├── webUI/
│   ├── app.py              # Flask server (model preloaded & warmed up on startup)
│   ├── detect.py           # Standalone prediction and validation logic
│   ├── requirements.txt    # Project dependencies
│   ├── static/             # Frontend assets (CSS styling, Chart.js logic)
│   ├── templates/          # HTML Templates (Interactive dashboard UI)
│   └── uploads/            # Upload directory
│       └── model.keras     # Trained 16MB MobileNet model weights
```

---

## 🛠️ Setup & Installation

### Prerequisites
Make sure you have **Python 3.10+** installed.

### 1. Install Dependencies
Install all required libraries using the requirements file:
```bash
pip install -r webUI/requirements.txt
```
*(Note: OpenCV and Pillow require native headers installed automatically via pip)*

### 2. Run the Web Interface
Start the local development server:
```bash
python webUI/app.py
```
Open your browser and navigate to `http://127.0.0.1:5000` to access the interactive dashboard.

---

## 💻 CLI Inference Usage

You can also run inference directly on any image from your terminal:
```bash
python webUI/detect.py path/to/your/image.png
```

This will run structural validation, morphology filters, deep learning inference, and print a formatted decision report directly to standard output before displaying the result in a Matplotlib pop-up.

---

## ⚡ Performance Optimization

Previously, the web interface spawned `detect.py` in a separate process for every click, leading to a slow 12–15 second wait as Python initialized TensorFlow and loaded the Keras model.

### Refactored Architecture
* **Startup Pre-loading**: `model.keras` is loaded once when the Flask server starts.
* **TensorFlow Warmup**: A dummy inference request is triggered on startup to compile TensorFlow execution paths.
* **In-Memory Prediction**: The Flask request handler (`/predict`) now imports the `detect` module and calls its prediction function directly in-memory, avoiding subprocess overhead entirely.
* **Result**: Average prediction latency reduced to **0.32 seconds** (~40x faster).
