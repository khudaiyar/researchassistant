import os
import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://localhost/research_assistant")


def get_conn():
    return psycopg2.connect(DATABASE_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def init_db():
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            SERIAL PRIMARY KEY,
                name          VARCHAR(255) NOT NULL,
                email         VARCHAR(255) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                is_admin      BOOLEAN DEFAULT FALSE,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS researchers (
                id            SERIAL PRIMARY KEY,
                name          VARCHAR(255) NOT NULL,
                affiliation   VARCHAR(500),
                research_area VARCHAR(500),
                email         VARCHAR(255),
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS papers (
                id            SERIAL PRIMARY KEY,
                title         VARCHAR(1000) NOT NULL,
                authors       TEXT,
                abstract      TEXT,
                year          INT,
                venue         VARCHAR(500),
                doi           VARCHAR(255),
                url           VARCHAR(1000),
                researcher_id INT REFERENCES researchers(id) ON DELETE SET NULL,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS local_files (
                id          SERIAL PRIMARY KEY,
                filename    VARCHAR(500) NOT NULL,
                filepath    VARCHAR(1000),
                description TEXT,
                paper_id    INT REFERENCES papers(id) ON DELETE SET NULL,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS search_history (
                id         SERIAL PRIMARY KEY,
                query      TEXT NOT NULL,
                response   TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    conn.commit()
    conn.close()


def seed_db():
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) AS cnt FROM papers")
        papers_count = cur.fetchone()["cnt"]
        cur.execute("SELECT COUNT(*) AS cnt FROM researchers")
        researchers_count = cur.fetchone()["cnt"]

        if papers_count > 0 and researchers_count > 0:
            conn.close()
            return

        if researchers_count == 0:
            cur.executemany(
                "INSERT INTO researchers (name, affiliation, research_area) VALUES (%s, %s, %s)",
                [
                    ("Yann LeCun",      "New York University / Meta AI",         "Deep Learning, Computer Vision"),
                    ("Geoffrey Hinton", "University of Toronto / Google Brain",  "Neural Networks, Deep Learning"),
                    ("Yoshua Bengio",   "Université de Montréal / Mila",         "Deep Learning, NLP"),
                    ("Andrew Ng",       "Stanford University / DeepLearning.AI", "Machine Learning, Deep Learning"),
                    ("Fei-Fei Li",      "Stanford University",                   "Computer Vision, AI for Healthcare"),
                ],
            )
            conn.commit()

        if papers_count == 0:
            cur.execute("SELECT id FROM researchers WHERE name = 'Fei-Fei Li'")
            row = cur.fetchone()
            fei_fei_id = row["id"] if row else None
            cur.executemany(
                "INSERT INTO papers (title, authors, abstract, year, venue, doi, url, researcher_id) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                [
                    ("Attention Is All You Need",
                     "Vaswani, Shazeer, Parmar et al.",
                     "We propose the Transformer, a model architecture based solely on attention mechanisms.",
                     2017, "NeurIPS", "10.48550/arXiv.1706.03762", "https://arxiv.org/abs/1706.03762", None),
                    ("ImageNet Large Scale Visual Recognition Challenge",
                     "Russakovsky, Deng, Su et al.",
                     "We present the ImageNet benchmark for object detection and image classification at large scale.",
                     2015, "IJCV", "10.1007/s11263-015-0816-y", "https://arxiv.org/abs/1409.0575", fei_fei_id),
                    ("Deep Residual Learning for Image Recognition",
                     "He, Zhang, Ren, Sun",
                     "We present a residual learning framework to ease the training of very deep neural networks.",
                     2016, "CVPR", "10.1109/CVPR.2016.90", "https://arxiv.org/abs/1512.03385", None),
                    ("BERT: Pre-training of Deep Bidirectional Transformers for Language Understanding",
                     "Devlin, Chang, Lee, Toutanova",
                     "We introduce BERT, designed to pretrain deep bidirectional representations from unlabeled text.",
                     2019, "NAACL", "10.18653/v1/N19-1423", "https://arxiv.org/abs/1810.04805", None),
                    ("Language Models are Few-Shot Learners (GPT-3)",
                     "Brown, Mann, Ryder et al.",
                     "We train GPT-3, an autoregressive language model with 175 billion parameters.",
                     2020, "NeurIPS", "10.48550/arXiv.2005.14165", "https://arxiv.org/abs/2005.14165", None),
                ],
            )
            conn.commit()

    conn.close()


def seed_admin(bcrypt_instance):
    """Create the default admin account if it doesn't exist."""
    from config import ADMIN_EMAIL, ADMIN_PASSWORD
    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("SELECT id FROM users WHERE email = %s", (ADMIN_EMAIL,))
        if cur.fetchone():
            conn.close()
            return
        pw_hash = bcrypt_instance.generate_password_hash(ADMIN_PASSWORD).decode("utf-8")
        cur.execute(
            "INSERT INTO users (name, email, password_hash, is_admin) VALUES (%s,%s,%s,%s)",
            ("Admin", ADMIN_EMAIL, pw_hash, True),
        )
    conn.commit()
    conn.close()
