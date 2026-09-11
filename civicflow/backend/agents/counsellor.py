"""
CivicFlow — Counsellor Agent (Sahayak) - Simplified
====================================================
Rule-based conversational agent guiding users through CivicFlow.
No LLM dependency - uses pattern matching and templates.
"""
import os
import sys
import json
import re
from datetime import datetime
from typing import Optional, List, Dict

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.chat_models import CounsellorResponse
from db.mongo import get_db

class CounsellorAgent:
    CONVERSATION_STAGES = [
        "welcome",
        "profile_creation",
        "document_upload",
        "form_selection",
        "form_review",
        "form_execution",
        "monitoring",
        "completion"
    ]

    def _get_system_prompt(self, stage: str, profile_completion: int) -> str:
        return f"""
You are Sahayak (सहायक), a warm and helpful AI assistant for CivicFlow.
You help Indian citizens navigate government forms and procedures.

Your personality:
- Patient and encouraging
- Speak simply, avoid jargon
- If user writes in Hindi/regional language, respond in that language
- Explain what is happening at each step
- When asking for documents, explain exactly why it's needed
- When conflicts are found, explain in simple terms what the problem is

Current conversation stage: {stage}
User profile completion: {profile_completion}%

You have access to tools to fetch live information. Use them if the user asks about their form status or what is missing.

IMPORTANT: If the user explicitly asks to perform an action (e.g. "fill my passport form", "start automation", "cancel this"), you must include a JSON block at the very end of your response exactly like this:
```json
{{"triggered_action": "start_form_fill"}}
```
Valid actions: start_form_fill, cancel_form, update_profile.
Otherwise, do not include the JSON block.
"""

    async def _calculate_profile_completion(self, user_id: str) -> int:
        db = await get_db()
        if db is None:
            return 0
            
        profile = await db.user_profiles.find_one({"user_id": user_id})
        if not profile:
            return 0
            
        # Basic heuristic: 4 sections + uploaded docs
        score = 0
        if profile.get("basic_info"): score += 20
        if profile.get("contact"): score += 20
        if profile.get("identity"): score += 20
        if profile.get("education"): score += 10
        if profile.get("uploaded_documents"): score += 30
        
        return min(100, score)

    async def chat(
        self,
        user_id: str,
        session_id: str,
        message: str,
        stage: str
    ) -> CounsellorResponse:
        """
        Process user message using rule-based responses.
        """
        db = await get_db()
        
        # 1. Load history
        history = []
        completion = 0
        try:
            if db is not None:
                session = await db.form_sessions.find_one({"session_id": session_id})
                if session:
                    history = session.get("conversation_history", [])
                completion = await self._calculate_profile_completion(user_id)
        except Exception as e:
            print(f"[Counsellor] Database error, using fallback defaults: {e}")
        
        # 3. Pattern matching for responses
        message_lower = message.lower().strip()
        final_text = ""
        triggered_action = None
        
        # Greetings
        if any(word in message_lower for word in ['hi', 'hello', 'hey', 'namaste']):
            final_text = f"Namaste! I'm Sahayak, your CivicFlow assistant. Your profile is {completion}% complete. How can I help you today?"
        
        # Profile queries
        elif any(word in message_lower for word in ['profile', 'complete', 'status', 'progress']):
            if completion < 50:
                final_text = f"Your profile is {completion}% complete. Let me help you finish it. Please share your basic details like name, date of birth, and address."
            else:
                final_text = f"Great! Your profile is {completion}% complete. You're ready to start filling forms."
        
        # Document upload
        elif any(word in message_lower for word in ['document', 'upload', 'aadhaar', 'pan', 'passport']):
            final_text = "Please use the document upload button to share your documents. I'll extract the information automatically and keep it encrypted for your safety."
        
        # Form filling
        elif any(word in message_lower for word in ['fill', 'form', 'start', 'begin', 'apply']):
            if completion < 30:
                final_text = "Before we start filling forms, let's complete your profile first. Please upload your documents or fill in the profile section."
            else:
                final_text = "I can help you fill government forms automatically. Which form do you need? For example: Passport, PAN Card, Driving License, or Aadhaar."
                triggered_action = "start_form_fill"
        
        # Help/guidance
        elif any(word in message_lower for word in ['help', 'how', 'what', 'guide']):
            final_text = """I can help you with:
1. Complete your profile automatically from documents
2. Fill government forms without manual typing
3. Track your application status
4. Answer questions about required documents

What would you like to do?"""
        
        # Thanks/bye
        elif any(word in message_lower for word in ['thanks', 'thank you', 'bye', 'goodbye']):
            final_text = "You're welcome! Feel free to ask if you need any help with your forms. Jai Hind!"
        
        # Default fallback
        else:
            final_text = "I'm here to help you with government forms. You can ask me to:\n- Check your profile status\n- Upload documents\n- Fill a specific form\n- Get help with the process\n\nWhat would you like to do?"
        
        # 4. Save to DB
        if db is not None:
            now = datetime.utcnow()
            new_msgs = [
                {"role": "user", "message": message, "timestamp": now},
                {"role": "assistant", "message": final_text, "timestamp": now}
            ]
            await db.form_sessions.update_one(
                {"session_id": session_id},
                {"$push": {"conversation_history": {"$each": new_msgs}}}
            )

        return CounsellorResponse(
            response=final_text,
            triggered_action=triggered_action,
            stage=stage
        )

    async def guide_profile_creation(self, user_id: str) -> str:
        """
        Check which profile fields are empty and ask for the most important one.
        """
        db = await get_db()
        if db is None:
            return "I'm having trouble accessing your profile right now."
            
        profile = await db.user_profiles.find_one({"user_id": user_id}) or {}
        
        # Extremely basic heuristic
        if not profile.get("basic_info", {}).get("full_name"):
            return "Could you please tell me your full name exactly as it appears on your official documents?"
            
        if not profile.get("identity", {}).get("aadhaar_last4"):
            return "I see we don't have your Aadhaar details yet. Could you please upload your Aadhaar card so I can extract the details safely?"

        return "Your profile looks complete! What form would you like to fill today?"

    async def explain_conflict(self, field: str, doc1_value: str, doc2_value: str) -> str:
        """
        Generate plain language explanation of a field conflict.
        """
        return f"I noticed a mismatch in your {field}. One document shows '{doc1_value}' and another shows '{doc2_value}'. Which one is correct?"

    async def get_stage_greeting(self, stage: str, user_name: str) -> str:
        """Return contextual greeting when entering a new stage."""
        greetings = {
            "welcome": f"Namaste {user_name}! I am Sahayak. I can help you fill out complex government forms automatically. Let's get started!",
            "profile_creation": "Let's set up your profile so you never have to type these details manually again.",
            "document_upload": "Now, let's upload your documents. I will extract the information automatically and encrypt it for your safety.",
            "form_selection": "What form do you need help with today? (e.g. Passport, PAN Card, Driving License)",
            "form_execution": "I'm starting the automation now. Please sit back. I'll let you know if I need an OTP or a Captcha solved.",
            "completion": "Great news! The form has been successfully completed."
        }
        return greetings.get(stage, f"Let's move on to the next step: {stage.replace('_', ' ')}.")

    async def summarize_form_progress(self, completed_fields: list, failed_fields: list, total: int) -> str:
        """Return a progress summary."""
        filled = len(completed_fields)
        if failed_fields:
            return f"I've filled {filled} out of {total} fields, but I'm missing some information for: {', '.join(failed_fields)}."
        return f"Making good progress! {filled}/{total} fields filled."
