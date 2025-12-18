# backend/user_manager.py
import sqlite3
import hashlib
import os
import shutil

class UserManager:

    def __init__(self, db_path="users.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY,
                full_name TEXT,
                password_hash TEXT NOT NULL
        )""")
        conn.commit()
        conn.close()

    def _hash_password(self, password):
        return hashlib.sha256(password.encode()).hexdigest()

    def create_user(self, username, full_name, password):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT username FROM users WHERE username = ?", (username,))
            if cursor.fetchone():
                return False

            pwd_hash = self._hash_password(password)
            cursor.execute("INSERT INTO users (username, full_name, password_hash) VALUES (?, ?, ?)", (username, full_name, pwd_hash))
            conn.commit()
            
            user_dir = os.path.join("users_data", username)
            os.makedirs(os.path.join(user_dir, "uploads"), exist_ok=True)
            return True

        except Exception as e:
            print(f"Error creating user: {e}")
            return False

        finally:
            conn.close()

    def verify_user(self, username, password):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT password_hash FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()
        conn.close()
        if result:
            return result[0] == self._hash_password(password)
        return False

    def get_full_name(self, username):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT full_name FROM users WHERE username = ?", (username,))
        result = cursor.fetchone()
        conn.close()
        return result[0] if result else username

    def update_user(self, current_username, new_full_name=None, new_username=None, new_password=None):
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            if new_full_name:
                cursor.execute("UPDATE users SET full_name = ? WHERE username = ?", (new_full_name, current_username))
            
            if new_password and new_password.strip():
                pwd_hash = self._hash_password(new_password)
                cursor.execute("UPDATE users SET password_hash = ? WHERE username = ?", (pwd_hash, current_username))

            if new_username and new_username != current_username:
                new_username = new_username.strip()
                
                cursor.execute("SELECT 1 FROM users WHERE username = ?", (new_username,))
                if cursor.fetchone():
                    return False, "User ID already exists, try another"
                
                old_dir = os.path.join("users_data", current_username)
                new_dir = os.path.join("users_data", new_username)
                
                if os.path.exists(old_dir):
                    os.rename(old_dir, new_dir)
                
                cursor.execute("UPDATE users SET username = ? WHERE username = ?", (new_username, current_username))
            
            conn.commit()
            return True, "Profile updated successfully"

        except Exception as e:
            conn.rollback()
            return False, f"Error updating profile: {str(e)}"

        finally:
            conn.close()

    def delete_user(self, username):
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM users WHERE username = ?", (username,))
            conn.commit()
            conn.close()
            
            user_dir = os.path.join("users_data", username)
            if os.path.exists(user_dir):
                shutil.rmtree(user_dir)
            return True

        except Exception as e:
            print(f"Error deleting user: {e}")
            return False
