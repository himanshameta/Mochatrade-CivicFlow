import os
import asyncio
import json
from pathlib import Path
from typing import TypedDict, Optional, Literal, Annotated
from datetime import datetime

from langgraph.graph import StateGraph, END

import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from models.form_models import ScrapedForm, UserDataItem, UserSession
from models.session_models import SessionStore
from agents.scout import scout
from agents.scraper import scraper
from agents.analyst import analyst
from agents.collector import is_data_complete
from agents.scriptgen import scriptgen
from agents.executor import executor, resume_after_captcha, resume_after_otp
from agents.notifier import notify


# Define the state structure
class PipelineState(TypedDict):
    session_id: str
    user_id: Optional[str]
    url: str
    html: Optional[str]
    page_title: Optional[str]
    screenshot_path: Optional[str]
    scraped_form: Optional[dict]  # ScrapedForm as dict
    user_documents_text: dict  # filename -> OCR text
    user_profile: dict  # Fetched from MongoDB
    data_requirements: list  # list of UserDataItem dicts
    pre_filled_values: dict  # {field_name: value} from profile mapping
    missing_fields: list  # [field_label] for required fields with no data
    file_requirements: list # requirements for file uploads
    matched_documents: list # physical documents matched
    blockers: list # strings explaining why execution is blocked
    ready_for_execution: bool
    generated_script: Optional[str]
    script_path: Optional[str]
    status: str
    error: Optional[str]
    pause_context: Optional[dict]
    retry_count: int


# Initialize session store
session_store = SessionStore()


# Node 1: Scout Agent
async def node_scout(state: PipelineState) -> PipelineState:
    """Visit the URL and capture page HTML and screenshot"""
    print(f"\n[Pipeline] Node: Scout - Visiting {state['url']}")
    
    result = await scout(state["url"])
    
    if result.get("error"):
        error_msg = result['error']
        print(f"[Pipeline] ✗ Scout failed: {error_msg}")
        
        # Provide more helpful error messages
        if "No form found" in error_msg:
            error_msg = "This page doesn't contain any forms. Please provide a direct link to the form page (not a homepage or information page)."
        elif "timeout" in error_msg.lower():
            error_msg = "The page took too long to load. The server may be slow or unreachable."
        
        return {
            **state,
            "status": "failed",
            "error": error_msg,
            "retry_count": 999
        }
    
    html = result.get("html", "")
    print(f"[Pipeline] ✓ Scout got HTML length: {len(html)}")
    
    return {
        **state,
        "html": html,
        "page_title": result.get("title", ""),
        "screenshot_path": result.get("screenshot_path"),
        "status": "scouted"
    }


# Node 2: Scraper Agent
async def node_scraper(state: PipelineState) -> PipelineState:
    """Extract all form fields from HTML"""
    print(f"\n[Pipeline] Node: Scraper - Extracting form fields")
    
    html = state.get("html", "")
    
    if not html or len(html) < 100:
        print("[Pipeline] ✗ Invalid HTML — stopping pipeline")
        return {
            **state,
            "scraped_form": None,
            "status": "failed",
            "error": "Page loaded but no valid HTML content found. The page may require authentication or JavaScript.",
            "retry_count": 999
        }
    
    result = await scraper(html, state["url"])
    
    if result is None:
        print("[Pipeline] ✗ Scraper returned None — stopping pipeline")
        return {
            **state,
            "scraped_form": None,
            "status": "failed",
            "error": "Could not find any form fields on this page. Make sure the URL points directly to a page with a form.",
            "retry_count": 999
        }
    
    fields_count = len(result.get('fields', []))
    if fields_count == 0:
        print("[Pipeline] ✗ No fields found — stopping pipeline")
        return {
            **state,
            "scraped_form": None,
            "status": "failed",
            "error": "Found form structure but no fillable fields detected.",
            "retry_count": 999
        }
    
    print(f"[Pipeline] ✓ Scraper found {fields_count} fields")
    
    session = await session_store.load(state["session_id"])
    if session:
        if isinstance(result, dict):
            session.scraped_form = ScrapedForm.model_validate(result)
        else:
            session.scraped_form = result
        session.html = state.get("html", "")
        session.page_title = state.get("page_title", "")
        await session_store.save(session)
        print(f"[Scraper] Saved scraped_form to session: {state['session_id']}")
    else:
        print(f"[Scraper] Error: Could not load session {state['session_id']} to save scraped form")
    
    return {
        **state,
        "scraped_form": result,
        "status": "scraped"
    }


