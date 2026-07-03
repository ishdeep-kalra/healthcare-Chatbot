import os
import shutil
from typing import List, Dict, Any
from fastapi import UploadFile
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.services.logger import logger

UPLOAD_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "uploads"))

class DocumentService:
    @staticmethod
    def save_uploaded_file(file: UploadFile) -> str:
        """Saves an uploaded file to the local directory.
        
        Args:
            file (UploadFile): The uploaded file from FastAPI.
            
        Returns:
            str: The absolute path of the saved file.
        """
        try:
            # Ensure upload directory exists
            os.makedirs(UPLOAD_DIR, exist_ok=True)
            
            filename = os.path.basename(file.filename)
            file_path = os.path.join(UPLOAD_DIR, filename)
            
            logger.info(f"Saving uploaded file '{filename}' to '{file_path}'")
            
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
                
            logger.info(f"File successfully saved: {file_path}")
            return file_path
        except Exception as e:
            logger.error(f"Error saving uploaded file: {str(e)}")
            raise e

    @staticmethod
    def process_pdf(file_path: str) -> List[Dict[str, Any]]:
        """Reads an uploaded PDF, extracts the text, and splits it into chunks.
        
        Args:
            file_path (str): Absolute path to the local PDF file.
            
        Returns:
            List[Dict[str, Any]]: List of document chunks with page_content and metadata.
        """
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"File not found at: {file_path}")
                
            logger.info(f"Loading and parsing PDF from path: {file_path}")
            
            # 1. Load and parse the PDF document page-by-page
            loader = PyPDFLoader(file_path)
            pages = loader.load()
            
            logger.info(f"Successfully loaded PDF. Total pages: {len(pages)}")
            
            # 2. Initialize the text splitter with chunk_size=1000 and overlap=200
            text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=1000,
                chunk_overlap=200,
                length_function=len
            )
            
            # 3. Split the loaded page documents into smaller chunks
            logger.info("Splitting text into chunks using RecursiveCharacterTextSplitter...")
            chunks = text_splitter.split_documents(pages)
            logger.info(f"Created {len(chunks)} text chunks from document.")
            
            # 4. Format chunks for return
            processed_chunks = []
            for i, chunk in enumerate(chunks):
                processed_chunks.append({
                    "id": f"{os.path.basename(file_path)}_chunk_{i}",
                    "page_content": chunk.page_content,
                    "metadata": {
                        "source": os.path.basename(file_path),
                        "page": chunk.metadata.get("page", 0) + 1,  # Make it 1-indexed for reader friendliness
                        "total_pages": len(pages)
                    }
                })
                
            return processed_chunks
            
        except Exception as e:
            logger.error(f"Error processing PDF at {file_path}: {str(e)}")
            raise e

document_service = DocumentService()
