import os
import sys
import time
import json
from datetime import datetime

# Configure python path to allow importing app modules
script_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(script_dir, ".."))
if backend_dir not in sys.path:
    sys.path.insert(0, backend_dir)

# Import services from app
from app.services.document_service import document_service
from app.services.rag_service import rag_service
from app.services.logger import logger

# Paths setup
METADATA_FILE = os.path.join(backend_dir, "indexed_files.json")
DOCS_DIR = os.path.join(backend_dir, "medical_documents")

def load_indexed_metadata() -> dict:
    """Loads metadata for previously indexed files."""
    if os.path.exists(METADATA_FILE):
        try:
            with open(METADATA_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[-] Warning: Failed to parse {METADATA_FILE}. Starting fresh. Error: {e}")
            return {}
    return {}

def save_indexed_metadata(metadata: dict):
    """Saves metadata to prevent reprocessing of unchanged files."""
    try:
        with open(METADATA_FILE, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"[-] Error saving metadata to {METADATA_FILE}: {e}")

def main():
    print("=" * 70)
    print("              MEDAI DOCUMENT INGESTION PIPELINE               ")
    print("=" * 70)
    
    if not os.path.exists(DOCS_DIR):
        print(f"[-] Error: Medical documents folder not found at: {DOCS_DIR}")
        print("Please create this directory and organize PDFs into specialty subfolders.")
        sys.exit(1)

    # 1. Scan for PDFs
    pdf_files = []
    for root, _, files in os.walk(DOCS_DIR):
        for file in files:
            if file.lower().endswith(".pdf"):
                full_path = os.path.join(root, file)
                # Compute path relative to backend_dir for portability
                rel_path = os.path.relpath(full_path, backend_dir)
                pdf_files.append((full_path, rel_path))

    total_files = len(pdf_files)
    print(f"[*] Found {total_files} PDF file(s) in medical_documents/ directory.")
    
    # 2. Load metadata
    indexed_metadata = load_indexed_metadata()
    
    processed_count = 0
    skipped_count = 0
    failed_count = 0
    total_chunks_indexed = 0
    
    start_time = time.time()
    
    # 3. Process each PDF
    for idx, (full_path, rel_path) in enumerate(pdf_files, 1):
        print("-" * 70)
        print(f"[{idx}/{total_files}] File: {rel_path}")
        
        try:
            stat = os.stat(full_path)
            mtime = stat.st_mtime
            size = stat.st_size
            
            # Check if already indexed and unchanged
            if rel_path in indexed_metadata:
                saved_meta = indexed_metadata[rel_path]
                if saved_meta.get("mtime") == mtime and saved_meta.get("size") == size:
                    print(f"    --> SKIPPED (Already indexed on {saved_meta.get('indexed_at')})")
                    skipped_count += 1
                    continue

            # Process the PDF using document_service
            print(f"    --> Extracting and chunking text...")
            chunks = document_service.process_pdf(full_path)
            
            chunk_count = len(chunks)
            if chunk_count == 0:
                print(f"    --> WARNING: Loaded PDF created 0 text chunks. Skipping vector save.")
                skipped_count += 1
                continue
                
            # Add to ChromaDB vector store
            print(f"    --> Saving {chunk_count} chunk(s) to ChromaDB vector store...")
            rag_service.add_documents(chunks)
            
            # Update metadata
            indexed_metadata[rel_path] = {
                "mtime": mtime,
                "size": size,
                "chunks_count": chunk_count,
                "indexed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }
            save_indexed_metadata(indexed_metadata)
            
            print(f"    --> SUCCESS: Indexed {chunk_count} chunk(s).")
            processed_count += 1
            total_chunks_indexed += chunk_count
            
        except Exception as e:
            print(f"    --> ERROR: Failed to ingest file: {e}")
            failed_count += 1
            logger.exception(f"Pipeline error for file '{rel_path}': {str(e)}")

    end_time = time.time()
    execution_time = end_time - start_time
    
    # 4. Summary Statistics
    print("=" * 70)
    print("                     INGESTION SUMMARY                        ")
    print("=" * 70)
    print(f"Total PDFs Scanned:      {total_files}")
    print(f"PDFs Processed:          {processed_count}")
    print(f"PDFs Skipped (Unchanged): {skipped_count}")
    print(f"PDFs Failed:             {failed_count}")
    print(f"Total Chunks Indexed:    {total_chunks_indexed}")
    print(f"Total Execution Time:    {execution_time:.2f} seconds")
    print("=" * 70)

if __name__ == "__main__":
    main()
