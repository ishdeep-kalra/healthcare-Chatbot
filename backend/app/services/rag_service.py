import os
import json
import math
import string
from typing import List, Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from app.config import settings
from app.services.logger import logger
from app.services.guardrail import guardrail

class RAGService:
    def __init__(self):
        self._llm = None
        self.collection_name = "medical_documents"

    @property
    def llm(self) -> ChatGoogleGenerativeAI:
        """Lazy-loaded Gemini client via LangChain."""
        if self._llm is None:
            logger.info("Initializing ChatGoogleGenerativeAI model: gemini-2.5-flash...")
            self._llm = ChatGoogleGenerativeAI(
                model="gemini-2.5-flash",
                google_api_key=settings.GEMINI_API_KEY,
                temperature=0.2,
                max_tokens=1024
            )
            logger.info("Gemini LLM client initialized successfully.")
        return self._llm

    def _get_storage_path(self) -> str:
        # Save JSON chunks in the parent directory of CHROMA_PERSIST_DIR (which is the data/ folder)
        persist_dir = os.path.abspath(settings.CHROMA_PERSIST_DIR)
        parent_dir = os.path.dirname(persist_dir)
        os.makedirs(parent_dir, exist_ok=True)
        return os.path.join(parent_dir, "medical_chunks.json")

    def _load_chunks(self) -> List[Dict[str, Any]]:
        path = self._get_storage_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                logger.error(f"Error loading chunks from {path}: {e}")
                return []
        return []

    def _save_chunks(self, chunks: List[Dict[str, Any]]) -> None:
        path = self._get_storage_path()
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump(chunks, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving chunks to {path}: {e}")
            raise e

    def add_documents(self, chunks: List[Dict[str, Any]]) -> None:
        """Adds a list of parsed document chunks to the local JSON store."""
        if not chunks:
            logger.warning("No document chunks to save.")
            return

        try:
            logger.info(f"Adding {len(chunks)} chunks to local JSON store...")
            existing_chunks = self._load_chunks()
            
            # Map existing chunks by ID to avoid duplicates
            chunk_dict = {c["id"]: c for c in existing_chunks}
            for chunk in chunks:
                chunk_dict[chunk["id"]] = chunk
                
            self._save_chunks(list(chunk_dict.values()))
            logger.info("Successfully persisted document chunks locally.")
        except Exception as e:
            logger.error(f"Failed to save chunks locally: {str(e)}")
            raise e

    def _tokenize(self, text: str) -> List[str]:
        # Lowercase, remove punctuation, and split by whitespace
        text = text.lower()
        translator = str.maketrans("", "", string.punctuation)
        text = text.translate(translator)
        return text.split()

    def search_similar_documents(self, query: str, k: int = 4) -> List[Dict[str, Any]]:
        """Queries the local JSON store using token matching & TF-IDF score."""
        try:
            logger.info(f"Performing search for query: '{query}' (k={k})")
            chunks = self._load_chunks()
            
            query_tokens = self._tokenize(query)
            if not query_tokens or not chunks:
                logger.info("Empty query tokens or empty chunks store.")
                return []

            # Calculate Document Frequency (DF) for each query token
            df = {token: 0 for token in query_tokens}
            for chunk in chunks:
                content_lower = chunk["page_content"].lower()
                for token in query_tokens:
                    if token in content_lower:
                        df[token] += 1

            N = len(chunks)
            # Calculate IDF for each query token
            idf = {}
            for token, count in df.items():
                idf[token] = math.log((N + 1) / (count + 1)) + 1.0

            scored_chunks = []
            for chunk in chunks:
                content = chunk["page_content"]
                tokens = self._tokenize(content)
                if not tokens:
                    continue

                # Term Frequency (TF) of query tokens in the chunk
                tf = {}
                for t in tokens:
                    if t in query_tokens:
                        tf[t] = tf.get(t, 0) + 1

                # Calculate cumulative TF-IDF score for this chunk
                score = 0.0
                for token in query_tokens:
                    if token in tf:
                        term_tf = tf[token] / len(tokens)
                        score += term_tf * idf[token]

                if score > 0.0:
                    scored_chunks.append((chunk, score))

            # Sort by score descending
            scored_chunks.sort(key=lambda x: x[1], reverse=True)

            results = []
            for chunk, score in scored_chunks[:k]:
                results.append({
                    "page_content": chunk["page_content"],
                    "metadata": chunk["metadata"],
                    "relevance_score": float(score)
                })

            logger.info(f"Retrieved {len(results)} matches from local JSON store.")
            return results
        except Exception as e:
            logger.error(f"Error during local document search: {str(e)}")
            raise e

    def answer_healthcare_query(self, query: str) -> Dict[str, Any]:
        """Runs the full RAG pipeline: retrieves context from the local JSON store,
        builds a safe clinical prompt, and calls Gemini LLM to generate the final response.
        
        Args:
            query (str): The user's medical or healthcare question.
            
        Returns:
            Dict[str, Any]: Dictionary containing the answer text and source metadata list.
        """
        try:
            logger.info(f"Executing RAG pipeline for healthcare query: '{query}'")
            
            # 1. Retrieve top 5 matching text chunks from local JSON store
            retrieved_docs = self.search_similar_documents(query=query, k=5)
            
            # 2. Check if relevant context is found
            if not retrieved_docs:
                logger.info("No relevant context found in local store.")
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
            
            # 4. Construct prompt applying healthcare instructions (safety guidelines)
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
               f"Use the retrieved context whenever it is relevant. If the context only partially answers the question or is insufficient, use your general medical knowledge to provide a helpful and accurate answer. Clearly distinguish information supported by the uploaded documents from information based on general medical knowledge. Never invent facts or citations.\n\n"
                f"Answer:"
            )
            
            logger.info("Invoking Gemini via LangChain ChatGoogleGenerativeAI...")
            logger.info("===== PROMPT =====")
            logger.info(prompt)

            llm_response = self.llm.invoke(prompt)

            logger.info("===== RAW GEMINI RESPONSE =====")
            logger.info(llm_response)

            answer = llm_response.content.strip()

            logger.info("===== ANSWER =====")
            logger.info(answer)
            
           

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
