import os
import json
import math
import string
import asyncio
import re
from typing import List, Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
try:
    from langchain_ollama import ChatOllama
    _OLLAMA_AVAILABLE = True
except ImportError:
    _OLLAMA_AVAILABLE = False
    ChatOllama = None
from app.config import settings
from app.services.logger import logger
from app.services.guardrail import guardrail

class RAGService:
    def __init__(self):
        self._llm = None
        self.collection_name = "medical_documents"
        self._cached_chunks = None
        self._answer_cache = {}

    @property
    def llm(self):
        """Lazy-loaded LLM client (Gemini or Ollama)."""
        if self._llm is None:

            if settings.LLM_PROVIDER.lower() == "ollama":
                if not _OLLAMA_AVAILABLE:
                    logger.warning("langchain-ollama not installed; falling back to Gemini.")
                else:
                    logger.info(f"Initializing Ollama model: {settings.OLLAMA_MODEL}...")
                    self._llm = ChatOllama(
                        model=settings.OLLAMA_MODEL,
                        temperature=0.2,
                    )
                    logger.info("Ollama LLM initialized successfully.")
                    return self._llm

            else:
                logger.info("Initializing ChatGoogleGenerativeAI model: gemini-2.5-flash...")
                self._llm = ChatGoogleGenerativeAI(
                    model="gemini-2.5-flash",
                    google_api_key=settings.GEMINI_API_KEY,
                    temperature=0.2,
                    max_tokens=1024,
                )
                logger.info("Gemini LLM initialized successfully.")

        return self._llm

    def _get_storage_path(self) -> str:
        # Save JSON chunks in the parent directory of CHROMA_PERSIST_DIR (which is the data/ folder)
        persist_dir = os.path.abspath(settings.CHROMA_PERSIST_DIR)
        parent_dir = os.path.dirname(persist_dir)
        os.makedirs(parent_dir, exist_ok=True)
        return os.path.join(parent_dir, "medical_chunks.json")

    def _load_chunks(self) -> List[Dict[str, Any]]:
        if self._cached_chunks is not None:
            return self._cached_chunks
        path = self._get_storage_path()
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    self._cached_chunks = json.load(f)
                    return self._cached_chunks
            except Exception as e:
                logger.error(f"Error loading chunks from {path}: {e}")
                return []
        self._cached_chunks = []
        return self._cached_chunks

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
                
            updated_chunks = list(chunk_dict.values())
            self._save_chunks(updated_chunks)
            
            # Update the in-memory cache
            self._cached_chunks = updated_chunks
            
            # Clear answer cache since new context is added
            self._answer_cache.clear()
            
            logger.info("Successfully persisted document chunks locally and cleared answer cache.")
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

    def _normalize_query(self, query: str) -> str:
        return query.strip().lower().rstrip("?").strip()

    def classify_intent(self, query: str) -> str:
        """Classifies the query intent into CASUAL_CHAT, DOCUMENT_QUERY, or GENERAL_MEDICAL."""
        cleaned = query.strip().lower()
        
        # 1. CASUAL_CHAT Keywords (regex)
        casual_patterns = [
            r"^\s*hi\s*$", r"^\s*hello\b", r"^\s*hey\b", r"good\s*morning", r"good\s*afternoon", r"good\s*evening",
            r"greetings", r"thank\s*s?", r"thank\s*you", r"who\s*are\s*you", r"what\s*can\s*you\s*do",
            r"what\s*is\s*your\s*name", r"how\s*are\s*you", r"how's\s*it\s*going", r"what's\s*up", r"help", r"gday", r"welcome"
        ]
        for pattern in casual_patterns:
            if re.search(pattern, cleaned):
                return "CASUAL_CHAT"
                
        # 2. DOCUMENT_QUERY Keywords (regex)
        document_patterns = [
            r"\bmy\s*(report|mri|blood|scan|prescription|file|pdf|document|test|ct|results|record|chart)\b",
            r"\bthis\s*(uploaded|prescription|report|pdf|document|file|mri|ct|scan)\b",
            r"\b(uploaded|my)\s*(reports|mris|scans|prescriptions|documents|files|tests)\b",
            r"\b(summarize|explain|read|check|parse|analyze)\s*(my|this|the\s*uploaded)\b",
            r"in\s*my\s*(report|mri|blood|scan|prescription|file|pdf|document|test|ct)",
            r"\bblood\s*test\s*indicate\b",
            r"\babnormalities\s*in\s*my\b",
            r"uploaded\s*report", r"uploaded\s*prescription", r"uploaded\s*mri", r"uploaded\s*scan", r"uploaded\s*document", r"uploaded\s*pdf"
        ]
        for pattern in document_patterns:
            if re.search(pattern, cleaned):
                return "DOCUMENT_QUERY"
                
        # 3. Default to GENERAL_MEDICAL
        return "GENERAL_MEDICAL"

    async def _stream_llm(self, prompt: str):
        """Streams the LLM response token-by-token with friendly error handling (Feature 10)."""
        try:
            async for chunk in self.llm.astream(prompt):
                if chunk and chunk.content:
                    yield chunk.content
        except Exception as e:
            logger.error(f"Error during LLM streaming: {str(e)}")
            error_msg = str(e)
            if settings.LLM_PROVIDER.lower() == "ollama" and ("connect" in error_msg.lower() or "connection" in error_msg.lower() or "refused" in error_msg.lower()):
                yield (
                    "\n\n🖥️ **Ollama Service Unavailable**\n\n"
                    "I was unable to connect to the local Ollama service. "
                    "Please ensure that the Ollama app is running locally on your computer "
                    "and that the model is loaded, or switch the LLM_PROVIDER in the settings."
                )
            else:
                yield (
                    "\n\n⚠️ **Inference Error**\n\n"
                    "An error occurred while generating the response from the LLM. "
                    "Please check the backend log files for details."
                )

    async def answer_healthcare_query_stream(self, query: str):
        """Asynchronously streams the healthcare query process, yielding status updates,
        model info, source citations, and the generated text token-by-token.
        """
        # 1. Check in-memory answer cache first (Feature 8)
        norm_query = self._normalize_query(query)
        if norm_query in self._answer_cache:
            logger.info(f"Cache hit for query: '{query}'")
            cached_data = self._answer_cache[norm_query]
            
            yield {"type": "status", "message": "🧠 Generating response..."}
            await asyncio.sleep(0.1)
            
            model_name = "Gemini" if settings.LLM_PROVIDER.lower() == "gemini" else "Ollama (Local)"
            yield {"type": "model", "name": model_name}
            
            if cached_data["sources"]:
                yield {"type": "sources", "sources": cached_data["sources"]}
            
            answer_text = cached_data["answer"]
            words = answer_text.split(" ")
            for i, word in enumerate(words):
                space = " " if i > 0 else ""
                yield {"type": "token", "content": space + word}
                await asyncio.sleep(0.01)
            
            yield {"type": "status", "message": "✍️ Writing answer..."}
            await asyncio.sleep(0.05)
            return

        # 2. Check input guardrails
        validation = guardrail.inspect_input(query)
        if not validation["is_allowed"]:
            logger.warning(f"Safety check blocked query: {validation['reason']}")
            yield {"type": "status", "message": "🚨 Safety check triggered..."}
            await asyncio.sleep(0.1)
            
            model_name = "Gemini" if settings.LLM_PROVIDER.lower() == "gemini" else "Ollama (Local)"
            yield {"type": "model", "name": model_name}
            
            answer_text = validation["message"]
            words = answer_text.split(" ")
            for i, word in enumerate(words):
                space = " " if i > 0 else ""
                yield {"type": "token", "content": space + word}
                await asyncio.sleep(0.01)
            return

        # 3. Classify query intent
        intent = self.classify_intent(query)
        logger.info(f"Classified query intent: {intent}")

        # 4. Handle CASUAL_CHAT
        if intent == "CASUAL_CHAT":
            yield {"type": "status", "message": "🧠 Generating response..."}
            await asyncio.sleep(0.1)
            
            model_name = "Gemini" if settings.LLM_PROVIDER.lower() == "gemini" else "Ollama (Local)"
            yield {"type": "model", "name": model_name}
            
            system_instructions = (
                "You are a helpful Healthcare AI Assistant. Respond politely, warmly, and briefly to the casual chat or greeting. "
                "Advise the user that they can upload medical documents for explanation, or ask health-related questions. "
                "Every response MUST naturally end with a relevant, contextual follow-up question based on the topic. "
                "Never end with generic questions like 'Anything else?'."
            )
            prompt = (
                f"{system_instructions}\n\n"
                f"User Query: {query}\n\n"
                f"Answer:"
            )
            
            async for token in self._stream_llm(prompt):
                yield {"type": "token", "content": token}
            
            yield {"type": "status", "message": "✍️ Writing answer..."}
            return

        # 5. Handle GENERAL_MEDICAL
        if intent == "GENERAL_MEDICAL":
            yield {"type": "status", "message": "🧠 Generating response..."}
            await asyncio.sleep(0.1)
            
            model_name = "Gemini" if settings.LLM_PROVIDER.lower() == "gemini" else "Ollama (Local)"
            yield {"type": "model", "name": model_name}
            
            system_instructions = (
                "You are a Healthcare AI Assistant. Safety: You cannot diagnose conditions, prescribe medications, or recommend dosages. "
                "For educational questions, answer directly, explaining concepts naturally and objectively. "
                "Do NOT start your response with a disclaimer or advice to consult a doctor. "
                "Rules: Answer the medical question directly using reliable medical knowledge. "
                "Do NOT refer to or mention any uploaded documents, PDFs, or context. "
                "Answer naturally and professionally in Markdown.\n"
                "Every response MUST naturally end with a relevant, contextual follow-up question based on the topic. "
                "Never end with generic questions like 'Anything else?'."
            )
            prompt = (
                f"{system_instructions}\n\n"
                f"Question: {query}\n\n"
                f"Answer:"
            )
            
            accumulated_answer = ""
            async for token in self._stream_llm(prompt):
                accumulated_answer += token
                yield {"type": "token", "content": token}
                
            yield {"type": "status", "message": "✍️ Writing answer..."}
            
            final_answer = guardrail.enforce_output_safety(accumulated_answer, "GENERAL_MEDICAL")
            if len(final_answer) > len(accumulated_answer):
                disclaimer_diff = final_answer[len(accumulated_answer):]
                yield {"type": "token", "content": disclaimer_diff}
                
            self._answer_cache[norm_query] = {
                "answer": final_answer,
                "sources": [],
                "status": "success"
            }
            return

        # 6. Handle DOCUMENT_QUERY
        # Check if documents exist in local store
        chunks = self._load_chunks()
        if not chunks:
            logger.info("No documents uploaded yet, returning natural warning.")
            yield {"type": "status", "message": "🧠 Generating response..."}
            await asyncio.sleep(0.1)
            
            model_name = "Gemini" if settings.LLM_PROVIDER.lower() == "gemini" else "Ollama (Local)"
            yield {"type": "model", "name": model_name}
            
            warning_text = "I don't see any uploaded medical documents yet. Please upload your report and I'll help explain it."
            words = warning_text.split(" ")
            for i, word in enumerate(words):
                space = " " if i > 0 else ""
                yield {"type": "token", "content": space + word}
                await asyncio.sleep(0.01)
                
            yield {"type": "status", "message": "✍️ Writing answer..."}
            return

        # Documents exist: perform RAG
        yield {"type": "status", "message": "🔍 Analyzing uploaded medical documents..."}
        await asyncio.sleep(0.1)
        
        retrieved_docs = self.search_similar_documents(query=query, k=3)
        
        yield {"type": "status", "message": "✓ Relevant medical information found."}
        await asyncio.sleep(0.1)
        yield {"type": "status", "message": "🧠 Generating response..."}
        await asyncio.sleep(0.1)
        
        context_blocks = []
        for idx, doc in enumerate(retrieved_docs):
            context_blocks.append(
                f"[Document {idx+1}] File: {doc['metadata']['source']}, Page: {doc['metadata']['page']}\n"
                f"Content: {doc['page_content']}"
            )
        context_text = "\n\n".join(context_blocks)
        
        sources = []
        for doc in retrieved_docs:
            sources.append({
                "source": doc["metadata"]["source"],
                "page": doc["metadata"]["page"],
                "relevance_score": doc["relevance_score"]
            })
            
        yield {"type": "sources", "sources": sources}
        
        model_name = "Gemini" if settings.LLM_PROVIDER.lower() == "gemini" else "Ollama (Local)"
        yield {"type": "model", "name": model_name}
        
        system_instructions = (
            "You are a Healthcare AI Assistant. Safety: Do NOT diagnose the user or prescribe medication. Answer educational questions naturally, explaining findings objectively. Never start your response with a disclaimer or warning. "
            "Rules: Answer the user's question by combining the retrieved document context below with reliable medical knowledge. "
            "CRITICAL: Do NOT mention where the information is coming from. Never use words like 'provided documents', 'provided text', 'uploaded files', 'the document', 'the report', 'the context', 'retrieved context', 'uploaded PDF', 'page number', or 'according to the report'. Write the response seamlessly as if you are directly reviewing the patient's records or explaining general concepts. Do not say 'based on the documents' or 'the documents state'.\n"
            "Every response MUST naturally end with a relevant, contextual follow-up question based on the topic. "
            "Never end with generic questions like 'Anything else?'."
        )
        
        prompt = (
            f"{system_instructions}\n\n"
            f"Context:\n{context_text}\n\n"
            f"Question: {query}\n\n"
            f"Answer:"
        )
        
        accumulated_answer = ""
        async for token in self._stream_llm(prompt):
            accumulated_answer += token
            yield {"type": "token", "content": token}
            
        yield {"type": "status", "message": "✍️ Writing answer..."}
        
        final_answer = guardrail.enforce_output_safety(accumulated_answer, "DOCUMENT_QUERY")
        if len(final_answer) > len(accumulated_answer):
            disclaimer_diff = final_answer[len(accumulated_answer):]
            yield {"type": "token", "content": disclaimer_diff}
            
        self._answer_cache[norm_query] = {
            "answer": final_answer,
            "sources": sources,
            "status": "success"
        }

    def answer_healthcare_query(self, query: str) -> Dict[str, Any]:
        """Backward-compatible synchronous query generator using cached result or standard run."""
        try:
            norm_query = self._normalize_query(query)
            if norm_query in self._answer_cache:
                logger.info(f"Cache hit (sync) for query: '{query}'")
                return self._answer_cache[norm_query]

            validation = guardrail.inspect_input(query)
            if not validation["is_allowed"]:
                return {
                    "answer": validation["message"],
                    "sources": [],
                    "status": "blocked"
                }

            intent = self.classify_intent(query)
            logger.info(f"Classified query intent (sync): {intent}")

            if intent == "CASUAL_CHAT":
                system_instructions = (
                    "You are a helpful Healthcare AI Assistant. Respond politely, warmly, and briefly to the casual chat or greeting. "
                    "Advise the user that they can upload medical documents for explanation, or ask health-related questions. "
                    "Every response MUST naturally end with a relevant, contextual follow-up question based on the topic. "
                    "Never end with generic questions like 'Anything else?'."
                )
                prompt = f"{system_instructions}\n\nUser Query: {query}\n\nAnswer:"
                llm_response = self.llm.invoke(prompt)
                answer = llm_response.content.strip()
                return {
                    "answer": answer,
                    "sources": [],
                    "status": "success"
                }

            if intent == "GENERAL_MEDICAL":
                system_instructions = (
                    "You are a Healthcare AI Assistant. Safety: You cannot diagnose conditions, prescribe medications, or recommend dosages. "
                    "For educational questions, answer directly, explaining concepts naturally and objectively. "
                    "Do NOT start your response with a disclaimer or advice to consult a doctor. "
                    "Rules: Answer the medical question directly using reliable medical knowledge. "
                    "Do NOT refer to or mention any uploaded documents, PDFs, or context. "
                    "Answer naturally and professionally in Markdown.\n"
                    "Every response MUST naturally end with a relevant, contextual follow-up question based on the topic. "
                    "Never end with generic questions like 'Anything else?'."
                )
                prompt = f"{system_instructions}\n\nQuestion: {query}\n\nAnswer:"
                llm_response = self.llm.invoke(prompt)
                answer = llm_response.content.strip()
                final_answer = guardrail.enforce_output_safety(answer, "GENERAL_MEDICAL")
                res = {
                    "answer": final_answer,
                    "sources": [],
                    "status": "success"
                }
                self._answer_cache[norm_query] = res
                return res

            # DOCUMENT_QUERY
            chunks = self._load_chunks()
            if not chunks:
                return {
                    "answer": "I don't see any uploaded medical documents yet. Please upload your report and I'll help explain it.",
                    "sources": [],
                    "status": "success"
                }

            retrieved_docs = self.search_similar_documents(query=query, k=3)
            context_blocks = []
            for idx, doc in enumerate(retrieved_docs):
                context_blocks.append(
                    f"[Document {idx+1}] File: {doc['metadata']['source']}, Page: {doc['metadata']['page']}\n"
                    f"Content: {doc['page_content']}"
                )
            context_text = "\n\n".join(context_blocks)

            system_instructions = (
                "You are a Healthcare AI Assistant. Safety: Do NOT diagnose the user or prescribe medication. Answer educational questions naturally, explaining findings objectively. Never start your response with a disclaimer or warning. "
                "Rules: Answer the user's question by combining the retrieved document context below with reliable medical knowledge. "
                "CRITICAL: Do NOT mention where the information is coming from. Never use words like 'provided documents', 'provided text', 'uploaded files', 'the document', 'the report', 'the context', 'retrieved context', 'uploaded PDF', 'page number', or 'according to the report'. Write the response seamlessly as if you are directly reviewing the patient's records or explaining general concepts. Do not say 'based on the documents' or 'the documents state'.\n"
                "Every response MUST naturally end with a relevant, contextual follow-up question based on the topic. "
                "Never end with generic questions like 'Anything else?'."
            )
            prompt = (
                f"{system_instructions}\n\n"
                f"Context:\n{context_text}\n\n"
                f"Question: {query}\n\n"
                f"Answer:"
            )

            llm_response = self.llm.invoke(prompt)
            answer = llm_response.content.strip()

            final_answer = guardrail.enforce_output_safety(answer, "DOCUMENT_QUERY")
            sources = []
            for doc in retrieved_docs:
                sources.append({
                    "source": doc["metadata"]["source"],
                    "page": doc["metadata"]["page"],
                    "relevance_score": doc["relevance_score"]
                })

            res = {
                "answer": final_answer,
                "sources": sources,
                "status": "success"
            }
            self._answer_cache[norm_query] = res
            return res
        except Exception as e:
            logger.error(f"Error in sync RAG answer generation: {e}")
            raise e

rag_service = RAGService()
