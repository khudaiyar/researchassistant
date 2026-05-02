import pymysql
from config import DB_HOST, DB_USER, DB_PASSWORD, DB_NAME


def get_conn():
    return pymysql.connect(
        host=DB_HOST, user=DB_USER, password=DB_PASSWORD,
        database=DB_NAME, charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )


def init_db():
    # create database if missing
    root = pymysql.connect(host=DB_HOST, user=DB_USER, password=DB_PASSWORD, charset="utf8mb4")
    with root.cursor() as cur:
        cur.execute(f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    root.close()

    conn = get_conn()
    with conn.cursor() as cur:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id            INT AUTO_INCREMENT PRIMARY KEY,
                name          VARCHAR(255) NOT NULL,
                email         VARCHAR(255) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                is_admin      TINYINT(1) DEFAULT 0,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS researchers (
                id            INT AUTO_INCREMENT PRIMARY KEY,
                name          VARCHAR(255) NOT NULL,
                affiliation   VARCHAR(500),
                research_area VARCHAR(500),
                email         VARCHAR(255),
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS papers (
                id            INT AUTO_INCREMENT PRIMARY KEY,
                title         VARCHAR(1000) NOT NULL,
                authors       TEXT,
                abstract      TEXT,
                year          INT,
                venue         VARCHAR(500),
                doi           VARCHAR(255),
                url           VARCHAR(1000),
                researcher_id INT,
                created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (researcher_id) REFERENCES researchers(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS local_files (
                id          INT AUTO_INCREMENT PRIMARY KEY,
                filename    VARCHAR(500) NOT NULL,
                filepath    VARCHAR(1000),
                description TEXT,
                paper_id    INT,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (paper_id) REFERENCES papers(id) ON DELETE SET NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS search_history (
                id         INT AUTO_INCREMENT PRIMARY KEY,
                query      TEXT NOT NULL,
                response   TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
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
            "INSERT INTO users (name, email, password_hash, is_admin) VALUES (%s,%s,%s,1)",
            ("Admin", ADMIN_EMAIL, pw_hash),
        )
    conn.commit()
    conn.close()
