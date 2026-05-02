import json
import os
import re
import requests
from ddgs import DDGS
from database import get_conn

DOWNLOADS_DIR    = "/tmp/downloads"
_last_downloaded = None   # filename of most recent successful download
os.makedirs(DOWNLOADS_DIR, exist_ok=True)


def get_last_download():
    global _last_downloaded
    f, _last_downloaded = _last_downloaded, None
    return f


# ── Web search ────────────────────────────────────────────────────────────────

def search_web(query: str) -> str:
    try:
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query + " research paper academic", max_results=5):
                results.append(f"• {r['title']}\n  {r['body'][:250]}\n  URL: {r['href']}")
        return "\n\n".join(results) if results else "No web results found."
    except Exception as e:
        return f"Web search error: {e}"


# ── Local DB search ───────────────────────────────────────────────────────────

def search_local_db(query: str) -> str:
    conn = get_conn()
    results = []
    like = f"%{query}%"
    with conn.cursor() as cur:
        cur.execute(
            "SELECT id, title, authors, year, venue FROM papers "
            "WHERE title LIKE %s OR authors LIKE %s OR abstract LIKE %s LIMIT 10",
            (like, like, like),
        )
        papers = cur.fetchall()
        if papers:
            results.append("Papers in local DB:")
            for p in papers:
                results.append(f"  [ID:{p['id']}] {p['title']} — {p['authors']} ({p['year']}, {p['venue']})")

        cur.execute(
            "SELECT id, name, affiliation, research_area FROM researchers "
            "WHERE name LIKE %s OR affiliation LIKE %s OR research_area LIKE %s LIMIT 5",
            (like, like, like),
        )
        researchers = cur.fetchall()
        if researchers:
            results.append("Researchers in local DB:")
            for r in researchers:
                results.append(f"  [ID:{r['id']}] {r['name']} — {r['affiliation']} | {r['research_area']}")
    conn.close()
    return "\n".join(results) if results else "Nothing found in local database."


# ── Save paper ────────────────────────────────────────────────────────────────

def save_paper(title: str, authors: str, abstract: str, year: str,
               venue: str, doi: str, url: str) -> str:
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM papers WHERE title = %s", (title,))
            if cur.fetchone():
                conn.close()
                return f"Paper already exists in database: '{title}'"
            yr = int(year) if str(year).isdigit() else None
            cur.execute(
                "INSERT INTO papers (title, authors, abstract, year, venue, doi, url) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (title, authors, abstract, yr, venue, doi, url),
            )
        conn.commit()
        conn.close()
        return f"Successfully saved paper to local database: '{title}'"
    except Exception as e:
        return f"Error saving paper: {e}"


# ── List papers ───────────────────────────────────────────────────────────────

def list_papers(filter_text: str = "") -> str:
    conn = get_conn()
    with conn.cursor() as cur:
        if filter_text:
            like = f"%{filter_text}%"
            cur.execute(
                "SELECT id, title, authors, year, venue FROM papers "
                "WHERE title LIKE %s OR authors LIKE %s OR CAST(year AS CHAR) = %s "
                "ORDER BY year DESC",
                (like, like, filter_text),
            )
        else:
            cur.execute("SELECT id, title, authors, year, venue FROM papers ORDER BY year DESC")
        papers = cur.fetchall()
    conn.close()
    if not papers:
        return "No papers found in local database."
    lines = [
        f"[ID:{p['id']}] {p['title']} — {p['authors']} ({p['year']}, {p['venue']})"
        for p in papers
    ]
    return f"Found {len(papers)} paper(s):\n" + "\n".join(lines)


# ── List researchers ──────────────────────────────────────────────────────────

def list_researchers(filter_text: str = "") -> str:
    conn = get_conn()
    with conn.cursor() as cur:
        if filter_text:
            like = f"%{filter_text}%"
            cur.execute(
                "SELECT id, name, affiliation, research_area FROM researchers "
                "WHERE name LIKE %s OR research_area LIKE %s",
                (like, like),
            )
        else:
            cur.execute("SELECT id, name, affiliation, research_area FROM researchers ORDER BY name")
        rows = cur.fetchall()
    conn.close()
    if not rows:
        return "No researchers found."
    lines = [
        f"[ID:{r['id']}] {r['name']} — {r['affiliation']} | {r['research_area']}"
        for r in rows
    ]
    return f"Found {len(rows)} researcher(s):\n" + "\n".join(lines)


# ── Add researcher ────────────────────────────────────────────────────────────

def add_researcher(name: str, affiliation: str, research_area: str) -> str:
    try:
        conn = get_conn()
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM researchers WHERE name = %s", (name,))
            if cur.fetchone():
                conn.close()
                return f"Researcher '{name}' already exists in database."
            cur.execute(
                "INSERT INTO researchers (name, affiliation, research_area) VALUES (%s, %s, %s)",
                (name, affiliation, research_area),
            )
        conn.commit()
        conn.close()
        return f"Successfully added researcher: {name} ({affiliation})"
    except Exception as e:
        return f"Error adding researcher: {e}"


# ── Download paper ────────────────────────────────────────────────────────────