# Node 3: Analyst Agent
async def node_analyst(state: PipelineState) -> PipelineState:
    """Analyze form and map user profile to fields"""
    print(f"\n[Pipeline] Node: Analyst - Analyzing form requirements")
    
    try:
        # Reload session fresh from store
        session = await session_store.load(state["session_id"])
        if session and session.scraped_form:
            scraped_form = session.scraped_form
            if isinstance(scraped_form, dict):
                scraped_form = ScrapedForm.model_validate(scraped_form)
        else:
            # Fallback to state if session not found or scraped_form missing
            scraped_form = state["scraped_form"]
            if isinstance(scraped_form, dict):
                scraped_form = ScrapedForm.model_validate(scraped_form)
        
        # Call analyst with new signature
        data_requirements, pre_filled, missing = await analyst(scraped_form, state["user_profile"])
        
        # Convert to dicts for state
        state["data_requirements"] = [item.model_dump() for item in data_requirements]
        state["pre_filled_values"] = pre_filled
        state["missing_fields"] = missing
        
        # Always set to ready to allow pipeline to continue
        # Frontend will show missing fields and user can fill them later
        state["status"] = "ready"
        
        if missing:
            print(f"[Pipeline] ⚠ {len(missing)} fields missing but continuing - user can fill them later")
        else:
            print(f"[Pipeline] ✓ All fields mapped from profile")
        
        # Save to session
        session = await session_store.load(state["session_id"])
        if session:
            session.data_requirements = data_requirements
            session.pre_filled_values = pre_filled
            session.missing_fields = missing
            session.status = state["status"]
            await session_store.save(session)
            print(f"[Analyst] Saved analyst results to session: {state['session_id']}")
        
        filled = len(pre_filled)
        total = len(scraped_form.fields)
        print(f"[Pipeline] ✓ Analyst complete - Mapped {filled}/{total} fields from user profile")
        
    except Exception as e:
        state["error"] = f"Analysis failed: {str(e)}"
        state["status"] = "failed"
        print(f"[Pipeline] ✗ Analyst failed: {e}")
        import traceback
        traceback.print_exc()
    
    return state


