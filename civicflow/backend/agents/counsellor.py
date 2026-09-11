"""
CivicFlow — Counsellor Agent (Sahayak)
======================================
LLM-powered conversational agent guiding users through CivicFlow.
"""
import os
import sys
import json
from datetime import datetime
from typing import Optional, List, Dict

from google import genai

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
        Process user message and return counsellor response.
        Loads history from DB, calls Gemini, saves history.
        """
        db = await get_db()
        
        # 1. Load history
        history = []
        if db is not None:
            session = await db.form_sessions.find_one({"session_id": session_id})
            if session:
                history = session.get("conversation_history", [])

        # 2. Build context
        completion = await self._calculate_profile_completion(user_id)
        sys_prompt = self._get_system_prompt(stage, completion)
        
        # We declare tools manually to handle async execution cleanly
        def get_profile_completion_status(uid: str) -> str:
            """Gets the percentage of the profile completed."""
            return f"Profile is {completion}% complete."

        def get_missing_form_fields(sid: str) -> str:
            """Gets a list of missing fields required for the current form."""
            return "Missing fields lookup requires data_requirements from session."

        def get_form_status(sid: str) -> str:
            """Gets the current status of the form filling automation."""
            return f"Status for session {sid}."

        tools = [get_profile_completion_status, get_missing_form_fields, get_form_status]

        client = genai.Client()
        
        # 3. Format history for Gemini
        gemini_history = []
        for msg in history:
            role = "model" if msg["role"] == "assistant" else "user"
            gemini_history.append({"role": role, "parts": [{"text": msg["message"]}]})

        chat_session = client.chats.create(
            model="gemini-2.0-flash-lite",
            config=genai.types.GenerateContentConfig(
                system_instruction=sys_prompt,
                tools=tools
            ),
            history=gemini_history
        )

        # 4. Invoke LLM
        response = chat_session.send_message(message)
        
        # Handle potential tool calls
        if response.function_calls:
            for fn in response.function_calls:
                # Execute tool
                if fn.name == "get_profile_completion_status":
                    res = get_profile_completion_status(user_id)
                elif fn.name == "get_missing_form_fields":
                    res = get_missing_form_fields(session_id)
                elif fn.name == "get_form_status":
                    res = get_form_status(session_id)
                else:
                    res = "Unknown tool."
                
                response = chat_session.send_message(
                    [{"function_response": {"name": fn.name, "response": {"result": res}}}]
                )

        final_text = response.text.strip()
        
        # 5. Extract action if any
        triggered_action = None
        import re
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', final_text, re.DOTALL)
        if json_match:
            try:
                action_data = json.loads(json_match.group(1))
                triggered_action = action_data.get("triggered_action")
                # Remove the JSON block from the user-facing response
                final_text = final_text[:json_match.start()].strip()
            except Exception:
                pass

        # 6. Save back to DB
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
        Generate plain language explanation of a field conflict using the LLM.
        """
        prompt = f"""
You are Sahayak. Explain to the user that there is a mismatch in their documents.
Field: {field}
Value 1: {doc1_value}
Value 2: {doc2_value}

Write a short, polite, 1-2 sentence explanation asking them to clarify which one is correct.
        """
        client = genai.Client()
        res = client.models.generate_content(model="gemini-2.0-flash-lite", contents=prompt)
        return res.text.strip()

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
