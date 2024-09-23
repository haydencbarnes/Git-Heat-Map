import sqlite3
import re
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# Constants
COMMIT_START_SYMBOL = chr(30)
COMMIT_SPLIT_SYMBOL = chr(31)

# SQL Statements
select_file_sql = """
    (
        SELECT files.fileID
        FROM files
        WHERE files.filePath = ?
    )
"""

insert_commit_sql = """
    INSERT INTO
    commits(hash, authorDate, committerName, committerEmail, committerDate)
    VALUES(?, ?, ?, ?, ?)
"""

insert_file_sql = """
    INSERT OR IGNORE INTO
    files(filePath)
    VALUES(?)
"""

# Modified to handle conflict by updating linesAdded and linesRemoved
insert_commitFile_sql = f"""
    INSERT INTO
    commitFile(hash, fileID, linesAdded, linesRemoved)
    VALUES(?, {select_file_sql}, ?, ?)
    ON CONFLICT(hash, fileID) DO UPDATE SET
        linesAdded = commitFile.linesAdded + excluded.linesAdded,
        linesRemoved = commitFile.linesRemoved + excluded.linesRemoved
"""

insert_author_sql = """
    INSERT OR IGNORE INTO
    author(authorEmail, authorName)
    VALUES(?, ?)
"""

insert_commitAuthor_sql = f"""
    INSERT OR IGNORE INTO
    commitAuthor(hash, authorEmail)
    VALUES(?, ?)
"""

update_file_sql = """
    UPDATE OR IGNORE files
    SET filePath = ?
    WHERE filePath = ?
"""

delete_commitFile_sql = f"""
    DELETE FROM commitFile
    WHERE commitFile.fileID = {select_file_sql}
"""

delete_file_sql = """
    DELETE FROM files
    WHERE files.filePath = ?
"""

nullify_file_sql = """
    UPDATE FILES
    SET filePath = NULL
    WHERE filePath = ?
"""

# Regular Expression for Parsing Git Numstat
regex_numstat_z = re.compile(r"([\-\d]+)\t([\-\d]+)\t(?:\0([^\0]+)\0([^\0]+)|([^\0]+))\0")

def db_connection(database_path):
    """
    Establishes a connection to the SQLite database with a higher timeout
    and enables Write-Ahead Logging (WAL) mode to improve concurrency.
    """
    try:
        logging.debug(f"Connecting to database at {database_path} with a timeout of 30 seconds.")
        con = sqlite3.connect(database_path, timeout=30)
        con.execute("PRAGMA journal_mode=WAL;")  # Enable WAL mode
        con.execute("PRAGMA foreign_keys = ON;")  # Enforce foreign key constraints
        return con
    except sqlite3.Error as e:
        logging.error(f"Failed to connect to the database: {e}")
        raise