# Node 4: Check Data Completeness and Build Review Payload
async def node_check_completeness(state: PipelineState) -> PipelineState:
    """Check if all required data has been collected, match documents, and pause for confirmation."""
    print(f"\n[Pipeline] Node: Check Completeness & Build Review Payload")
    
    # 1. Fetch user's stored vault documents
    user_documents = []
    try:
        from db.vault_db import list_documents
        if state.get("user_id"):
            vault_docs = await list_documents(state["user_id"])
            user_documents = [json.loads(d.model_dump_json()) for d in vault_docs]
    except Exception as e:
        print(f"[Pipeline] Could not fetch vault documents: {e}")

    # Fallback: also try legacy physical_documents
    if not user_documents:
        try:
            from db.mongo import get_db
            db = await get_db()
            if db is not None:
                cursor = db.physical_documents.find({"user_id": state["user_id"], "is_active": True, "is_deleted": {"$ne": True}})
                legacy_docs = await cursor.to_list(length=100)
                for ld in legacy_docs:
                    ld.pop("_id", None)
                    # Normalize legacy fields to vault format
                    ld.setdefault("document_id", ld.get("doc_id", ""))
                    ld.setdefault("display_name", ld.get("doc_label", ld.get("original_filename", "")))
                    ld.setdefault("category", "other")
                    ld.setdefault("extension", "")
                    user_documents.append(ld)
        except Exception as e:
            print(f"[Pipeline] Could not fetch legacy documents: {e}")

    # 2. Extract file fields from scraped form
    scraped_form = state.get("scraped_form")
    fields = []
    if scraped_form:
        if isinstance(scraped_form, dict):
            fields = scraped_form.get("fields", [])
        else:
            fields = getattr(scraped_form, "fields", [])

    file_fields = [f for f in fields if (f.get("field_type") if isinstance(f, dict) else getattr(f, "field_type", "")) == "file"]
    
    # 3. Match documents using ranked matcher
    from utils.document_matcher import match_documents_for_file_field
    
    file_requirements = []
    blockers = []
    
    for f in file_fields:
        f_dict = f if isinstance(f, dict) else f.model_dump()
        key = f_dict.get("name") or f_dict.get("id_attr") or f_dict.get("label", "file_upload")
        label = f_dict.get("label", "Unnamed File Field")
        required = f_dict.get("required", False)
        accept = f_dict.get("accept", "")
        multiple = f_dict.get("multiple", False)
        selector = f_dict.get("selector", "")
        
        ranked_matches = match_documents_for_file_field(f_dict, user_documents)
        
        matched_saved = []
        for m in ranked_matches:
            matched_saved.append({
                "document_id": m.document_id,
                "display_name": m.display_name,
                "category": m.category,
                "mime_type": m.mime_type,
                "score": m.score,
            })
        
        # Determine status
        status = "optional_unset"
        if required and not matched_saved:
            status = "missing"
            accept_msg = f" ({accept})" if accept else ""
            blockers.append(f"Required document '{label}'{accept_msg} is missing. Please upload it.")
        elif required:
            status = "missing"  # Still missing until user explicitly selects
        
        file_requirements.append({
            "key": key,
            "label": label,
            "selector": selector,
            "required": required,
            "accept": accept,
            "multiple": multiple,
            "matched_saved_documents": matched_saved,
            "selected_document_id": None,
            "status": status,
        })

    # Add text field blockers
    for mf in state.get("missing_fields", []):
        blockers.append(f"Required text field '{mf}' is missing.")
        
    state["file_requirements"] = file_requirements
    state["matched_documents"] = []  # Deprecated, kept for compat
    state["blockers"] = blockers
    state["ready_for_execution"] = len(blockers) == 0

    # Pause for user confirmation
    state["status"] = "awaiting_confirmation"
    
    if blockers:
        print(f"[Pipeline] ⚠ {len(blockers)} blockers found")
    else:
        print(f"[Pipeline] ✓ All required data available, awaiting user confirmation")
    
    # Update session
    session = await session_store.load(state["session_id"])
    if session:
        session.file_requirements = file_requirements
        session.blockers = blockers
        session.ready_for_execution = state["ready_for_execution"]
        session.status = state["status"]
        await session_store.save(session)
    
    return state


# Conditional routing after completeness check
def route_after_completeness(state: PipelineState) -> str:
    """Pause pipeline at check_completeness. User must trigger resume."""
    return END


