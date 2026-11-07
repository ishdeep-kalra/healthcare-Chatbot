import os
import json
import math
import string
import asyncio
import re
from typing import List, Dict, Any, Tuple
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


# ---------------------------------------------------------------------------
# Shared system-prompt building blocks
# ---------------------------------------------------------------------------

_SAFETY_BOUNDARY = (
    "SAFETY RULES (non-negotiable):\n"
    "- Never diagnose a patient or confirm a specific disease for the user.\n"
    "- Never prescribe medication, recommend specific drug names, or suggest dosages.\n"
    "- Never fabricate clinical data, statistics, or research citations.\n"
    "- If the question has emergency signs (chest pain, difficulty breathing, etc.), "
    "immediately tell the user to call emergency services.\n\n"
)

_FORMAT_RULES = (
    "FORMAT RULES:\n"
    "- Always respond in Markdown.\n"
    "- Use ## headings to structure long answers.\n"
    "- Use bullet points ( - ) for lists of symptoms, causes, or tips.\n"
    "- Use **bold** for important medical terms on first use.\n"
    "- Keep language clear and accessible - explain jargon in plain English.\n"
    "- Do NOT start the response with a disclaimer or warning.\n"
    "- Do NOT add a generic disclaimer in the middle of the answer.\n"
    "- End every response with ONE natural, specific follow-up question that is "
    "directly relevant to what the user just asked. Never use generic questions "
    "like 'Is there anything else?' or 'Do you have more questions?'.\n\n"
)

_CASUAL_SYSTEM = (
    "You are MedAI, a warm and friendly Healthcare AI Assistant.\n\n"
    "TASK: Respond naturally to the user's greeting or casual message.\n\n"
    "RULES:\n"
    "- Use a friendly, conversational tone.\n"
    "- Keep the reply short (2-4 sentences max).\n"
    "- Briefly mention that you can help with medical questions or explain uploaded reports.\n"
    "- Do NOT use medical jargon or give unsolicited health advice.\n"
    "- Do NOT add disclaimers.\n"
    "- End with a natural, inviting follow-up question (e.g. 'What health topic can I help you with today?').\n"
)

_GENERAL_MEDICAL_SYSTEM = (
    "You are MedAI, an expert Healthcare AI Assistant with deep medical knowledge.\n\n"
    + _SAFETY_BOUNDARY
    + _FORMAT_RULES
    + "TASK: Answer the user's medical question accurately, in depth, and in plain language.\n\n"
    "GUIDELINES:\n"
    "- Explain the concept clearly, as if talking to an intelligent patient who is NOT a doctor.\n"
    "- Structure your answer with sections where appropriate: e.g. ## What is it?, "
    "## Causes, ## Symptoms, ## Complications, ## When to see a doctor.\n"
    "- Use real-world examples or analogies to make complex ideas easy to understand.\n"
    "- If comparing two things (e.g. Type 1 vs Type 2), use a comparison table in Markdown.\n"
    "- Do NOT refer to any uploaded documents, PDFs, context, or retrieved passages.\n"
    "- Do NOT start with 'I am an AI' or any robotic preamble.\n"
)

_DOCUMENT_SYSTEM = (
    "You are MedAI, an expert Healthcare AI Assistant reviewing medical records.\n\n"
    + _SAFETY_BOUNDARY
    + _FORMAT_RULES
    + "TASK: Answer the user's question using the medical document context provided below.\n\n"
    "CRITICAL RULES FOR DOCUMENT ANSWERS:\n"
    "- Integrate the retrieved context seamlessly into your answer as if you are directly "
    "reviewing the patient's records. Never say 'the document says', 'according to the PDF', "
    "'the provided text', 'the context states', 'based on the uploaded file', or any similar phrase.\n"
    "- If the retrieved context is not relevant to the question, rely on general medical knowledge "
    "and do NOT invent document content.\n"
    "- Distinguish clearly between what is clinically established and what requires a doctor's judgment.\n"
)