def create_tables(cur):
    """
    Creates the necessary tables in the SQLite database.
    """
    try:
        logging.debug("Creating 'commits' table.")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS commits(
                hash TEXT PRIMARY KEY,
                authorDate TEXT NOT NULL,
                committerName TEXT NOT NULL,
                committerEmail TEXT NOT NULL,
                committerDate TEXT NOT NULL
            )
        """)

        logging.debug("Creating 'files' table.")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS files(
                fileID INTEGER PRIMARY KEY AUTOINCREMENT,
                filePath TEXT UNIQUE
            )
        """)

        logging.debug("Creating 'commitFile' table.")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS commitFile(
                hash TEXT,
                fileID INTEGER,
                linesAdded INTEGER,
                linesRemoved INTEGER,
                FOREIGN KEY (hash) REFERENCES commits (hash),
                FOREIGN KEY (fileID) REFERENCES files (fileID),
                PRIMARY KEY (hash, fileID)
            )
        """)

        logging.debug("Creating 'author' table.")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS author(
                authorEmail TEXT PRIMARY KEY,
                authorName TEXT NOT NULL
            )
        """)

        logging.debug("Creating 'commitAuthor' table.")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS commitAuthor(
                hash TEXT,
                authorEmail TEXT,
                FOREIGN KEY (hash) REFERENCES commits (hash),
                FOREIGN KEY (authorEmail) REFERENCES author (authorEmail),
                PRIMARY KEY (hash, authorEmail)
            )
        """)

        logging.debug("Creating necessary indices.")
        create_indices(cur)

        logging.debug("All tables and indices created successfully.")
    except sqlite3.Error as e:
        logging.error(f"An error occurred while creating tables: {e}")
        raise

def create_indices(cur):
    """
    Creates indices to optimize query performance.
    """
    try:
        logging.debug("Creating index on 'commitFile.fileID'.")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_commitFile_fileID ON commitFile (fileID)")

        logging.debug("Creating index on 'commitAuthor.authorEmail'.")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_commitAuthor_authorEmail ON commitAuthor (authorEmail)")
    except sqlite3.Error as e:
        logging.error(f"An error occurred while creating indices: {e}")
        raise

def commit_create(cur, fields):
    """
    Inserts a commit record into the 'commits' table.
    """
    try:
        cur.execute(insert_commit_sql,
                    (fields["hash"], fields["authorDate"],
                     fields["committerName"], fields["committerEmail"], fields["committerDate"]))
        logging.debug(f"Inserted commit {fields['hash']} into 'commits' table.")
    except sqlite3.IntegrityError:
        logging.warning(f"Commit {fields['hash']} already exists in 'commits' table.")
    except sqlite3.Error as e:
        logging.error(f"Failed to insert commit {fields['hash']}: {e}")
        raise

def author_create(cur, email, name):
    """
    Inserts an author record into the 'author' table.
    """
    try:
        cur.execute(insert_author_sql, (email, name))
        logging.debug(f"Inserted/ignored author {email} - {name} into 'author' table.")
    except sqlite3.Error as e:
        logging.error(f"Failed to insert author {email}: {e}")
        raise

def commitAuthor_create(cur, hash, email):
    """
    Inserts a commit-author association into the 'commitAuthor' table.
    """
    try:
        cur.execute(insert_commitAuthor_sql, (hash, email))
        logging.debug(f"Associated commit {hash} with author {email} in 'commitAuthor' table.")
    except sqlite3.Error as e:
        logging.error(f"Failed to associate commit {hash} with author {email}: {e}")
        raise

def handle_commit(cur, commit_lines):
    """
    Processes a single commit's data and inserts relevant records into the database.
    """
    if len(commit_lines) <= 1:
        logging.debug("Commit has insufficient lines to process.")
        return

    encoding = commit_lines[0].split(COMMIT_SPLIT_SYMBOL.encode())[-2].decode()
    if encoding == "":
        encoding = "utf-8"

    keys = ("hash", "authorName", "authorEmail", "authorDate",
            "committerName", "committerEmail", "committerDate")
    first_line_sep = commit_lines[0][1:].decode(encoding, errors="replace").split(COMMIT_SPLIT_SYMBOL)
    fields = {keys[i]: first_line_sep[i] for i in range(len(keys))}
    
    try:
        commit_create(cur, fields)
    except sqlite3.IntegrityError:
        logging.warning(f"Commit {fields['hash']} already exists. Skipping detailed processing.")
        return fields["hash"]
    except Exception as e:
        logging.error(f"Error inserting commit {fields['hash']}: {e}")
        raise

    author_create(cur, fields["authorEmail"], fields["authorName"])
    commitAuthor_create(cur, fields["hash"], fields["authorEmail"])

    # Handle co-authors if any
    for i in range(len(keys), len(first_line_sep) - 2):
        co_authors = re.findall(r"(.*?) <(.*?)> ?", first_line_sep[i])
        for name, email in co_authors:
            author_create(cur, email, name)
            commitAuthor_create(cur, fields["hash"], email)

    # Process numstat data
    numstat_line = commit_lines[1].decode(encoding)
    matches = regex_numstat_z.findall(numstat_line)
    
    # Handle possible continuation lines
    if len(commit_lines) > 2:
        first_secondary_line = commit_lines[2].decode(encoding)
        commit_lines.insert(2, first_secondary_line.encode(encoding))
    
    for i, match in enumerate(matches):
        try:
            handle_match(cur, match, commit_lines[2 + i].decode(encoding), fields)
        except Exception as e:
            logging.error(f"Error handling match {match}: {e}")
            # Continue processing other matches
            continue
    return fields["hash"]

def file_create(cur, file_path):
    """
    Inserts a file record into the 'files' table.
    """
    try:
        cur.execute(insert_file_sql, (file_path,))
        logging.debug(f"Inserted/ignored file '{file_path}' into 'files' table.")
    except sqlite3.Error as e:
        logging.error(f"Failed to insert file '{file_path}': {e}")
        raise

def file_rename(cur, old_name, new_name):
    """
    Updates a file's path in the 'files' table to reflect a rename.
    """
    try:
        cur.execute(update_file_sql, (new_name, old_name))
        logging.debug(f"Renamed file from '{old_name}' to '{new_name}' in 'files' table.")
    except sqlite3.Error as e:
        logging.error(f"Failed to rename file from '{old_name}' to '{new_name}': {e}")
        raise

def file_delete(cur, file_path):
    """
    Marks a file as deleted in the 'files' table by setting its path to NULL.
    """
    try:
        cur.execute(nullify_file_sql, (file_path,))
        logging.debug(f"Marked file '{file_path}' as deleted in 'files' table.")
    except sqlite3.Error as e:
        logging.error(f"Failed to delete file '{file_path}': {e}")
        raise

def commitFile_create(cur, fields, file_path, added, removed):
    """
    Inserts or updates a commit-file association in the 'commitFile' table.
    If the (hash, fileID) already exists, updates the linesAdded and linesRemoved.
    """
    try:
        # Use the modified SQL with ON CONFLICT to handle duplicates
        cur.execute(insert_commitFile_sql, (fields["hash"], file_path, added, removed))
        logging.debug(f"Inserted/Updated commitFile association for commit {fields['hash']} and file '{file_path}'.")
    except sqlite3.Error as e:
        logging.error(f"Failed to insert/update commitFile for commit {fields['hash']} and file '{file_path}': {e}")
        raise

def handle_match(cur, match, secondary_line, fields):
    """
    Processes a single file change (match) within a commit.
    """
    if "|" not in secondary_line:
        logging.error(f"Secondary line missing '|': '{secondary_line}' for commit {fields['hash']} and file '{match[-1]}'")
        return

    try:
        p, n = secondary_line.split("|")
    except ValueError:
        logging.error(f"Failed to split secondary_line: '{secondary_line}' for commit {fields['hash']}'")
        return

    second_path = p.strip()

    if match[4]:
        file_path = match[4]
    elif match[2] and match[3]:
        file_rename(cur, match[2], match[3])
        file_path = match[3]
    else:
        file_path = "unknown"

    if re.match(r"(.*)\(new.{0,3}\)$", second_path):
        file_create(cur, file_path)

    if "-" in match[:1]:
        added = 0
        removed = 0
    else:
        try:
            added = int(match[0])
            removed = int(match[1])
            second_total = int(n.split()[0])
            assert added + removed == second_total, "Mismatch in added and removed lines."
        except ValueError:
            logging.warning(f"Non-integer values found in match: {match} and secondary_line: {secondary_line}")
            added = 0
            removed = 0
        except AssertionError as e:
            logging.warning(f"{e} in commit {fields['hash']}. Setting added and removed to 0.")
            added = 0
            removed = 0

    commitFile_create(cur, fields, file_path, added, removed)

    if re.match(r"(.*)\(gone\)$", second_path):
        file_delete(cur, file_path)

def get_next_line(log_output):
    """
    Reads the next line from the log output.
    """
    return log_output.readline()

def create_indices(cur):
    """
    Creates indices to optimize query performance.
    """
    try:
        logging.debug("Creating index on 'commitFile.fileID'.")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_commitFile_fileID ON commitFile (fileID)")

        logging.debug("Creating index on 'commitAuthor.authorEmail'.")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_commitAuthor_authorEmail ON commitAuthor (authorEmail)")
    except sqlite3.Error as e:
        logging.error(f"An error occurred while creating indices: {e}")
        raise