# Node 5: ScriptGen Agent
async def node_scriptgen(state: PipelineState) -> PipelineState:
    """Generate custom Playwright automation script"""
    print(f"\n[Pipeline] Node: ScriptGen - Generating automation script")
    
    # GUARD: If analyst failed (status is failed), stop immediately
    if state.get("status") == "failed":
        print("[Pipeline] ✗ ScriptGen skipped — pipeline already failed")
        return {**state, "retry_count": 999}  # Prevent retry loop
    
    # HARD GUARD: stop immediately if scraped_form is None
    raw = state.get("scraped_form")
    if raw is None:
        print("[Pipeline] ✗ ScriptGen ABORTED: scraped_form is None — scraping failed earlier")
        return {
            **state,
            "status": "failed",
            "error": "Form scraping returned no data. Cannot generate script.",
            "retry_count": 999  # Set high so retry edge goes to END
        }
    
    # Deserialize dict → ScrapedForm safely
    try:
        if isinstance(raw, dict):
            scraped_form = ScrapedForm(**raw)
        elif isinstance(raw, ScrapedForm):
            scraped_form = raw
        else:
            raise ValueError(f"Unexpected type for scraped_form: {type(raw)}")
    except Exception as e:
        print(f"[Pipeline] ✗ ScriptGen ABORTED: cannot parse scraped_form: {e}")
        return {
            **state,
            "status": "failed",
            "error": f"Cannot parse scraped form: {str(e)}",
            "retry_count": 999
        }
    
    # Deserialize data_requirements safely (kept for backward compatibility)
    raw_reqs = state.get("data_requirements", [])
    data_requirements = []
    for item in raw_reqs:
        try:
            if isinstance(item, dict):
                data_requirements.append(UserDataItem(**item))
            elif isinstance(item, UserDataItem):
                data_requirements.append(item)
        except Exception:
            pass
    
    # Get pre_filled_values from state (this is what executor will use)
    pre_filled_values = state.get("pre_filled_values", {})
    
    # Now run actual scriptgen with pre_filled_values
    try:
        script = await scriptgen(scraped_form, state["session_id"], pre_filled_values)
        
        # Determine script path
        upload_dir = os.getenv("UPLOAD_DIR", "./uploads")
        script_path = Path(upload_dir) / "scripts" / f"{state['session_id']}.py"
        
        print(f"[Pipeline] ✓ ScriptGen succeeded: {script_path}")
        return {
            **state,
            "generated_script": script,
            "script_path": str(script_path),
            "status": "script_ready",
            "retry_count": state.get("retry_count", 0)
        }
    except Exception as e:
        print(f"[Pipeline] ✗ ScriptGen failed with exception: {e}")
        return {
            **state,
            "status": "failed",
            "error": f"ScriptGen exception: {str(e)}",
            "retry_count": state.get("retry_count", 0) + 1
        }


# Node 6: Executor Agent
async def node_executor(state: PipelineState) -> PipelineState:
    """Execute the generated Playwright script"""
    print(f"\n[Pipeline] Node: Executor - Running automation script")
    
    script_path = state.get("script_path")
    if not script_path:
        print("[Pipeline] ✗ Executor skipped — no script_path in state")
        return {
            **state,
            "status": "failed",
            "error": "No script was generated — check ScriptGen logs above",
            "retry_count": state.get("retry_count", 0) + 1
        }
    
    try:
        result = await executor(
            state["script_path"],
            state["session_id"],
            session_store,
            max_retries=2
        )
        
        state["status"] = result["status"]
        
        if result["status"] == "paused_captcha":
            state["pause_context"] = {
                "type": "captcha",
                "message": result["message"],
                "screenshot_path": result.get("screenshot_path")
            }
            print(f"[Pipeline] ⏸ Execution paused - CAPTCHA detected")
            
        elif result["status"] == "paused_otp":
            state["pause_context"] = {
                "type": "otp",
                "message": result["message"]
            }
            print(f"[Pipeline] ⏸ Execution paused - OTP required")
            
        elif result["status"] == "completed":
            state["pause_context"] = None
            print(f"[Pipeline] ✓ Execution complete - form submitted!")
            
        elif result["status"] == "failed":
            state["error"] = result["message"]
            print(f"[Pipeline] ✗ Execution failed: {result['message']}")
            
            # PART 8: Retry logic fix
            if "Script error" in result["message"] or "SyntaxError" in result["message"]:
                if state.get("retry_count", 0) < 2:
                    print("[Pipeline] ↻ Executor failure was due to generated script, preparing for ScriptGen retry")
                    state["status"] = "retrying"
        
    except Exception as e:
        state["error"] = f"Execution exception: {str(e)}"
        state["status"] = "failed"
        print(f"[Pipeline] ✗ Executor exception: {e}")
    
    return state


