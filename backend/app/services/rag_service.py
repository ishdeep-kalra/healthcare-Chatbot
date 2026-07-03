import os
from typing import List, Dict, Any
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import settings
from app.services.logger import logger
from app.services.guardrail import guardrail

class RAGService:
    def __init__(self):
        self._embeddings = None
        self._vector_store = None
        self._llm = None
        self.collection_name = "medical_documents"

    @property
    def embeddings(self) -> HuggingFaceEmbeddings:
        """Lazy-loaded HuggingFace Embeddings generator."""
        if self._embeddings is None:
            logger.info("Initializing HuggingFaceEmbeddings model: sentence-transformers/all-MiniLM-L6-v2...")
            os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
            self._embeddings = HuggingFaceEmbeddings(
                model_name="sentence-transformers/all-MiniLM-L6-v2"
            )
            logger.info("Embedding model loaded successfully.")
        return self._embeddings

    @property
    def vector_store(self) -> Chroma:
        """Lazy-loaded persistent Chroma DB client."""
        if self._vector_store is None:
            persist_dir = os.path.abspath(settings.CHROMA_PERSIST_DIR)
            logger.info(f"Initializing persistent ChromaDB vector store at: {persist_dir}")
            os.makedirs(persist_dir, exist_ok=True)
            self._vector_store = Chroma(
                collection_name=self.collection_name,
                embedding_function=self.embeddings,
                persist_directory=persist_dir
            )
            logger.info("ChromaDB vector store initialized.")
        return self._vector_store

    @property
    def llm(self) -> ChatGoogleGenerativeAI:
        """Lazy-loaded Gemini 1.5 Flash client via LangChain."""
        if self._llm is None:
            logger.info("Initializing ChatGoogleGenerativeAI model: gemini-1.5-flash...")
            # Google SDK expects key in GOOGLE_API_KEY environment variable
            self._llm = ChatGoogleGenerativeAI(
    model="gemini-2.5-flash",
    google_api_key=settings.GEMINI_API_KEY,
    temperature=0.2,
    max_tokens=1024
)
            logger.info("Gemini LLM client initialized successfully.")
        return self._llm

    def add_documents(self, chunks: List[Dict[str, Any]]) -> None:
        """Adds a list of parsed document chunks to the persistent ChromaDB collection."""
        if not chunks:
            logger.warning("No document chunks to save to ChromaDB.")
            return

        try:
            texts = [chunk["page_content"] for chunk in chunks]
            metadatas = [chunk["metadata"] for chunk in chunks]
            ids = [chunk["id"] for chunk in chunks]
            
            logger.info(f"Adding {len(texts)} chunks to ChromaDB...")
            self.vector_store.add_texts(texts=texts, metadatas=metadatas, ids=ids)
            logger.info("Successfully persisted document embeddings in ChromaDB.")
        except Exception as e:
            logger.error(f"Failed to save embeddings to ChromaDB: {str(e)}")
            raise e

    def search_similar_documents(self, query: str, k: int = 4) -> List[Dict[str, Any]]:
        """Queries the vector store for documents similar to the search query."""
        try:
            logger.info(f"Performing similarity search for query: '{query}' (k={k})")
            docs_and_scores = self.vector_store.similarity_search_with_relevance_scores(query, k=k)
            
            results = []
            for doc, score in docs_and_scores:
                results.append({
                    "page_content": doc.page_content,
                    "metadata": doc.metadata,
                    "relevance_score": float(score)
                })
            
            logger.info(f"Retrieved {len(results)} matches from ChromaDB.")
            return results
        except Exception as e:
            logger.error(f"Error during ChromaDB similarity search: {str(e)}")
            raise e

    def answer_healthcare_query(self, query: str) -> Dict[str, Any]:
        """Runs the full RAG pipeline: retrieves context, builds a safe clinical prompt,

        and calls Gemini LLM to generate the final response.
        
        Args:
            query (str): The user's medical or healthcare question.
            
        Returns:
            Dict[str, Any]: Dictionary containing the answer text and source metadata list.
        """
        try:
            logger.info(f"Executing RAG pipeline for healthcare query: '{query}'")
            
            # 1. Retrieve top 5 matching text chunks from vector storage
            retrieved_docs = self.search_similar_documents(query=query, k=5)
            
            # 2. Check if relevant context is found (Requirement 7)
            if not retrieved_docs:
                logger.info("No relevant context found in ChromaDB.")
                return {
                    "answer": "I could not find relevant information in the uploaded medical documents.",
                    "sources": [],
                    "status": "no_context"
                }
            
            # 3. Format the retrieved context segments for the prompt
            context_blocks = []
            for idx, doc in enumerate(retrieved_docs):
                context_blocks.append(
                    f"[Document {idx+1}] File: {doc['metadata']['source']}, Page: {doc['metadata']['page']}\n"
                    f"Content: {doc['page_content']}"
                )
            context_text = "\n\n".join(context_blocks)
            
            # 4. Construct prompt applying healthcare instructions (Step 10 safety guidelines)
            system_instructions = guardrail.apply_prompt_safety()
            
            prompt = (
                f"{system_instructions}\n"
                f"Use the following pieces of retrieved context to answer the user's healthcare query:\n\n"
                f"--- BEGIN RETRIEVED CONTEXT ---\n"
                f"{context_text}\n"
                f"--- END RETRIEVED CONTEXT ---\n\n"
                f"User Question: {query}\n\n"
                f"Format your response professionally in Markdown.\n"
                f"CRITICAL CITATION RULE: Do NOT include any inline citations, document tags, brackets, or references (such as [Document 1], [Document 2], [1], or source file names) within the text of your response. The answer must read naturally and fluidly as a direct explanation. All source information is displayed separately by the user interface.\n"
                f"If the context does not contain the answer, reply exactly: 'I could not find relevant information in the uploaded medical documents.'\n\n"
                f"Answer:"
            )
            
            logger.info("Invoking Gemini 1.5 Flash via LangChain ChatGoogleGenerativeAI...")
            logger.info("===== PROMPT =====")
            logger.info(prompt)

            llm_response = self.llm.invoke(prompt)

            logger.info("===== RAW GEMINI RESPONSE =====")
            logger.info(llm_response)

            answer = llm_response.content.strip()

            logger.info("===== ANSWER =====")
            logger.info(answer)
            
            # If the model explicitly outputs that it couldn't find the answer, respect that
            if "i could not find relevant information" in answer.lower():
                logger.info("Gemini indicated the context was insufficient to answer.")
                return {
                    "answer": "I could not find relevant information in the uploaded medical documents.",
                    "sources": [],
                    "status": "no_context"
                }

            # 5. Apply safety disclaimer filters to the generated answer
            final_answer = guardrail.enforce_output_safety(answer)
            
            # 6. Extract source summaries for citation mapping
            sources = []
            for doc in retrieved_docs:
                sources.append({
                    "source": doc["metadata"]["source"],
                    "page": doc["metadata"]["page"],
                    "relevance_score": doc["relevance_score"]
                })
                
            logger.info("RAG pipeline execution completed successfully.")
            return {
                "answer": final_answer,
                "sources": sources,
                "status": "success"
            }
            
        except Exception as e:
            logger.error(f"Error executing RAG pipeline: {str(e)}")
            raise e

rag_service = RAGService()