class RAGService:
    def __init__(self):
        self._llm = None
        self.collection_name = "medical_documents"
        self._cached_chunks = None
        self._answer_cache = {}

    # ------------------------------------------------------------------
    # LLM lazy-loader
    # ------------------------------------------------------------------

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
                        temperature=0.3,
                    )
                    logger.info("Ollama LLM initialized successfully.")
                    return self._llm

            # Default: Gemini
            logger.info("Initializing ChatGoogleGenerativeAI model: gemini-1.5-flash...")
            self._llm = ChatGoogleGenerativeAI(
                model="gemini-1.5-flash",
                google_api_key=settings.GEMINI_API_KEY,
                temperature=0.3,
                max_tokens=2048,
            )
            logger.info("Gemini LLM initialized successfully.")

        return self._llm

    # ------------------------------------------------------------------
    # JSON chunk store helpers
    # ------------------------------------------------------------------

    def _get_storage_path(self) -> str:
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

            chunk_dict = {c["id"]: c for c in existing_chunks}
            for chunk in chunks:
                chunk_dict[chunk["id"]] = chunk

            updated_chunks = list(chunk_dict.values())
            self._save_chunks(updated_chunks)

            self._cached_chunks = updated_chunks
            self._answer_cache.clear()

            logger.info("Successfully persisted document chunks locally and cleared answer cache.")
        except Exception as e:
            logger.error(f"Failed to save chunks locally: {str(e)}")
            raise e

    # ------------------------------------------------------------------
    # TF-IDF + Cosine Similarity retrieval
    # ------------------------------------------------------------------

    def _tokenize(self, text: str) -> List[str]:
        """Tokenize text: lowercase, remove punctuation, remove stopwords."""
        text = text.lower()
        translator = str.maketrans("", "", string.punctuation)
        text = text.translate(translator)
        tokens = text.split()
        stopwords = {
            "the", "and", "or", "a", "an", "of", "in", "on", "for", "to",
            "with", "is", "are", "was", "were", "be", "been", "has",
            "have", "had", "by", "as", "at", "from", "it", "its",
            "that", "this", "these", "those", "not", "but", "if",
        }
        return [t for t in tokens if t not in stopwords and len(t) > 1]

    def search_similar_documents(self, query: str, k: int = 4) -> List[Dict[str, Any]]:
        """Retrieve top-k document chunks using TF-IDF cosine similarity."""
        try:
            logger.info(f"Performing search for query: '{query}' (k={k})")
            chunks = self._load_chunks()

            query_tokens = self._tokenize(query)
            if not query_tokens or not chunks:
                logger.info("Empty query tokens or empty chunks store.")
                return []

            # --- Document Frequency (DF) ---
            df: Dict[str, int] = {token: 0 for token in set(query_tokens)}
            for chunk in chunks:
                content_lower = chunk["page_content"].lower()
                for token in df:
                    if token in content_lower:
                        df[token] += 1

            N = len(chunks)

            # --- Inverse Document Frequency (IDF) ---
            idf: Dict[str, float] = {
                token: math.log((N + 1) / (count + 1)) + 1.0
                for token, count in df.items()
            }

            # --- TF-IDF vector for the query ---
            query_vec: Dict[str, float] = {}
            for token in set(query_tokens):
                tf = query_tokens.count(token) / len(query_tokens)
                query_vec[token] = tf * idf.get(token, 0.0)

            mag_q = math.sqrt(sum(v * v for v in query_vec.values()))
            if mag_q == 0:
                return []

            # --- Score each chunk ---
            scored: List[Tuple[Dict[str, Any], float]] = []
            for chunk in chunks:
                doc_tokens = self._tokenize(chunk["page_content"])
                if not doc_tokens:
                    continue

                doc_vec: Dict[str, float] = {}
                for token in set(doc_tokens):
                    tf = doc_tokens.count(token) / len(doc_tokens)
                    doc_vec[token] = tf * idf.get(token, 0.0)

                mag_d = math.sqrt(sum(v * v for v in doc_vec.values()))
                if mag_d == 0:
                    continue

                dot = sum(
                    query_vec.get(t, 0.0) * doc_vec.get(t, 0.0)
                    for t in set(query_vec) & set(doc_vec)
                )
                cosine_sim = dot / (mag_q * mag_d)
                if cosine_sim > 0.0:
                    scored.append((chunk, cosine_sim))

            scored.sort(key=lambda x: x[1], reverse=True)

            results = [
                {
                    "page_content": chunk["page_content"],
                    "metadata": chunk["metadata"],
                    "relevance_score": float(score),
                }
                for chunk, score in scored[:k]
            ]

            logger.info(f"Retrieved {len(results)} matches from local JSON store.")
            return results

        except Exception as e:
            logger.error(f"Error during local document search: {str(e)}")
            raise e

    # ------------------------------------------------------------------
    # Intent classification
    # ------------------------------------------------------------------

    def _normalize_query(self, query: str) -> str:
        return query.strip().lower().rstrip("?").strip()

    def classify_intent(self, query: str) -> str:
        """Classifies the query intent: CASUAL_CHAT | DOCUMENT_QUERY | GENERAL_MEDICAL."""
        cleaned = query.strip().lower()

        # 1. CASUAL_CHAT
        casual_patterns = [
            r"^\s*hi\s*$", r"^\s*hello\b", r"^\s*hey\b",
            r"good\s*morning", r"good\s*afternoon", r"good\s*evening",
            r"greetings", r"thank\s*s?", r"thank\s*you",
            r"who\s*are\s*you", r"what\s*can\s*you\s*do",
            r"what\s*is\s*your\s*name", r"how\s*are\s*you",
            r"how's\s*it\s*going", r"what's\s*up",
            r"^\s*help\s*$", r"gday", r"welcome",
        ]
        for pattern in casual_patterns:
            if re.search(pattern, cleaned):
                return "CASUAL_CHAT"

        # 2. DOCUMENT_QUERY
        document_patterns = [
            r"\bmy\s*(report|mri|blood|scan|prescription|file|pdf|document|test|ct|results|record|chart)\b",
            r"\bthis\s*(uploaded|prescription|report|pdf|document|file|mri|ct|scan)\b",
            r"\b(uploaded|my)\s*(reports|mris|scans|prescriptions|documents|files|tests)\b",
            r"\b(summarize|explain|read|check|parse|analyze)\s*(my|this|the\s*uploaded)\b",
            r"in\s*my\s*(report|mri|blood|scan|prescription|file|pdf|document|test|ct)",
            r"\bblood\s*test\s*indicate\b",
            r"\babnormalities\s*in\s*my\b",
            r"uploaded\s*report", r"uploaded\s*prescription",
            r"uploaded\s*mri", r"uploaded\s*scan",
            r"uploaded\s*document", r"uploaded\s*pdf",
        ]
        for pattern in document_patterns:
            if re.search(pattern, cleaned):
                return "DOCUMENT_QUERY"

        # 3. Default
        return "GENERAL_MEDICAL"

    # ------------------------------------------------------------------
    # LLM streaming
    # ------------------------------------------------------------------

    async def _stream_llm(self, prompt: str):
        """Stream LLM response token-by-token."""
        try:
            async for chunk in self.llm.astream(prompt):
                if chunk and chunk.content:
                    yield chunk.content
        except Exception as e:
            logger.error(f"Error during LLM streaming: {str(e)}")
            error_msg = str(e)
            if settings.LLM_PROVIDER.lower() == "ollama" and (
                "connect" in error_msg.lower() or "refused" in error_msg.lower()
            ):
                yield (
                    "\n\n-- **Ollama Service Unavailable**\n\n"
                    "I was unable to connect to the local Ollama service. "
                    "Please ensure Ollama is running and the model is loaded."
                )
            else:
                yield (
                    "\n\n-- **Inference Error**\n\n"
                    "An error occurred while generating the response. "
                    "Please check the backend logs for details."
                )

    # ------------------------------------------------------------------
    # Streaming answer generation
    # ------------------------------------------------------------------

    async def answer_healthcare_query_stream(self, query: str):
        """Stream the full RAG pipeline with status events, tokens and sources."""

        norm_query = self._normalize_query(query)

        # --- Cache hit ---
        if norm_query in self._answer_cache:
            logger.info(f"Cache hit for query: '{query}'")
            cached = self._answer_cache[norm_query]
            yield {"type": "status", "message": "- Generating response..."}
            await asyncio.sleep(0.05)
            model_name = "Gemini" if settings.LLM_PROVIDER.lower() != "ollama" else "Ollama (Local)"
            yield {"type": "model", "name": model_name}
            if cached["sources"]:
                yield {"type": "sources", "sources": cached["sources"]}
            for word in cached["answer"].split(" "):
                yield {"type": "token", "content": word + " "}
                await asyncio.sleep(0.008)
            yield {"type": "status", "message": "- Done"}
            return

        # --- Input guardrail ---
        validation = guardrail.inspect_input(query)
        if not validation["is_allowed"]:
            logger.warning(f"Safety check blocked query: {validation['reason']}")
            yield {"type": "status", "message": "- Safety check triggered..."}
            await asyncio.sleep(0.05)
            model_name = "Gemini" if settings.LLM_PROVIDER.lower() != "ollama" else "Ollama (Local)"
            yield {"type": "model", "name": model_name}
            for word in validation["message"].split(" "):
                yield {"type": "token", "content": word + " "}
                await asyncio.sleep(0.008)
            return

        # --- Classify intent ---
        intent = self.classify_intent(query)
        logger.info(f"Classified query intent: {intent}")
        model_name = "Gemini" if settings.LLM_PROVIDER.lower() != "ollama" else "Ollama (Local)"

        # ---- CASUAL_CHAT ----
        if intent == "CASUAL_CHAT":
            yield {"type": "status", "message": "- Composing reply..."}
            await asyncio.sleep(0.05)
            yield {"type": "model", "name": model_name}

            prompt = (
                f"{_CASUAL_SYSTEM}\n\n"
                f"User message: {query}\n\n"
                f"Reply:"
            )
            async for token in self._stream_llm(prompt):
                yield {"type": "token", "content": token}
            yield {"type": "status", "message": "- Done"}
            return

        # ---- GENERAL_MEDICAL ----
        if intent == "GENERAL_MEDICAL":
            yield {"type": "status", "message": "- Thinking..."}
            await asyncio.sleep(0.05)
            yield {"type": "model", "name": model_name}

            prompt = (
                f"{_GENERAL_MEDICAL_SYSTEM}\n\n"
                f"User question: {query}\n\n"
                f"Answer:"
            )
            accumulated = ""
            async for token in self._stream_llm(prompt):
                accumulated += token
                yield {"type": "token", "content": token}

            yield {"type": "status", "message": "- Done"}

            final = guardrail.enforce_output_safety(accumulated, "GENERAL_MEDICAL")
            if len(final) > len(accumulated):
                yield {"type": "token", "content": final[len(accumulated):]}

            self._answer_cache[norm_query] = {"answer": final, "sources": [], "status": "success"}
            return

        # ---- DOCUMENT_QUERY ----
        chunks = self._load_chunks()
        if not chunks:
            logger.info("No documents uploaded yet.")
            yield {"type": "status", "message": "- Generating response..."}
            await asyncio.sleep(0.05)
            yield {"type": "model", "name": model_name}
            msg = (
                "It looks like no medical documents have been uploaded yet. "
                "Please upload your report or PDF, and I'll explain it in plain language. "
                "Alternatively, feel free to ask me any general health question!"
            )
            for word in msg.split(" "):
                yield {"type": "token", "content": word + " "}
                await asyncio.sleep(0.008)
            yield {"type": "status", "message": "- Done"}
            return

        yield {"type": "status", "message": "- Searching your medical documents..."}
        await asyncio.sleep(0.05)

        retrieved_docs = self.search_similar_documents(query=query, k=4)

        yield {"type": "status", "message": "- Generating response..."}
        await asyncio.sleep(0.05)

        context_blocks = []
        for idx, doc in enumerate(retrieved_docs):
            context_blocks.append(
                f"[Passage {idx + 1}]\n{doc['page_content']}"
            )
        context_text = "\n\n".join(context_blocks) if context_blocks else "No relevant passages found."

        sources = [
            {
                "source": doc["metadata"]["source"],
                "page": doc["metadata"]["page"],
                "relevance_score": doc["relevance_score"],
            }
            for doc in retrieved_docs
        ]
        if sources:
            yield {"type": "sources", "sources": sources}

        yield {"type": "model", "name": model_name}

        prompt = (
            f"{_DOCUMENT_SYSTEM}\n\n"
            f"Retrieved context:\n{context_text}\n\n"
            f"User question: {query}\n\n"
            f"Answer:"
        )

        accumulated = ""
        async for token in self._stream_llm(prompt):
            accumulated += token
            yield {"type": "token", "content": token}

        yield {"type": "status", "message": "- Done"}

        final = guardrail.enforce_output_safety(accumulated, "DOCUMENT_QUERY")
        if len(final) > len(accumulated):
            yield {"type": "token", "content": final[len(accumulated):]}

        self._answer_cache[norm_query] = {"answer": final, "sources": sources, "status": "success"}

    # ------------------------------------------------------------------
    # Synchronous (non-streaming) fallback
    # ------------------------------------------------------------------

    def answer_healthcare_query(self, query: str) -> Dict[str, Any]:
        """Synchronous RAG query handler (non-streaming fallback)."""
        try:
            norm_query = self._normalize_query(query)
            if norm_query in self._answer_cache:
                logger.info(f"Cache hit (sync) for query: '{query}'")
                return self._answer_cache[norm_query]

            validation = guardrail.inspect_input(query)
            if not validation["is_allowed"]:
                return {"answer": validation["message"], "sources": [], "status": "blocked"}

            intent = self.classify_intent(query)
            logger.info(f"Classified query intent (sync): {intent}")

            if intent == "CASUAL_CHAT":
                prompt = f"{_CASUAL_SYSTEM}\n\nUser message: {query}\n\nReply:"
                llm_response = self.llm.invoke(prompt)
                return {"answer": llm_response.content.strip(), "sources": [], "status": "success"}

            if intent == "GENERAL_MEDICAL":
                prompt = f"{_GENERAL_MEDICAL_SYSTEM}\n\nUser question: {query}\n\nAnswer:"
                llm_response = self.llm.invoke(prompt)
                answer = llm_response.content.strip()
                final = guardrail.enforce_output_safety(answer, "GENERAL_MEDICAL")
                res = {"answer": final, "sources": [], "status": "success"}
                self._answer_cache[norm_query] = res
                return res

            # DOCUMENT_QUERY
            chunks = self._load_chunks()
            if not chunks:
                return {
                    "answer": (
                        "It looks like no medical documents have been uploaded yet. "
                        "Please upload your report or PDF, and I'll explain it in plain language."
                    ),
                    "sources": [],
                    "status": "success",
                }

            retrieved_docs = self.search_similar_documents(query=query, k=4)
            context_blocks = [
                f"[Passage {idx + 1}]\n{doc['page_content']}"
                for idx, doc in enumerate(retrieved_docs)
            ]
            context_text = "\n\n".join(context_blocks) if context_blocks else "No relevant passages found."

            prompt = (
                f"{_DOCUMENT_SYSTEM}\n\n"
                f"Retrieved context:\n{context_text}\n\n"
                f"User question: {query}\n\n"
                f"Answer:"
            )

            llm_response = self.llm.invoke(prompt)
            answer = llm_response.content.strip()
            final = guardrail.enforce_output_safety(answer, "DOCUMENT_QUERY")

            sources = [
                {
                    "source": doc["metadata"]["source"],
                    "page": doc["metadata"]["page"],
                    "relevance_score": doc["relevance_score"],
                }
                for doc in retrieved_docs
            ]
            res = {"answer": final, "sources": sources, "status": "success"}
            self._answer_cache[norm_query] = res
            return res

        except Exception as e:
            logger.error(f"Error in sync RAG answer generation: {e}")
            raise e


rag_service = RAGService()