# Conditional routing after executor
def route_after_executor(state: PipelineState) -> str:
    """Route based on execution result"""
    status = state.get("status", "failed")
    retry_count = state.get("retry_count", 0)
    
    if status == "completed":
        return "notifier"
    
    if status in ("paused_captcha", "paused_otp", "paused_payment"):
        return END   # Human action needed — stop graph, wait for API resume
    
    if status in ("failed", "retrying"):
        if retry_count < 2:
            print(f"[Pipeline] Retrying script generation (attempt {retry_count + 1}/2)")
            return "scriptgen"
        else:
            print("[Pipeline] ✗ Max retries reached. Stopping.")
            return END  # CRITICAL: must return END not loop again
    
    return END  # Default: always END if unknown status


# Node 7: Notifier Agent
async def node_notifier(state: PipelineState) -> PipelineState:
    """Send completion notifications"""
    print(f"\n[Pipeline] Node: Notifier - Sending completion notification")
    
    try:
        await notify(
            session_id=state["session_id"],
            status=state["status"],
            message="Form automation completed successfully!",
            url=state["url"]
        )
        
        print(f"[Pipeline] ✓ Notification sent")
        
    except Exception as e:
        print(f"[Pipeline] ⚠ Notification failed: {e}")
        # Don't fail the pipeline for notification errors
    
    return state


# Build the StateGraph
def build_graph():
    """Build and compile the LangGraph pipeline"""
    
    workflow = StateGraph(PipelineState)
    
    # Add nodes
    workflow.add_node("scout", node_scout)
    workflow.add_node("scraper", node_scraper)
    workflow.add_node("analyst", node_analyst)
    workflow.add_node("check_completeness", node_check_completeness)
    workflow.add_node("scriptgen", node_scriptgen)
    workflow.add_node("executor", node_executor)
    workflow.add_node("notifier", node_notifier)
    
    # Add edges
    workflow.set_entry_point("scout")
    workflow.add_edge("scout", "scraper")
    
    # Conditional edge after scraper
    def route_after_scraper(state: PipelineState) -> str:
        if state.get("status") == "failed" or state.get("scraped_form") is None:
            return END   # Stop immediately, tell user scraping failed
        return "analyst"
    
    workflow.add_conditional_edges(
        "scraper",
        route_after_scraper,
        {
            "analyst": "analyst",
            END: END
        }
    )
    
    workflow.add_edge("analyst", "check_completeness")
    
    # Conditional edge after check_completeness
    workflow.add_conditional_edges(
        "check_completeness",
        route_after_completeness,
        {
            END: END,
            "scriptgen": "scriptgen"
        }
    )
    
    workflow.add_edge("scriptgen", "executor")
    
    # Conditional edge after executor
    workflow.add_conditional_edges(
        "executor",
        route_after_executor,
        {
            "notifier": "notifier",
            "scriptgen": "scriptgen",  # Retry
            END: END  # All other cases go to END
        }
    )
    
    workflow.add_edge("notifier", END)
    
    return workflow.compile()


# Compile the graph once
compiled_graph = build_graph()


