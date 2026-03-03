# 📝 Resume Optimizer

An AI-assisted Streamlit app that parses your resume, extracts skills, and compares them against a job description, giving you an instant match score and a list of missing skills to work on.

> 🤖 Built with the assistance of Claude (Anthropic)

---

## ✨ Features

- **PDF resume parsing** — extracts raw text using PyPDF2
- **Contact info extraction** — finds your name, email, and phone number via regex
- **Smart skill detection** — uses exact and fuzzy matching plus synonym expansion (e.g. `ml` → `machine learning`)
- **Job description comparison** — works with both PDF and TXT job postings
- **Match score** — shows a 0–100% score with a color-coded progress bar
- **JSON export** — download your full analysis in one click

---

## 🚀 Getting Started

### 1. Clone the repository

```bash
git clone https://github.com/your-username/resume-optimizer.git
cd resume-optimizer
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv
source venv/bin/activate      # macOS / Linux
venv\Scripts\activate         # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the app

```bash
streamlit run app.py
```

Then open [http://localhost:8501](http://localhost:8501) in your browser.

---

## 🗂️ Project Structure

```
resume-optimizer/
├── app.py              # Streamlit front-end
├── resume_parser.py    # Core parsing & analysis logic
├── requirements.txt    # Python dependencies
├── data/               # Sample resumes and job descriptions
│   ├── sample_resume.pdf
│   ├── sample_resume2.pdf
│   ├── sample_job.txt
│   └── sample-job-description.pdf
└── README.md
```

---

## ⚙️ How It Works

1. **Upload** your resume (PDF) and a job description (PDF or TXT)
2. The app extracts text from both files using `PyPDF2`
3. Your resume is scanned for skills using:
   - Synonym expansion (abbreviations like `py` → `python`)
   - Exact substring matching for multi-word skills
   - Fuzzy matching (via `difflib`) for typos and slight variations
4. Detected skills are compared against the skills mentioned in the job description
5. You get a **match score**, a list of **matched skills**, and a list of **missing skills**

---

## 🛠️ Extending the Skill Set

Open `resume_parser.py` and edit the `SKILLS` list or `SYNONYMS` dict:

```python
SKILLS = [
    "python", "sql", "machine learning",
    # add your own skills here ↓
    "react", "docker", "kubernetes",
]

SYNONYMS = {
    "k8s": "kubernetes",   # add abbreviations here
}
```

---

## 🧪 Running the Parser Standalone

To test the parser without launching the Streamlit app:

```bash
python resume_parser.py
```

This runs a full pipeline against the sample files in `data/`.

---

## 📦 Dependencies

| Package     | Purpose                        |
|-------------|-------------------------------|
| streamlit   | Web app framework              |
| PyPDF2      | PDF text extraction            |
| difflib     | Fuzzy string matching (stdlib) |
| re          | Regex for email / phone (stdlib)|

---

## 📄 License

MIT — free to use, modify, and distribute.
