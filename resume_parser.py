"""
resume_parser.py
================
Core parsing utilities for the Resume Optimizer application.

Provides functions to:
  - Extract raw text from PDF files
  - Parse contact information (email, phone) via regex
  - Guess the applicant's name from the top lines of the resume
  - Detect skills using exact and fuzzy matching with synonym expansion
  - Extract meaningful keywords directly from a job description
  - Compare detected skills against a job description

Typical usage (from app.py):
    from resume_parser import (
        extract_text_from_pdf, extract_contact_info,
        extract_skills, extract_name, compare_skills,
        extract_keywords_from_job, SKILLS,
    )
"""

import re
import difflib
import string
from collections import Counter
from typing import Optional

from PyPDF2 import PdfReader


# ── Stop-word list ─────────────────────────────────────────────────────────────
# Common English words that carry no meaningful signal in a job description.
# Keywords are built by removing these from the job text, so anything that
# remains is likely a skill, tool, or domain term worth comparing against.
STOP_WORDS: set[str] = {
    "a", "an", "the", "and", "or", "but", "if", "in", "on", "at", "to",
    "for", "of", "with", "by", "from", "as", "is", "was", "are", "were",
    "be", "been", "being", "have", "has", "had", "do", "does", "did",
    "will", "would", "could", "should", "may", "might", "must", "shall",
    "not", "no", "nor", "so", "yet", "both", "either", "neither", "each",
    "than", "too", "very", "just", "about", "above", "after", "also",
    "any", "because", "before", "between", "during", "here", "how",
    "into", "more", "other", "our", "out", "over", "same", "such",
    "that", "their", "them", "then", "there", "these", "they", "this",
    "those", "through", "under", "up", "use", "used", "using", "we",
    "what", "when", "where", "which", "while", "who", "whose", "why",
    "within", "without", "work", "you", "your",
    # Generic job-posting filler that adds no skill signal
    "role", "team", "years", "year", "experience", "ability", "strong",
    "good", "great", "excellent", "including", "plus", "preferred",
    "required", "responsibilities", "qualifications", "candidate",
    "opportunity", "position", "join", "looking", "help", "ensure",
    "knowledge", "understanding", "familiarity", "proficiency",
    "minimum", "equivalent", "related", "relevant", "demonstrate",
    "across", "support", "develop", "build", "create", "manage",
    "provide", "make", "work", "working", "responsible",
}


# ── Skill catalog ──────────────────────────────────────────────────────────────
# Add or remove entries here to expand / shrink the recognized skill set.
# Skills are matched case-insensitively, so keep them lower-case.
SKILLS: list[str] = [
    "python", "java", "c++", "sql", "excel",
    "machine learning", "deep learning", "data analysis",
    "pandas", "numpy", "tensorflow", "pytorch", "statistics",
    "communication", "project management", "leadership",
    "git", "linux", "data",
]

# ── Synonym / abbreviation map ─────────────────────────────────────────────────
# Keys   → abbreviations or alternate spellings found in real resumes.
# Values → canonical forms used in SKILLS (or meaningful expansions).
# These are substituted into the resume text before skill matching begins.
SYNONYMS: dict[str, str] = {
    "ml":           "machine learning",
    "dl":           "deep learning",
    "js":           "javascript",
    "aws":          "amazon web services",
    "ai":           "artificial intelligence",
    "nlp":          "natural language processing",
    "cv":           "computer vision",
    "data viz":     "data visualization",
    "big data":     "big data technologies",
    "python 3":     "python",
    "py":           "python",
    "np":           "numpy",
    "pd":           "pandas",
    "ts":           "tensorflow",
    "pt":           "pytorch",
    "git":          "git version control",
    "sql":          "sql database",
    "sql database": "structured query language",
}


# ── PDF text extraction ────────────────────────────────────────────────────────

def extract_text_from_pdf(file_path: str) -> str:
    """Read every page of a PDF and return all text as a single string.

    Args:
        file_path: Absolute or relative path to the PDF file.

    Returns:
        Concatenated text from all pages, separated by newlines.
        Returns an empty string if no text could be extracted.
    """
    reader = PdfReader(file_path)
    pages: list[str] = []

    for page in reader.pages:
        content = page.extract_text()
        if content:
            pages.append(content)

    return "\n".join(pages)


# ── Name extraction ────────────────────────────────────────────────────────────

