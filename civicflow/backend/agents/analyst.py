import os
import json
import asyncio
from typing import Optional
from google import genai
import sys

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from models.form_models import ScrapedForm, UserDataItem


async def analyst(scraped_form: ScrapedForm, user_documents_text: dict[str, str]) -> list[UserDataItem]:
    """
    Analyze form fields and determine what user information is needed.
    Auto-extract values from provided user documents if available.
    
    Args:
        scraped_form: The scraped form structure
        user_documents_text: Dict mapping filename -> extracted text from OCR
        
    Returns:
        List of UserDataItem with values pre-filled where found in documents
    """
    fields = scraped_form.fields if hasattr(scraped_form, 'fields') else scraped_form.get('fields', [])
    
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY not found in environment")
        
        client = genai.Client(api_key=api_key)
        
        # Step 1: Ask Gemini to analyze the form fields
        system_prompt = """You are a form analysis expert. Given a list of form fields, 
determine what real-world information from the user is needed to fill each field.
For each field, determine:
- A plain English question to ask the user (description)
- The input_type: 'text' for names/addresses/IDs, 'document' for file uploads, 
  'date' for dates, 'selection' for dropdowns/radio, 'boolean' for checkboxes
- An example value that helps the user understand what to enter

Merge similar fields (e.g. if there are 10 fields all from 'personal info', 
group them so you ask the user ONCE for their full name, not 10 separate asks).

Return ONLY valid JSON array matching this schema:
[{
  "field_id": "<original field_id>",
  "label": "<field label>",
  "input_type": "<type>",
  "description": "<plain english question>",
  "example": "<example value>"
}]"""
        
        # Prepare fields data
        fields_data = [f.model_dump() for f in scraped_form.fields]
        user_message = f"{system_prompt}\n\nForm fields: {json.dumps(fields_data, indent=2)}"
        
        response = client.models.generate_content(
            model='gemini-2.0-flash-lite',
            contents=user_message
        )
        response_text = response.text.strip()
        
        # Try to find JSON in response (handle markdown code blocks)
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0].strip()
        
        try:
            analyzed_fields = json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"Failed to parse Gemini response: {response_text}")
            raise ValueError(f"Gemini returned invalid JSON: {e}")
        
        # Step 2: Convert to UserDataItem objects
        data_items = []
        for field_data in analyzed_fields:
            item = UserDataItem(
                field_id=field_data["field_id"],
                label=field_data["label"],
                input_type=field_data["input_type"],
                description=field_data["description"],
                example=field_data["example"],
                value=None,
                document_path=None,
                extracted_from_doc=False
            )
            data_items.append(item)
        
        # Step 3: Auto-extract values from user documents
        if user_documents_text:
            # Combine all document text
            combined_text = "\n\n".join([
                f"=== {filename} ===\n{text}" 
                for filename, text in user_documents_text.items()
            ])
            
            # For each non-document field, try to extract from docs
            for item in data_items:
                if item.input_type == "document":
                    continue
                
                # Ask Gemini to extract the value
                extraction_prompt = f"""Given the following text extracted from user documents, 
determine if it contains information that answers this question: "{item.description}"

Label: {item.label}
Example of expected value: {item.example}

Document text:
{combined_text[:3000]}

If you find a matching value, extract it exactly as it appears.
Return ONLY valid JSON: {{"found": true/false, "value": "extracted value or empty string"}}"""
                
                try:
                    extract_response = client.models.generate_content(
                        model='gemini-2.0-flash-lite',
                        contents=extraction_prompt
                    )
                    extract_text = extract_response.text.strip()
                    
                    # Parse JSON response
                    if "```json" in extract_text:
                        extract_text = extract_text.split("```json")[1].split("```")[0].strip()
                    elif "```" in extract_text:
                        extract_text = extract_text.split("```")[1].split("```")[0].strip()
                    
                    result = json.loads(extract_text)
                    
                    if result.get("found") and result.get("value"):
                        item.value = result["value"]
                        item.extracted_from_doc = True
                        
                except Exception as e:
                    # If extraction fails for this field, just continue
                    print(f"Failed to extract value for {item.label}: {e}")
                    continue
        
        # Step 4: Post-process file upload fields with intelligent document detection
        for item in data_items:
            # Find the original FormField for this item
            original_field = next(
                (f for f in scraped_form.fields if f.field_id == item.field_id), None
            )
            
            if original_field and original_field.field_type == "file":
                # Override input_type to always be "document" for file fields
                item.input_type = "document"
                
                # Use Gemini to determine WHAT document is needed based on context
                context_prompt = f"""A form has a file upload field with this label: "{original_field.label}"
The form is at URL: {scraped_form.url}
The form title is: {scraped_form.page_title}

What specific document is this field asking for? 
Respond with a JSON object:
{{
  "document_name": "e.g. Passport, Aadhaar Card, Marksheet, Photo",
  "description": "Plain English: what to upload and why",
  "accepted_formats": ["PDF", "JPG", "PNG"],
  "max_size_hint": "e.g. under 500KB, under 2MB",
  "is_mandatory": true/false
}}
Only respond with the JSON. No explanation."""
                
                try:
                    doc_response = client.models.generate_content(
                        model='gemini-2.0-flash-lite',
                        contents=context_prompt
                    )
                    doc_text = doc_response.text.strip()
                    
                    # Parse JSON response
                    if "```json" in doc_text:
                        doc_text = doc_text.split("```json")[1].split("```")[0].strip()
                    elif "```" in doc_text:
                        doc_text = doc_text.split("```")[1].split("```")[0].strip()
                    
                    doc_info = json.loads(doc_text)
                    item.description = f"Upload your {doc_info['document_name']} — {doc_info['description']}"
                    item.example = f"Accepted: {', '.join(doc_info['accepted_formats'])} | {doc_info['max_size_hint']}"
                    
                except Exception as e:
                    # Fallback if Gemini fails
                    print(f"Failed to analyze document requirement for {original_field.label}: {e}")
                    item.description = f"Upload required document for: {original_field.label}"
                    item.example = "Accepted: PDF, JPG, PNG"
        
        return data_items
        
    except Exception as e:
        print(f"[Analyst] ⚠ AI call failed: {e}")
        print("[Analyst] Using rule-based fallback — generating questions from field labels")
        
        # FALLBACK: Generate UserDataItem for each field without AI
        fallback_items = []
        for field in fields:
            field_id = field.get("field_id") if isinstance(field, dict) else field.field_id
            label = field.get("label") if isinstance(field, dict) else field.label
            field_type = field.get("field_type") if isinstance(field, dict) else field.field_type
            options = field.get("options", []) if isinstance(field, dict) else getattr(field, 'options', [])
            
            # Skip hidden fields
            if field_type == "hidden":
                continue
            
            # Map field_type to input_type
            if field_type == "file":
                input_type = "document"
                description = f"Upload document for: {label}"
                example = "PDF, JPG, or PNG file"
            elif field_type in ("select", "radio"):
                input_type = "selection"
                description = f"Choose option for: {label}"
                example = options[0] if options else "Select an option"
            elif field_type == "checkbox":
                input_type = "boolean"
                description = f"Check if applicable: {label}"
                example = "yes or no"
            elif field_type == "date":
                input_type = "date"
                description = f"Enter date for: {label}"
                example = "DD/MM/YYYY"
            elif field_type == "email":
                input_type = "text"
                description = f"Enter your email address"
                example = "example@email.com"
            elif field_type == "tel":
                input_type = "text"
                description = f"Enter phone number for: {label}"
                example = "9876543210"
            elif field_type == "number":
                input_type = "text"
                description = f"Enter number for: {label}"
                example = "0"
            else:
                input_type = "text"
                description = f"Enter your {label}"
                example = f"Your {label.lower()}"
            
            fallback_items.append(UserDataItem(
                field_id=field_id,
                label=label,
                input_type=input_type,
                description=description,
                example=example,
                value=None,
                document_path=None,
                extracted_from_doc=False
            ))
        
        print(f"[Analyst] ✓ Fallback generated {len(fallback_items)} data requirements")
        return fallback_items


