from pydantic import BaseModel, Field
from typing import List

class ChatRequest(BaseModel):
    question: str = Field(..., description="The healthcare query or question from the user")

class SourceMetadata(BaseModel):
    source: str = Field(..., description="Filename of the source document")
    page: int = Field(..., description="Page number where context was retrieved")
    relevance_score: float = Field(..., description="Similarity score calculated by ChromaDB")

class ChatResponse(BaseModel):
    answer: str = Field(..., description="The synthesized response from the RAG pipeline")
    sources: List[SourceMetadata] = Field(..., description="Metadata list of cited documents")
    status: str = Field(..., description="Status flag of the execution")
