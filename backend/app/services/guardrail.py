import re
from typing import Dict, Any

EMERGENCY_KEYWORDS = [
    r"chest\s*pain", r"difficulty\s*breathing", r"shortness\s*of\s*breath",
    r"stroke", r"heart\s*attack", r"heavy\s*bleeding", r"unconscious",
    r"poison", r"suicide", r"kill\s*myself", r"choking", r"severe\s*allergic\s*reaction",
    r"anaphylaxis", r"seizure"
]

PRESCRIPTION_DIAGNOSIS_KEYWORDS = [
    r"prescribe", r"prescription", r"write\s*a\s*rx", r"diagnose\s*me",
    r"what\s*disease\s*do\s*i\s*have", r"what\s*is\s*my\s*diagnosis",
    r"what\s*medicine\s*should\s*i\s*take", r"give\s*me\s*medication",
    r"dosing\s*for", r"dosage\s*of"
]

MEDICAL_DISCLAIMER = (
    "\n\n***Disclaimer:** This information is retrieved from your uploaded medical documents "
    "for educational/informational reference. It is NOT a clinical diagnosis, prescription, "
    "or substitute for professional medical advice. If you are experiencing persistent or "
    "severe symptoms, please consult a licensed healthcare provider.*"
)

class HealthcareGuardrail:
    @staticmethod
    def inspect_input(query: str) -> Dict[str, Any]:
        """Scans the user query for medical emergencies, prescription requests, or out-of-scope topics.
        
        Args:
            query (str): The raw query input text from the user.
            
        Returns:
            Dict[str, Any]: Validation status indicating if query is allowed, is an emergency, or has errors.
        """
        cleaned_query = query.strip().lower()
        
        # 1. Check for severe emergency keywords
        for pattern in EMERGENCY_KEYWORDS:
            if re.search(pattern, cleaned_query):
                return {
                    "is_allowed": False,
                    "is_emergency": True,
                    "reason": "emergency_redirection",
                    "message": (
                        "🚨 **CRITICAL NOTICE: POSSIBLE MEDICAL EMERGENCY DETECTED** 🚨\n\n"
                        "Your query indicates symptoms that may require urgent medical attention. "
                        "Do not rely on this chatbot. Please call emergency services (e.g., 911 or 112) "
                        "or proceed immediately to the nearest hospital emergency department."
                    )
                }

        # 2. Check for prescription or direct diagnosis attempts
        for pattern in PRESCRIPTION_DIAGNOSIS_KEYWORDS:
            if re.search(pattern, cleaned_query):
                return {
                    "is_allowed": False,
                    "is_emergency": False,
                    "reason": "prescription_or_diagnosis_denied",
                    "message": (
                        "⚠️ **CLINICAL BOUNDARY VIOLATION** ⚠️\n\n"
                        "I am an AI assistant and cannot diagnose diseases, prescribe medication, "
                        "or recommend specific drug dosages. Please consult a licensed medical practitioner "
                        "or doctor for diagnostic assessments and prescription instructions."
                    )
                }

        # Query is cleared for processing
        return {
            "is_allowed": True,
            "is_emergency": False,
            "reason": "cleared"
        }

    @staticmethod
    def apply_prompt_safety() -> str:
        """Returns prompt engineering guidelines to inject into LangChain LLM prompts."""
        return (
            "You are a helpful Healthcare AI Assistant. You must follow these clinical safety boundaries:\n"
            "1. You are NOT a doctor. Never diagnose the user or tell them they have a specific condition.\n"
            "2. Never recommend specific prescription medication dosages or write mock prescriptions.\n"
            "3. Answer the user's question objectively using ONLY the retrieved context. If the answer is "
            "not found in the retrieved context, state clearly that you cannot find the information in the documents.\n"
            "4. Always advise the user to consult a physician for official medical decisions.\n"
        )

    @staticmethod
    def enforce_output_safety(answer: str) -> str:
        """Formats the final text output and appends mandatory medical disclaimers."""
        # Ensure the disclaimer isn't double-appended
        if "***Disclaimer:" not in answer:
            return f"{answer}{MEDICAL_DISCLAIMER}"
        return answer

guardrail = HealthcareGuardrail()
