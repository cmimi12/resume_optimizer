"""
app.py
======
Resume Optimizer — Streamlit front-end.

Upload your resume (PDF) and a job description (PDF or TXT) to:
  • Automatically extract keywords from the job description
  • See which keywords your resume already covers
  • Get a keyword match score and a list of missing terms to add
  • Download the full analysis as a JSON file

Run locally:
    streamlit run app.py
"""

import json
import os
import tempfile

import streamlit as st

from resume_parser import (
    extract_keywords_from_job,
    extract_text_from_pdf,
    match_keywords_to_resume,
)


# ── Page configuration ────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Resume Optimizer",
    page_icon="📝",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── Sidebar: instructions & controls ──────────────────────────────────────────
with st.sidebar:
    st.title("Resume Optimizer")
    st.markdown(
        """
        **How to use:**
        1. Upload your **resume** as a PDF
        2. Upload the **job description** (PDF or TXT)
        3. Review your keyword match score and gaps
        4. Download the full analysis as JSON

        ---
        Built with [Streamlit](https://streamlit.io) · AI-assisted 🤖
        """
    )
    st.divider()

    # Let the user control how many keywords get extracted from the job posting
    top_n = st.slider(
        "Keywords to extract from job description",
        min_value=5,
        max_value=40,
        value=20,
        step=5,
        help="How many of the top keywords to pull from the job posting.",
    )

    st.divider()
    st.caption(
        "Keywords are extracted automatically by frequency after removing "
        "common English filler words. Higher frequency = the employer "
        "repeated it more = likely more important."
    )


# ── Cached helpers ────────────────────────────────────────────────────────────
# @st.cache_data means Streamlit skips re-parsing the same file on every
# UI interaction — results are reused until the uploaded file changes.

@st.cache_data(show_spinner=False)
def cached_pdf_to_text(file_bytes: bytes) -> str:
    """Write *file_bytes* to a temp file, extract its text, then delete it.

    Using a temp file avoids polluting the working directory and guarantees
    cleanup even if extraction raises an exception.
    """
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    try:
        return extract_text_from_pdf(tmp_path)
    finally:
        os.unlink(tmp_path)  # always clean up, success or failure


@st.cache_data(show_spinner=False)
def cached_extract_keywords(job_text: str, top_n: int) -> list[tuple[str, int]]:
    """Cache keyword extraction — re-runs only if the job text or top_n changes."""
    return extract_keywords_from_job(job_text, top_n=top_n)


# ── Page header ───────────────────────────────────────────────────────────────
st.title("Resume Optimizer")
st.caption("Upload your resume and a job description to see how well you match.")

st.divider()

# ── File upload widgets (side by side) ────────────────────────────────────────
col_left, col_right = st.columns(2)

with col_left:
    resume_file = st.file_uploader("📄 Upload your resume (PDF)", type=["pdf"])

with col_right:
    job_file = st.file_uploader("📋 Upload job description (PDF or TXT)", type=["txt", "pdf"])

# Hold until both files are present
if not (resume_file and job_file):
    st.info("⬆️  Upload both files above to get started.", icon="💡")
    st.stop()


# ── Parse & analyse ───────────────────────────────────────────────────────────
with st.spinner("Analysing your resume…"):
    try:
        # Extract text from the resume PDF
        raw_text = cached_pdf_to_text(resume_file.getvalue())

        # Extract text from the job description (PDF or plain TXT)
        job_bytes = job_file.getvalue()
        if job_file.name.lower().endswith(".pdf"):
            job_text = cached_pdf_to_text(job_bytes).lower()
        else:
            job_text = job_bytes.decode("utf-8").lower()

        # Pull top keywords from the job description, then check the resume
        job_keywords    = cached_extract_keywords(job_text, top_n)
        keyword_results = match_keywords_to_resume(job_keywords, raw_text)

    except Exception as exc:
        st.error(f"Something went wrong while parsing your files: {exc}")
        st.stop()


# ── Keyword match score ───────────────────────────────────────────────────────
st.subheader("📈 Keyword Match Score")

score = keyword_results["score"]
icon  = "🟢" if score >= 75 else ("🟡" if score >= 45 else "🔴")

st.markdown(f"### {icon} {score}% of job keywords found on your resume")
st.progress(score / 100)

st.divider()


# ── Keyword breakdown ─────────────────────────────────────────────────────────
st.subheader("🔍 Job Description Keywords")
st.caption(
    "Extracted automatically from the job posting — filler words removed, "
    "everything ranked by how often it appeared. Higher frequency = more important."
)

kw_found_col, kw_missing_col = st.columns(2)

with kw_found_col:
    st.markdown("**✅ Keywords found on your resume**")
    if keyword_results["found"]:
        for kw, count in keyword_results["found"]:
            st.markdown(f"- **{kw}** *(mentioned {count}x)*")
    else:
        st.write("None of the job keywords matched your resume.")

with kw_missing_col:
    st.markdown("**❌ Keywords missing from your resume**")
    if keyword_results["missing"]:
        for kw, count in keyword_results["missing"]:
            st.markdown(f"- **{kw}** *(mentioned {count}x)*")
    else:
        st.write("Your resume covers all extracted keywords! 🎉")

st.divider()


# ── JSON download ─────────────────────────────────────────────────────────────
output = {
    "keyword_match_score":  keyword_results["score"],
    "keywords_found":       [kw for kw, _ in keyword_results["found"]],
    "keywords_missing":     [kw for kw, _ in keyword_results["missing"]],
}

st.download_button(
    label="📥 Download Full Analysis (JSON)",
    data=json.dumps(output, indent=2),
    file_name="resume_analysis.json",
    mime="application/json",
    use_container_width=True,
)
