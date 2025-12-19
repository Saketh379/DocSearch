# main.py
import os
import shutil
import zipfile
import uvicorn
import docx
import sqlite3
from typing import List, Optional
from fastapi import FastAPI, Request, Form, File, UploadFile, Body
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

# Backend Modules
from backend.database import PDF_Database
from backend.indexer import Indexer
from backend.ranker import Ranker
from backend.preprocess import preprocess
from backend.pdf_reader import PDF_Reader
from backend.user_manager import UserManager

app = FastAPI()

# --- Setup ---
os.makedirs("static", exist_ok=True)
os.makedirs("users_data", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# --- User Management System ---
user_manager = UserManager()

class DeleteRequest(BaseModel):
    doc_ids: List[int]

# --- Helper Functions ---
def get_user_resources(username: str):
    user_root = f"users_data/{username}"
    db_path = f"{user_root}/database.db"
    index_path = f"{user_root}/index.json"
    db = PDF_Database(db_path=db_path)
    indexer = Indexer(index_path=index_path)
    ranker = Ranker(indexer)
    return db, indexer, ranker, user_root

def process_file_for_user(username: str, file_path: str, display_filename: str):
    db, indexer, _, _ = get_user_resources(username)
    
    try:
        ext = display_filename.split('.')[-1].lower()
        text_content = ""

        if ext == "pdf":
            reader = PDF_Reader(file_path)
            text_content = reader.extract_text()
        elif ext == "docx":
            try:
                doc = docx.Document(file_path)
                text_content = "\n".join([para.text for para in doc.paragraphs])
            except: return
        elif ext in ["txt", "md"]:
            with open(file_path, 'r', encoding='utf-8') as f:
                text_content = f.read()
        else:
            return 

        if text_content.strip():
            processed_text = preprocess(text_content)
            doc_id = db.add_document(display_filename, file_path, processed_text)
            if doc_id:
                tokens = processed_text.split()
                indexer.index_document(doc_id, tokens)

    except Exception as e:
        print(f"Error processing {display_filename}: {e}")

# --- Routes ---
@app.get("/", response_class=HTMLResponse)
async def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

@app.post("/signup")
async def signup(
    request: Request,
    username: str = Form(...),
    full_name: str = Form(...),
    password: str = Form(...)
):
    if user_manager.create_user(username, full_name, password):
        return templates.TemplateResponse("login.html", {"request": request, "success": "Account created successfully!"})
    else:
        return templates.TemplateResponse("login.html", {"request": request, "error": "User ID already exists!"})

@app.post("/login")
async def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if user_manager.verify_user(username, password):
        response = RedirectResponse(url="/dashboard", status_code=303)
        response.set_cookie(key="user_session", value=username)
        return response
    else:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"})

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):
    user = request.cookies.get("user_session")
    if not user:
        return RedirectResponse(url="/")
    
    db, _, _, _ = get_user_resources(user)
    docs = db.get_all_documents()
    full_name = user_manager.get_full_name(user)
    
    return templates.TemplateResponse("dashboard.html", {
        "request": request, 
        "user_id": user,
        "display_name": full_name,
        "docs": docs,
        "total_docs": len(docs)
    })

@app.post("/upload")
async def upload_files(
    request: Request, 
    files: List[UploadFile] = File(...),
    custom_filenames: List[str] = Form(...) 
):
    user = request.cookies.get("user_session")
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    _, _, _, user_root = get_user_resources(user)
    upload_dir = os.path.join(user_root, "uploads")
    os.makedirs(upload_dir, exist_ok=True)

    uploaded_names = []
    batch_names_seen = {}

    if len(custom_filenames) < len(files):
        custom_filenames.extend([""] * (len(files) - len(custom_filenames)))

    for i, file in enumerate(files):
        original_ext = file.filename.split('.')[-1].lower()
        user_provided_name = custom_filenames[i].strip()
        
        if user_provided_name:
            safe_name = "".join([c for c in user_provided_name if c.isalpha() or c.isdigit() or c in " -_"])
            if not safe_name.lower().endswith(f".{original_ext}"):
                base_final_name = f"{safe_name}.{original_ext}"
            else:
                base_final_name = safe_name
        else:
            base_final_name = file.filename

        if base_final_name in batch_names_seen:
            count = batch_names_seen[base_final_name]
            name_part, ext_part = os.path.splitext(base_final_name)
            final_name = f"{name_part}_{count}{ext_part}"
            batch_names_seen[base_final_name] += 1
        else:
            final_name = base_final_name
            batch_names_seen[base_final_name] = 1

        physical_path = os.path.join(upload_dir, final_name)
        if os.path.exists(physical_path):
             import uuid
             name_part, ext_part = os.path.splitext(final_name)
             physical_path = os.path.join(upload_dir, f"{name_part}_{uuid.uuid4().hex[:4]}{ext_part}")

        with open(physical_path, "wb+") as file_object:
            shutil.copyfileobj(file.file, file_object)

        if final_name.endswith(".zip"):
            with zipfile.ZipFile(physical_path, 'r') as zip_ref:
                extract_path = os.path.join(upload_dir, f"{final_name}_extracted")
                zip_ref.extractall(extract_path)
                for root, dirs, extracted_files in os.walk(extract_path):
                    for extracted_file in extracted_files:
                        if not extracted_file.startswith('.'):
                            full_path = os.path.join(root, extracted_file)
                            if user_provided_name:
                                display_name = f"{safe_name}_{extracted_file}"
                            else:
                                display_name = f"{file.filename}_{extracted_file}"
                            process_file_for_user(user, full_path, display_name)
                            uploaded_names.append(display_name)
        else:
            process_file_for_user(user, physical_path, final_name)
            uploaded_names.append(final_name)

    return JSONResponse({
        "status": "success", 
        "message": "Upload complete", 
        "files": uploaded_names
    })