def download_paper(query: str) -> str:
    """Search for a paper and download its PDF from arXiv."""
    try:
        arxiv_id   = None
        pdf_url    = None
        paper_title = query
        hdrs = {"User-Agent": "FridayResearchAssistant/1.0 (educational tool)"}

        # Check if query is already an arXiv ID (e.g. "1706.03762")
        direct = re.search(r'\b(\d{4}\.\d{4,5})\b', query)
        if direct:
            arxiv_id = direct.group(1)
            pdf_url  = f"https://arxiv.org/pdf/{arxiv_id}.pdf"

        # arXiv Atom API search
        if not pdf_url:
            try:
                url  = f"https://export.arxiv.org/api/query?search_query=all:{requests.utils.quote(query)}&max_results=1&sortBy=relevance"
                resp = requests.get(url, headers=hdrs, timeout=15)
                if resp.status_code == 200:
                    id_m = re.search(r'<id>\s*http://arxiv\.org/abs/([\d\.v]+)\s*</id>', resp.text)
                    if id_m:
                        arxiv_id = id_m.group(1).split("v")[0]
                        pdf_url  = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                    t_m = re.search(r'<entry>.*?<title>(.*?)</title>', resp.text, re.DOTALL)
                    if t_m:
                        paper_title = re.sub(r'\s+', ' ', t_m.group(1)).strip()
            except Exception:
                pass

        # DuckDuckGo fallback
        if not pdf_url:
            try:
                with DDGS() as ddgs:
                    for r in ddgs.text(query + " arxiv", max_results=5):
                        href = r.get("href", "")
                        m = re.search(r'arxiv\.org/(?:abs|pdf)/([\d\.]+)', href)
                        if m:
                            arxiv_id    = m.group(1)
                            pdf_url     = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
                            paper_title = r.get("title", query)
                            break
            except Exception:
                pass

        if not pdf_url:
            return (
                f"Could not find a downloadable PDF for '{query}'.\n"
                "Tip: use the exact paper title or an arXiv ID like '1706.03762'."
            )

        filename = f"{arxiv_id or re.sub(r'[^\\w-]', '_', query)[:60]}.pdf"
        filepath = os.path.join(DOWNLOADS_DIR, filename)

        if os.path.exists(filepath):
            size_kb = os.path.getsize(filepath) // 1024
            return f"Already in library: {filename} ({size_kb} KB)"

        r = requests.get(pdf_url, headers=hdrs, timeout=40, stream=True)
        if r.status_code != 200:
            return f"Failed to download (HTTP {r.status_code}) from {pdf_url}"

        with open(filepath, "wb") as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)

        size_kb = os.path.getsize(filepath) // 1024
        if size_kb < 5:
            os.remove(filepath)
            return "Download failed: arXiv returned an invalid response. Try a different query."

        # Record in local_files table and mark for browser delivery
        try:
            conn = get_conn()
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO local_files (filename, filepath, description) VALUES (%s,%s,%s)",
                    (filename, filepath, paper_title[:200]),
                )
            conn.commit()
            conn.close()
        except Exception:
            pass

        global _last_downloaded
        _last_downloaded = filename

        return (
            f"Downloaded successfully!\n"
            f"Title: {paper_title}\n"
            f"File: {filename} ({size_kb} KB)\n"
            f"Your browser will save it automatically."
        )
    except Exception as e:
        return f"Download error: {e}"


# ── Tool registry ─────────────────────────────────────────────────────────────

def _json_call(fn):
    def wrapper(args):
        try:
            kwargs = json.loads(args) if args.strip().startswith("{") else {"filter_text": args}
            return fn(**kwargs)
        except Exception as e:
            return f"Tool input error: {e}"
    return wrapper


TOOLS = {
    "search_web": {
        "func": search_web,
        "description": (
            "Search the web for research papers, researchers, or academic topics. "
            "Input: a plain text search query."
        ),
    },
    "search_local_db": {
        "func": search_local_db,
        "description": (
            "Search the local MySQL database for saved papers and researchers. "
            "Input: a keyword, researcher name, or topic."
        ),
    },
    "save_paper": {
        "func": _json_call(save_paper),
        "description": (
            "Save a research paper to the local database. "
            'Input: JSON — {"title":"...","authors":"...","abstract":"...","year":"2024","venue":"NeurIPS","doi":"","url":""}'
        ),
    },
    "list_papers": {
        "func": list_papers,
        "description": (
            "List papers stored in the local database. "
            "Input: optional filter (year number, author name, keyword) or empty string for all."
        ),
    },
    "list_researchers": {
        "func": list_researchers,
        "description": (
            "List researchers stored in the local database. "
            "Input: optional filter keyword or empty string for all."
        ),
    },
    "add_researcher": {
        "func": _json_call(add_researcher),
        "description": (
            "Add a researcher to the local database. "
            'Input: JSON — {"name":"...","affiliation":"...","research_area":"..."}'
        ),
    },
    "download_paper": {
        "func": download_paper,
        "description": (
            "Download a research paper as a PDF file to the local library. "
            "Searches arXiv and open-access sources. "
            "Input: paper title, arXiv ID, or descriptive query (e.g. 'Attention Is All You Need Vaswani 2017')."
        ),
    },
}