def extract_name(text: str) -> str:
    """Heuristically guess the applicant's name from the top of the resume.

    Strategy: scan the first 5 non-empty lines and return the first line
    whose words are all title-cased and whose word count is 2–3
    (typical for "First Last" or "First Middle Last").

    Args:
        text: Raw resume text.

    Returns:
        The guessed name string, or "Not found" if no candidate line is detected.
    """
    lines = text.strip().split("\n")

    for line in lines[:5]:
        words = line.strip().split()
        # A name is 2–3 words where every word starts with an uppercase letter
        if 2 <= len(words) <= 3 and all(w[0].isupper() for w in words):
            return line.strip()

    return "Not found"


# ── Contact-info extraction ────────────────────────────────────────────────────

def extract_contact_info(text: str) -> dict[str, str]:
    """Extract the first email address and phone number found in the text.

    Regex patterns:
      Email — standard RFC-5322-style pattern.
      Phone — supports US formats with optional country code:
              +1 (555) 555-5555  ·  555.555.5555  ·  5555555555

    Args:
        text: Raw resume text (any case).

    Returns:
        Dict with keys "email" and "phone"; value is "Not found" when absent.
    """
    email_pattern = r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+"
    phone_pattern = r"(\+?\d{1,2}[\s\-]?)?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{4}"

    email_match = re.search(email_pattern, text)
    phone_match = re.search(phone_pattern, text)

    return {
        "email": email_match.group() if email_match else "Not found",
        "phone": phone_match.group() if phone_match else "Not found",
    }


# ── Skill extraction ───────────────────────────────────────────────────────────

def extract_skills(
    text: str,
    skill_list: list[str],
    threshold: float = 0.80,
) -> list[str]:
    """Detect skills present in *text* using exact and fuzzy matching.

    Algorithm:
      1. Lower-case the text and expand known abbreviations via SYNONYMS.
      2. For each skill in *skill_list*:
         a. Multi-word skills → try exact substring first; if not found,
            fuzzy-match against every n-gram of the same word-length.
         b. Single-word skills → fuzzy-match against individual tokens.
      3. A fuzzy match is accepted when its similarity ratio ≥ *threshold*.

    Args:
        text:       Raw resume text (any case).
        skill_list: Canonical list of skills to search for.
        threshold:  Minimum similarity ratio for a fuzzy match (0.0–1.0).
                    Higher values mean stricter matching.

    Returns:
        Sorted list of matched skill names (canonical casing from *skill_list*).
    """
    found: set[str] = set()
    text_lower = text.lower()

    # Step 1 — expand synonyms / abbreviations before tokenizing
    for abbr, canonical in SYNONYMS.items():
        text_lower = re.sub(rf"\b{re.escape(abbr)}\b", canonical, text_lower)

    tokens = text_lower.split()

    for skill in skill_list:
        skill_lower = skill.lower()
        skill_words = skill_lower.split()
        n = len(skill_words)

        if n > 1:
            # ── Multi-word skill ─────────────────────────────────────────────
            # Fast path: plain substring match
            if skill_lower in text_lower:
                found.add(skill)
                continue
            # Slow path: fuzzy matching over every n-gram in the token list
            ngrams = [" ".join(tokens[i : i + n]) for i in range(len(tokens) - n + 1)]
            if difflib.get_close_matches(skill_lower, ngrams, n=1, cutoff=threshold):
                found.add(skill)
        else:
            # ── Single-word skill ────────────────────────────────────────────
            if difflib.get_close_matches(skill_lower, tokens, n=1, cutoff=threshold):
                found.add(skill)

    return sorted(found)


# ── Job keyword extraction ────────────────────────────────────────────────────

