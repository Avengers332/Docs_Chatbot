import os
import json
import logging
from datetime import datetime
from flask import Blueprint, request, jsonify
from werkzeug.utils import secure_filename
from langchain_community.document_loaders import UnstructuredPDFLoader
from langchain.schema import Document
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
import fitz
from PIL import Image
import io

# Constants
PDF_FOLDER = 'data/pdfs'
VECTOR_DB_FOLDER = 'data/vector_db'
FILE_STATUS_PATH = 'data/file_status.json'
LOG_FILE_PATH = 'data/pdf_processing.log'

# Setup logging
logging.basicConfig(filename=LOG_FILE_PATH, level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


app = Blueprint('pdf_upload_and_embedding', __name__)
os.makedirs(PDF_FOLDER, exist_ok=True)
os.makedirs(VECTOR_DB_FOLDER, exist_ok=True)

# Initialize embedding and vector store
text_splitter = RecursiveCharacterTextSplitter(chunk_size=800, chunk_overlap=300)
embedding_model = HuggingFaceEmbeddings(model_name='sentence-transformers/all-MiniLM-L6-v2')
chroma_db = Chroma(persist_directory=VECTOR_DB_FOLDER, embedding_function=embedding_model)

# File status functions
def load_file_status():
    if os.path.exists(FILE_STATUS_PATH):
        with open(FILE_STATUS_PATH, 'r') as f:
            return json.load(f)
    return {}

def save_file_status(data):
    with open(FILE_STATUS_PATH, 'w') as f:
        json.dump(data, f)

# PDF extraction function
def extract_text_and_images_from_pdf(pdf_path):
    text_chunks = []
    images = []
    try:
        document = fitz.open(pdf_path)
        for page_num, page in enumerate(document):
            text = page.get_text()
            text_chunks.append(Document(page_content=text, metadata={"source": pdf_path, "page": page_num}))
            
            image_list = page.get_images(full=True)
            for img in image_list:
                xref = img[0]
                base_image = document.extract_image(xref)
                image_bytes = base_image["image"]
                image_obj = Image.open(io.BytesIO(image_bytes))
                
                images.append({
                    "image": image_obj,
                    "page": page_num,
                    "source": pdf_path,
                    "format": base_image["ext"]
                })
    except Exception as e:
        logging.error(f"Error processing {pdf_path}: {e}")
    return text_chunks, images

@app.route('/upload_pdf', methods=['POST'])
def upload_pdf():
    if 'pdf' not in request.files:
        logging.warning("No PDF file provided.")
        return jsonify({"error": "No PDF file provided."}), 400

    pdf_file = request.files['pdf']
    if pdf_file.filename == '':
        logging.warning("No file selected.")
        return jsonify({"error": "No file selected."}), 400

    filename = secure_filename(pdf_file.filename)
    pdf_path = os.path.join(PDF_FOLDER, filename)
    pdf_file.save(pdf_path)

    text_chunks, images = extract_text_and_images_from_pdf(pdf_path)
    if not text_chunks:
        return jsonify({"error": "No text found in PDF."}), 400

    # Add documents to Chroma (no need to call persist)
    chroma_db.add_documents(text_chunks)

    file_status = load_file_status()
    file_status[filename] = {
        "status": "processed",
        "text_chunks": len(text_chunks),
        "images": len(images),
        "stored_in_chromadb": True
    }
    save_file_status(file_status)

    return jsonify({
        "message": f"Processed {filename}: {len(text_chunks)} text chunks and {len(images)} images embedded.",
        'status': 'success'
    }), 200

# List PDF and ChromaDB status routes
@app.route('/file_status', methods=['GET'])
def file_status():
    return jsonify(load_file_status()), 200

@app.route('/list_pdfs', methods=['GET'])
def list_pdfs():
    pdf_files = [f for f in os.listdir(PDF_FOLDER) if f.endswith('.pdf')]
    return jsonify(pdfNames=pdf_files)

@app.route('/query_chromadb', methods=['GET'])
def query_chromadb():
    file_status = load_file_status()
    unique_filenames = list(file_status.keys())
    stored_in_chromadb = [
        filename for filename, status in file_status.items() if status.get("stored_in_chromadb", False)
    ]
    return jsonify({
        "stored_files_count": len(unique_filenames),
        "file_names": unique_filenames,
        "stored_in_chromadb": stored_in_chromadb,
        "details": file_status
    }), 200

@app.route('/list_chromadb_collections', methods=['GET'])
def list_chromadb_collections():
    try:
        collections = chroma_db.get()
        return jsonify({"collections": collections}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500
