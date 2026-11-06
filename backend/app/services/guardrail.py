import re
from typing import Dict, Any

EMERGENCY_KEYWORDS = [
    r"chest\s*pain", r"difficulty\s*breathing", r"shortness\s*of\s*breath",
    r"heart\s*attack", r"heavy\s*bleeding", r"unconscious",
    r"poison(ed|ing)?", r"suicid", r"kill\s*myself", r"choking",
    r"severe\s*allergic\s*reaction", r"anaphylaxis", r"seizure",
]

# Only block queries explicitly requesting a personal prescription/diagnosis
PRESCRIPTION_DIAGNOSIS_KEYWORDS = [
    r"\bprescribe\s+me\b", r"\bwrite\s*a?\s*rx\b",
    r"\bdiagnose\s+me\b",
    r"\bwhat\s*(disease|illness|condition)\s*do\s*i\s*have\b",
    r"\bwhat\s*is\s*my\s*(diagnosis|condition)\b",
    r"\bgive\s+me\s+(medication|medicine|a\s*prescription|a\s*drug)\b",
]

DOCUMENT_DISCLAIMER = (
    "\n\n---\n*This information is provided for educational reference based on "
    "your uploaded medical documents. It is not a clinical diagnosis or prescription. "
    "Please consult a licensed healthcare provider for medical decisions.*"
)

GENERAL_DISCLAIMER = (
    "\n\n---\n*This is general educational health information and is not a substitute "
    "for professional medical advice, diagnosis, or treatment. Always consult a qualified "
    "healthcare provider for personal health concerns.*"
)


class HealthcareGuardrail:
    @staticmethod
    def inspect_input(query: str) -> Dict[str, Any]:
        """Scan user query for medical emergencies or personal prescription requests."""
        cleaned = query.strip().lower()

        # 1. Emergency check
        for pattern in EMERGENCY_KEYWORDS:
            if re.search(pattern, cleaned):
                return {
                    "is_allowed": False,
                    "is_emergency": True,
                    "reason": "emergency_redirection",
                    "message": (
                        "🚨 **CRITICAL: Possible Medical Emergency Detected** 🚨\n\n"
                        "Your message describes symptoms that may need urgent attention. "
                        "Please **call emergency services (911 / 112)** immediately or go to the nearest hospital emergency department.\n\n"
                        "Do not rely on this chatbot in an emergency situation."
                    ),
                }

        # 2. Personal prescription / diagnosis request
        for pattern in PRESCRIPTION_DIAGNOSIS_KEYWORDS:
            if re.search(pattern, cleaned):
                return {
                    "is_allowed": False,
                    "is_emergency": False,
                    "reason": "prescription_or_diagnosis_denied",
                    "message": (
                        "⚠️ **I cannot issue personal prescriptions or diagnoses.**\n\n"
                        "As an AI, I'm not able to diagnose your condition or prescribe specific "
                        "medications for you. However, I can explain how medications, conditions, "
                        "or treatments work in general terms.\n\n"
                        "Please consult a licensed doctor or pharmacist for personal medical advice. "
                        "Is there a general question about this medication or condition I can help with?"
                    ),
                }

        return {"is_allowed": True, "is_emergency": False, "reason": "cleared"}

    @staticmethod
    def apply_prompt_safety() -> str:
        return (
            "You are a Healthcare AI Assistant. Follow these safety rules:\n"
            "1. Never diagnose the user or prescribe specific medication for them.\n"
            "2. Answer educational questions naturally and objectively.\n"
            "3. Never start your response with a disclaimer or warning.\n"
            "4. If clinically appropriate, suggest consulting a physician at the end.\n"
        )

    @staticmethod
    def enforce_output_safety(answer: str, intent: str = "GENERAL_MEDICAL") -> str:
        """Append a brief educational disclaimer to medical answers (not casual chat)."""
        if intent == "CASUAL_CHAT":
            return answer

        marker = "---\n*This"
        if marker in answer:
            return answer  # Already has disclaimer

        if intent == "DOCUMENT_QUERY":
            return f"{answer}{DOCUMENT_DISCLAIMER}"

        if intent == "GENERAL_MEDICAL":
            return f"{answer}{GENERAL_DISCLAIMER}"

        return answer


guardrail = HealthcareGuardrail()