async def run_pipeline(session_id: str, url: str, user_id: Optional[str] = None, user_documents_text: dict = None) -> UserSession:
    """
    Run the complete pipeline from URL to automation.
    
    Args:
        session_id: Unique session identifier
        url: Target form URL
        user_id: User ID to fetch profile for
        user_documents_text: Dict of filename -> OCR extracted text (optional)
        
    Returns:
        Updated UserSession
    """
    print(f"\n{'=' * 80}")
    print(f"Starting CivicFlow Pipeline")
    print(f"Session ID: {session_id}")
    print(f"User ID: {user_id}")
    print(f"URL: {url}")
    print(f"{'=' * 80}")
    
    # STEP 1: Fetch user profile FIRST from DB (before analyzing form)
    user_profile = {}
    if user_id:
        from utils.generic_mapper import get_flat_user_profile
        try:
            user_profile = await get_flat_user_profile(user_id)
            print(f"[Pipeline] Loaded user profile from DB: {len(user_profile)} fields")
            for key, val in list(user_profile.items())[:5]:  # Show first 5
                print(f"  - {key}: {val}")
        except Exception as e:
            print(f"[Pipeline] Could not load user profile: {e}")
    else:
        print(f"[Pipeline] No user_id provided, skipping profile fetch")
    
    # Create initial session with user profile
    session = await session_store.load(session_id)
    if not session:
        session = UserSession(
            session_id=session_id,
            user_id=user_id,
            url=url,
            status="created",
            user_profile=user_profile
        )
        await session_store.save(session)
    
    # Initialize state
    initial_state: PipelineState = {
        "session_id": session_id,
        "user_id": user_id,
        "url": url,
        "html": None,
        "page_title": None,
        "screenshot_path": None,
        "scraped_form": None,
        "user_documents_text": user_documents_text or {},
        "user_profile": user_profile,  # Pass stored profile to pipeline
        "data_requirements": [],
        "pre_filled_values": {},
        "missing_fields": [],
        "file_requirements": [],
        "matched_documents": [],
        "blockers": [],
        "ready_for_execution": False,
        "generated_script": None,
        "script_path": None,
        "status": "created",
        "error": None,
        "pause_context": None,
        "retry_count": 0
    }
    
    # Run the graph
    try:
        final_state = await compiled_graph.ainvoke(
            initial_state,
            config={"recursion_limit": 20}
        )
        
        print(f"\n{'=' * 80}")
        print(f"Pipeline Execution Complete")
        print(f"Final Status: {final_state['status']}")
        if final_state.get('error'):
            print(f"Error: {final_state['error']}")
        if final_state.get('pause_context'):
            print(f"Paused: {final_state['pause_context']}")
        print(f"{'=' * 80}\n")
        
    except Exception as e:
        print(f"\n[Pipeline] Fatal error: {e}")
        await session_store.update_status(session_id, "failed")
        await session_store.update_field(session_id, "error", str(e))
    
    # Return final session
    return await session_store.load(session_id)


async def resume_pipeline(
    session_id: str, 
    resume_type: Literal["captcha", "otp", "user_data"], 
    resume_value: Optional[str] = None
) -> UserSession:
    """
    Resume a paused pipeline.
    
    Args:
        session_id: Session identifier
        resume_type: Type of resume ("captcha", "otp", "user_data")
        resume_value: Value for resume (e.g., OTP code, or None for CAPTCHA)
        
    Returns:
        Updated UserSession
    """
    print(f"\n{'=' * 80}")
    print(f"Resuming CivicFlow Pipeline")
    print(f"Session ID: {session_id}")
    print(f"Resume Type: {resume_type}")
    print(f"{'=' * 80}")
    
    # Load session
    session = await session_store.load(session_id)
    if not session:
        raise ValueError(f"Session {session_id} not found")
    
    if resume_type == "captcha":
        # Signal captcha solved
        result = await resume_after_captcha(session_id, session_store)
        print(f"[Pipeline] CAPTCHA resume signal sent: {result['message']}")
        
        # The executor is already running and polling Redis
        # Just return the session - the executor will continue
        return await session_store.load(session_id)
        
    elif resume_type == "otp":
        # Provide OTP value
        if not resume_value:
            raise ValueError("OTP value required for OTP resume")
        
        result = await resume_after_otp(session_id, resume_value, session_store)
        print(f"[Pipeline] OTP resume signal sent: {result['message']}")
        
        # The executor is already running and polling Redis
        return await session_store.load(session_id)
        
    elif resume_type == "user_data":
        # User provided missing data - re-enter at check_completeness
        print(f"[Pipeline] User data updated - resuming from completeness check")
        
        # Convert session to dict for safe access
        if hasattr(session, 'model_dump'):
            session_dict = session.model_dump()
        else:
            session_dict = dict(session)
        
        # Debug: confirm scraped_form is in the saved session
        scraped_form_data = session_dict.get("scraped_form")
        print(f"[Resume] scraped_form in saved session: {scraped_form_data is not None}")
        if scraped_form_data:
            if isinstance(scraped_form_data, dict):
                fields = scraped_form_data.get("fields", [])
            else:
                fields = getattr(scraped_form_data, 'fields', [])
            print(f"[Resume] scraped_form has {len(fields)} fields")
        
        # Reconstruct state from session with ALL required data
        state: PipelineState = {
            "session_id": session.session_id,
            "user_id": session_dict.get("user_id"),
            "url": session.url,
            "html": session_dict.get("html", ""),
            "page_title": session_dict.get("page_title", ""),
            "screenshot_path": None,
            "scraped_form": scraped_form_data,
            "user_documents_text": session_dict.get("user_documents_text", {}),
            "user_profile": session_dict.get("user_profile", {}),
            "data_requirements": [item.model_dump() if hasattr(item, 'model_dump') else item for item in session.data_requirements],
            "pre_filled_values": session_dict.get("pre_filled_values", {}),
            "missing_fields": session_dict.get("missing_fields", []),
            "file_requirements": session_dict.get("file_requirements", []),
            "matched_documents": session_dict.get("matched_documents", []),
            "blockers": session_dict.get("blockers", []),
            "ready_for_execution": session_dict.get("ready_for_execution", False),
            "generated_script": session.generated_script,
            "script_path": session_dict.get("script_path"),
            "status": "ready",
            "error": None,
            "pause_context": None,
            "retry_count": 0
        }
        
        # Re-enter graph at scriptgen since data is confirmed
        try:
            state = await node_scriptgen(state)
            state = await node_executor(state)
            
            if state["status"] == "completed":
                state = await node_notifier(state)
            
            print(f"\n{'=' * 80}")
            print(f"Pipeline Resume Complete")
            print(f"Final Status: {state['status']}")
            print(f"{'=' * 80}\n")
            
        except Exception as e:
            print(f"\n[Pipeline] Resume error: {e}")
            await session_store.update_status(session_id, "failed")
            await session_store.update_field(session_id, "error", str(e))
        
        return await session_store.load(session_id)
    
    else:
        raise ValueError(f"Unknown resume type: {resume_type}")


