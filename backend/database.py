# backend/database.py
import os
import sqlite3
import pandas as pd

class PDF_Database:

    def __init__(self, db_path="documents.db"):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self._connect()
        self._create_table()

    def _connect(self):
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.cursor = self.conn.cursor()

    def _create_table(self):
        SQL_QUERY = """
        CREATE TABLE IF NOT EXISTS documents (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            upload_date DATETIME DEFAULT CURRENT_TIMESTAMP,
            file_path TEXT UNIQUE,
            text_content TEXT
        );
        """
        self.cursor.execute(SQL_QUERY)
        self.conn.commit()

    def add_document(self, filename, file_path, text_content):
        try:
            SQL_QUERY = """
            INSERT INTO documents (filename, file_path, text_content)
            VALUES (?, ?, ?)
            """
            self.cursor.execute(SQL_QUERY, (filename, file_path, text_content))
            self.conn.commit()
            return self.cursor.lastrowid
        except sqlite3.IntegrityError:
            print(f"Error: The file '{filename}' already exists in the database.")
            return None

    def delete_document(self, doc_id):
        try:
            self.cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            self.conn.commit()
            if self.cursor.rowcount > 0:
                return True
            else:
                return False
        except sqlite3.Error as e:
            print(f"Error deleting document: {e}")
            return False

    def get_document(self, doc_id):
        self.cursor.execute("SELECT text_content FROM documents WHERE id = ?", (doc_id,))
        result = self.cursor.fetchone()
        return result if result else None

    def get_all_documents(self):
        self.cursor.execute("SELECT id, filename, upload_date FROM documents ORDER BY upload_date DESC")
        return self.cursor.fetchall()
        
    def view_database(self):
        try:
            SQL_QUERY = "SELECT * FROM documents"
            df = pd.read_sql_query(SQL_QUERY, self.conn)
            print(df)
        except sqlite3.Error as e:
            print(f"Database error: {e}")
        except Exception as e:
            print(f"An error occurred: {e}")
        finally:
            self.close()

    def clear(self):
        try:
            self.cursor.execute("DELETE FROM documents")
            self.cursor.execute("DELETE FROM sqlite_sequence WHERE name ='documents'")
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Error clearing database: {e}")

    def close(self):
        if self.conn:
            self.conn.close()