if __name__ == "__main__":
    async def test_analyst():
        from scraper import scraper
        from scout import scout
        
        print("=" * 80)
        print("Testing Analyst Agent")
        print("=" * 80)
        
        # First, scout and scrape a test form
        test_url = "https://httpbin.org/forms/post"
        
        print(f"\n[1] Scouting URL: {test_url}")
        scout_result = await scout(test_url)
        
        if "error" in scout_result:
            print(f"Scout Error: {scout_result['error']}")
            return
        
        print(f"✓ Page scouted successfully")
        
        print(f"\n[2] Scraping form fields...")
        scraped_form = await scraper(scout_result['html'], scout_result['url'])
        print(f"✓ Found {len(scraped_form.fields)} fields")
        
        print(f"\n[3] Analyzing form with Analyst...")
        
        # Test with no documents
        user_docs = {}
        
        data_requirements = await analyst(scraped_form, user_docs)
        
        print(f"\n✓ Analyst generated {len(data_requirements)} data requirements")
        
        print("\n" + "=" * 80)
        print("Data Requirements:")
        print("=" * 80)
        
        for i, item in enumerate(data_requirements, 1):
            print(f"\n[Requirement {i}]")
            print(f"  Field ID: {item.field_id}")
            print(f"  Label: {item.label}")
            print(f"  Input Type: {item.input_type}")
            print(f"  Description: {item.description}")
            print(f"  Example: {item.example}")
            print(f"  Value: {item.value}")
            print(f"  Extracted from doc: {item.extracted_from_doc}")
    
    asyncio.run(test_analyst())