if __name__ == "__main__":
    async def test_pipeline():
        import uuid
        
        print("=" * 80)
        print("Testing CivicFlow Pipeline Orchestrator")
        print("=" * 80)
        
        # Test with httpbin form
        test_session_id = str(uuid.uuid4())
        test_url = "https://httpbin.org/forms/post"
        
        # Sample OCR text from user documents
        user_docs = {
            "id_card.txt": """
            John Smith
            Date of Birth: 01/15/1990
            Address: 123 Main St, Springfield, IL 62701
            Phone: 555-1234
            Email: john.smith@example.com
            """
        }
        
        print(f"\n[Test] Running full pipeline for session: {test_session_id}")
        
        # Run pipeline
        final_session = await run_pipeline(test_session_id, test_url, user_docs)
        
        print(f"\n[Test] Pipeline Result:")
        print(f"  Status: {final_session.status}")
        print(f"  URL: {final_session.url}")
        
        if final_session.scraped_form:
            print(f"  Fields found: {len(final_session.scraped_form.fields)}")
        
        if final_session.data_requirements:
            print(f"  Data requirements: {len(final_session.data_requirements)}")
            filled = sum(1 for item in final_session.data_requirements if item.value)
            print(f"  Pre-filled: {filled}/{len(final_session.data_requirements)}")
        
        if final_session.generated_script:
            print(f"  Script generated: {len(final_session.generated_script)} chars")
        
        if final_session.error:
            print(f"  Error: {final_session.error}")
        
        # Test resume if paused
        if final_session.status == "collecting":
            print(f"\n[Test] Pipeline paused - would need user input to resume")
            print(f"  Missing fields:")
            for item in final_session.data_requirements:
                if not item.value:
                    print(f"    - {item.label}: {item.description}")
        
        # Cleanup
        await session_store.delete(test_session_id)
        await session_store.close()
        
        print("\n" + "=" * 80)
        print("Pipeline test complete!")
        print("=" * 80)
    
    asyncio.run(test_pipeline())