def extract_keywords_from_job(
    job_text: str,
    top_n: int = 20,
    min_length: int = 3,
) -> list[tuple[str, int]]:
    """Extract the most meaningful keywords from a job description automatically.

    Works entirely from the uploaded text — no manual input required.

    Algorithm:
      1. Lower-case and strip punctuation from the job text.
      2. Tokenize into individual words.
      3. Remove stop words (common English words + generic job-posting filler).
      4. Drop tokens shorter than *min_length* characters.
      5. Count how often each remaining token appears.
      6. Return the top *top_n* terms ranked by frequency.

    Frequency matters because recruiters repeat the things they care most
    about — a word that appears 8 times is almost certainly a core requirement,
    whereas a word that appears once might just be context.

    Args:
        job_text:   Raw or lower-cased job description text.
        top_n:      Maximum number of keywords to return (default 20).
        min_length: Minimum character length for a token to be kept (default 3).

    Returns:
        List of (keyword, count) tuples sorted by count descending.
        e.g. [("python", 7), ("kubernetes", 4), ("agile", 3), ...]
    """
    # Normalise: lower-case and strip punctuation
    text_lower = job_text.lower()
    text_clean = text_lower.translate(str.maketrans("", "", string.punctuation))

    # Tokenise and filter
    tokens = [
        word for word in text_clean.split()
        if word not in STOP_WORDS and len(word) >= min_length
    ]

    # Rank by frequency and return the top N
    counts = Counter(tokens)
    return counts.most_common(top_n)


def match_keywords_to_resume(
    keywords: list[tuple[str, int]],
    resume_text: str,
) -> dict:
    """Check which extracted job keywords appear in the resume.

    Args:
        keywords:    Output of extract_keywords_from_job() — (word, count) pairs.
        resume_text: Raw resume text (any case).

    Returns:
        Dict with keys:
          "found"   — keywords present in the resume (sorted by frequency).
          "missing" — keywords absent from the resume (sorted by frequency).
          "score"   — percentage of job keywords found on the resume (int).
    """
    resume_lower = resume_text.lower()

    found   = [(kw, cnt) for kw, cnt in keywords if kw in resume_lower]
    missing = [(kw, cnt) for kw, cnt in keywords if kw not in resume_lower]

    score = round(len(found) / len(keywords) * 100) if keywords else 0

    return {
        "found":   found,
        "missing": missing,
        "score":   score,
    }


# ── Job-description file loader ────────────────────────────────────────────────

def load_job_description(file_path: str) -> str:
    """Read a plain-text job description from disk and return it lower-cased.

    Args:
        file_path: Path to the .txt job description file.

    Returns:
        Lower-cased file contents as a single string.
    """
    with open(file_path, "r", encoding="utf-8") as fh:
        return fh.read().lower()


# ── Skill comparison ───────────────────────────────────────────────────────────

def compare_skills(
    resume_skills: list[str],
    job_text: str,
    skill_list: list[str],
) -> dict:
    """Compare resume skills against the skills required by a job description.

    Determines which skills from *skill_list* appear in the job description,
    then partitions *resume_skills* into matched and missing sets.

    Args:
        resume_skills: Skills extracted from the applicant's resume.
        job_text:      Lower-cased job description text.
        skill_list:    Master list of recognized skills.

    Returns:
        Dict with three keys:
          "matched_skills" — skills on the resume that the job requires.
          "missing_skills" — skills the job requires that are absent from resume.
          "match_score"    — percentage of required skills that are matched (int).
    """
    # Identify which catalog skills the job posting actually mentions
    required = [s for s in skill_list if s.lower() in job_text]

    matched = [s for s in resume_skills if s in required]
    missing = [s for s in required if s not in resume_skills]

    # Guard against division by zero when no known skills appear in the posting
    score = round(len(matched) / len(required) * 100) if required else 0

    return {
        "matched_skills": matched,
        "missing_skills": missing,
        "match_score":    score,
    }


# ── CLI test harness ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Quick sanity-check: run the full pipeline against sample data files.
    # This block is skipped when resume_parser is imported as a module.

    RESUME_FILE = "data/sample_resume2.pdf"
    JOB_FILE    = "data/sample_job.txt"

    try:
        raw_text = extract_text_from_pdf(RESUME_FILE)
        print("✅ PDF loaded successfully!\n")

        contact_info = extract_contact_info(raw_text)
        print(f"📫 Contact Info:\n  {contact_info}\n")

        name = extract_name(raw_text)
        print(f"🧑‍💼 Name Guess:\n  {name}\n")

        skills = extract_skills(raw_text, SKILLS)
        print(f"🛠️  Skills Found:\n  {skills}\n")

        job_text  = load_job_description(JOB_FILE)
        job_match = compare_skills(skills, job_text, SKILLS)

        print("📋 Job Match Analysis:")
        print(f"  ✅ Matched : {job_match['matched_skills']}")
        print(f"  ❌ Missing : {job_match['missing_skills']}")
        print(f"  📈 Score   : {job_match['match_score']}%")

    except FileNotFoundError as exc:
        print(f"❌ File not found: {exc}")
