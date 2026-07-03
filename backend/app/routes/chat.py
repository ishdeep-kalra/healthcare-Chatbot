from fastapi import APIRouter, HTTPException, Query, status
from app.services.rag_service import rag_service
from app.services.guardrail import guardrail
from app.services.logger import logger
from app.schemas.chat import ChatRequest, ChatResponse

router = APIRouter(prefix="/api/chat", tags=["Chat & Retrieval"])

@router.get("/retrieve")
async def retrieve_context(
    query: str = Query(..., description="The user question or search terms"),
    limit: int = Query(5, description="Number of relevant text chunks to retrieve")
):
    """Retrieves top semantically matching chunks from ChromaDB with similarity scores, protected by safety filters."""
    logger.info(f"Retrieval request: query='{query}', limit={limit}")
    
    if not query.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Query query parameter cannot be empty."
        )
        
    # 1. Enforce Healthcare Safety Guardrails
    validation = guardrail.inspect_input(query)
    if not validation["is_allowed"]:
        logger.warning(f"Guardrail intercepted query: reason='{validation['reason']}'")
        return {
            "query": query,
            "count": 0,
            "documents": [],
            "status": "blocked",
            "safety_alert": True,
            "is_emergency": validation.get("is_emergency", False),
            "message": validation["message"]
        }
        
    try:
        # 2. Perform semantic similarity search in ChromaDB vector store
        retrieved_documents = rag_service.search_similar_documents(query=query, k=limit)
        
        return {
            "query": query,
            "count": len(retrieved_documents),
            "documents": retrieved_documents,
            "status": "success",
            "safety_alert": False,
            "is_emergency": False
        }
        
    except Exception as e:
        logger.error(f"Retrieval service failed for query '{query}': {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while retrieving relevant chunks: {str(e)}"
        )

@router.post("", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Processes RAG medical questions, retrieves context, and queries Gemini."""
    logger.info(f"Received RAG chat query request: '{request.question}'")
    
    if not request.question.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Question payload cannot be empty."
        )
        
    # 1. Enforce Healthcare Safety Guardrails (Input checks)
    validation = guardrail.inspect_input(request.question)
    if not validation["is_allowed"]:
        logger.warning(f"Safety check blocked query: {validation['reason']}")
        return ChatResponse(
            answer=validation["message"],
            sources=[],
            status="blocked"
        )
        
    try:
        # 2. Run the complete RAG Pipeline (Retrieve -> Prompt -> Gemini -> Enforce output safety)
        result = rag_service.answer_healthcare_query(request.question)
        
        return ChatResponse(
            answer=result["answer"],
            sources=result["sources"],
            status=result["status"]
        )
        
    except Exception as e:
        logger.error(f"RAG query generation failure: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An internal error occurred while generating response: {str(e)}"
        )

