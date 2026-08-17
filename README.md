# 🎌 Japan Job Matcher & Scraper

An automated high-performance Data Pipeline built with **Python**, **Polars**, **HTTPX**, and **BeautifulSoup4** to scrape, normalize, and score tech job postings in Japan across multiple sources (Japan Dev, TokyoDev).

## 🚀 Key Features

- **Multi-Source Scraping:** Concurrent or sequential ingestion from leading Japanese tech career boards.
- **Ultra-fast Ranking (Polars Engine):** Vectorized keyword scoring and weight calculation built on top of Apache Arrow/Polars.
- **Data Normalization:** Maps heterogeneous payload formats into a unified Data Model.
- **Automated Alerts:** GitHub Actions runner scheduled to harvest daily opportunities and export ranked JSON reports.

## 🛠 Tech Stack

- **Data Processing:** Polars (Rust-backed DataFrame engine)
- **Scraping & Networking:** HTTPX, BeautifulSoup4
- **Automation:** GitHub Actions
- **Configuration & Typing:** Pydantic / Native Python Typing

## ⚙️ How to Run Locally

```bash
# Clone repository
git clone [https://github.com/your-user/japan_job_scraper.git](https://github.com/your-user/japan_job_scraper.git)
cd japan_job_scraper

# Setup Virtual Environment
python3 -m venv .venv
source .venv/bin/activate

# Install Dependencies
pip install -r requirements.txt

# Execute Pipeline
python main.py