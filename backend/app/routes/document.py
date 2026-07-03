from fastapi import APIRouter, File, UploadFile, HTTPException, status
from app.services.document_service import document_service
from app.services.rag_service import rag_service
from app.services.logger import logger

router = APIRouter(prefix="/api/document", tags=["Document Ingestion"])

@router.post("/upload")
async def upload_document(file: UploadFile = File(...)):
    """Uploads a PDF document, validates it, parses it, and indexes its embeddings in ChromaDB."""
    logger.info(f"Received upload request for file: {file.filename}")
    
    # 1. Validate File Extension
    if not file.filename.lower().endswith(".pdf"):
        logger.warning(f"File validation failed: '{file.filename}' is not a PDF")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file format. Only PDF files are allowed."
        )
        
    # 2. Validate Content Type
    if file.content_type != "application/pdf":
        logger.warning(f"File validation failed: MIME type '{file.content_type}' is not application/pdf")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid media type. Expected 'application/pdf'."
        )
        
    try:
        # 3. Save File Locally
        saved_path = document_service.save_uploaded_file(file)
        
        # 4. Extract text & Chunk PDF
        chunks = document_service.process_pdf(saved_path)
        
        # 5. Embed and Index chunks in ChromaDB Vector Store
        rag_service.add_documents(chunks)
        
        return {
            "message": "File uploaded, processed, and indexed in ChromaDB successfully.",
            "filename": file.filename,
            "saved_path": saved_path,
            "total_chunks": len(chunks),
            "status": "success"
        }
        
    except Exception as e:
        logger.error(f"Failed to process uploaded file {file.filename}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while processing the file: {str(e)}"
        )

@router.get("/search")
async def search_documents(query: str, k: int = 4):
    """Semantic similarity search in ChromaDB vector store."""
    if not query:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query parameter is required."
        )
    try:
        results = rag_service.search_similar_documents(query, k=k)
        return {
            "query": query,
            "results": results,
            "status": "success"
        }
    except Exception as e:
        logger.error(f"Search failed for query '{query}': {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred during search: {str(e)}"
        )