@app.post("/delete_docs")
async def delete_documents(request: Request, payload: DeleteRequest):
    user = request.cookies.get("user_session")
    if not user:
        return JSONResponse({"error": "Unauthorized"}, status_code=401)

    db, indexer, _, _ = get_user_resources(user)
    deleted_count = 0
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()

    for doc_id in payload.doc_ids:
        cursor.execute("SELECT file_path FROM documents WHERE id = ?", (doc_id,))
        row = cursor.fetchone()
        if row:
            file_path = row[0]
            if os.path.exists(file_path):
                try: os.remove(file_path)
                except: pass
            indexer.remove_index(doc_id)
            cursor.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
            deleted_count += 1
    
    conn.commit()
    conn.close()
    return JSONResponse({"status": "success", "deleted_count": deleted_count})

@app.get("/view_file/{doc_id}")
async def view_file(request: Request, doc_id: int):
    user = request.cookies.get("user_session")
    if not user:
        return RedirectResponse(url="/")
    
    db, _, _, _ = get_user_resources(user)
    conn = sqlite3.connect(db.db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT file_path, filename FROM documents WHERE id = ?", (doc_id,))
    row = cursor.fetchone()
    conn.close()
    
    if row and os.path.exists(row[0]):
        return FileResponse(row[0], filename=row[1], content_disposition_type="inline")
    return HTMLResponse("File not found", status_code=404)

@app.get("/search")
async def search(request: Request, query: str, search_type: str = "content"):
    user = request.cookies.get("user_session")
    if not user:
        return {"results": []}

    db, _, ranker, _ = get_user_resources(user)
    if not query or not query.strip():
        return {"results": []}

    results = []
    if search_type == "filename":
        all_docs = db.get_all_documents()
        results = [
            {"id": d[0], "filename": d[1], "score": 1.0, "snippet": "Filename matched"} 
            for d in all_docs if query.lower() in d[1].lower()
        ]
    else:
        processed_query = preprocess(query)
        if not processed_query: return {"results": []}
        
        query_tokens = processed_query.split()
        top_docs = ranker.rank(query_tokens, top_k=5)
        
        conn = sqlite3.connect(db.db_path)
        c = conn.cursor()
        for doc_id, score in top_docs:
            c.execute("SELECT filename, text_content FROM documents WHERE id=?", (doc_id,))
            row = c.fetchone()
            if row:
                filename, text = row
                snippet_idx = text.lower().find(query_tokens[0]) if query_tokens else 0
                start = max(0, snippet_idx - 50)
                end = min(len(text), snippet_idx + 60)
                snippet = "..." + text[start:end] + "..."
                results.append({"id": doc_id, "filename": filename, "score": round(score, 4), "snippet": snippet})
        conn.close()
    return {"results": results}

@app.post("/update_profile")
async def update_profile(
    request: Request,
    full_name: Optional[str] = Form(None),
    new_username: Optional[str] = Form(None),
    new_password: Optional[str] = Form(None)
):
    current_user = request.cookies.get("user_session")
    if not current_user: 
        return JSONResponse({"status": "error", "message": "Unauthorized"}, status_code=401)

    success, message = user_manager.update_user(current_user, full_name, new_username, new_password)
    
    if success:
        response = JSONResponse({"status": "success", "message": message})
        if new_username and new_username != current_user:
            response.set_cookie(key="user_session", value=new_username)
        return response
    else:
        return JSONResponse({"status": "error", "message": message})

@app.post("/delete_account")
async def delete_account(request: Request):
    user = request.cookies.get("user_session")
    if not user: 
        return JSONResponse({"status": "error", "message": "Unauthorized"}, status_code=401)
    
    if user_manager.delete_user(user):
        response = JSONResponse({"status": "success", "message": "Account deleted"})
        response.delete_cookie("user_session")
        return response
    else:
        return JSONResponse({"status": "error", "message": "Failed to delete account"})

@app.get("/logout")
async def logout():
    response = RedirectResponse(url="/")
    response.delete_cookie("user_session")
    return response

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000)
    # uvicorn.run(
    #     "main:app",
    #     host="0.0.0.0",
    #     port=int(os.environ.get("PORT", 8000))
    # )