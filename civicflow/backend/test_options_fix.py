"""
Test script to verify FormField options handling
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.form_models import FormField, ScrapedForm
from datetime import datetime

def test_formfield_options():
    print("=" * 80)
    print("Testing FormField options handling")
    print("=" * 80)
    
    # Test 1: String options (backward compatibility)
    print("\n[Test 1] String options (backward compatibility)")
    field1 = FormField(
        label="Gender",
        field_type="select",
        name="gender",
        selector="#gender",
        options=["Male", "Female", "Other"]
    )
    print(f"Input: ['Male', 'Female', 'Other']")
    print(f"Output: {field1.options}")
    assert all(isinstance(opt, dict) for opt in field1.options)
    assert field1.options[0]['value'] == 'Male'
    assert field1.options[0]['label'] == 'Male'
    print("✓ String options normalized to dict format")
    
    # Test 2: Dict options (new format)
    print("\n[Test 2] Dict options (new structured format)")
    field2 = FormField(
        label="State",
        field_type="select",
        name="state",
        selector="#state",
        options=[
            {"value": "delhi", "label": "Delhi"},
            {"value": "mumbai", "label": "Mumbai"},
            {"value": "bangalore", "label": "Bangalore"}
        ]
    )
    print(f"Input: [{{'value': 'delhi', 'label': 'Delhi'}}, ...]")
    print(f"Output: {field2.options}")
    assert field2.options[0]['value'] == 'delhi'
    assert field2.options[0]['label'] == 'Delhi'
    print("✓ Dict options preserved correctly")
    
    # Test 3: Mixed format (should handle gracefully)
    print("\n[Test 3] Mixed format")
    field3 = FormField(
        label="Category",
        field_type="radio",
        name="category",
        selector="input[name='category']",
        options=["General", {"value": "obc", "label": "OBC"}, "SC/ST"]
    )
    print(f"Input: ['General', {{'value': 'obc', 'label': 'OBC'}}, 'SC/ST']")
    print(f"Output: {field3.options}")
    assert field3.options[0]['value'] == 'General'
    assert field3.options[1]['value'] == 'obc'
    assert field3.options[2]['value'] == 'SC/ST'
    print("✓ Mixed format normalized correctly")
    
    # Test 4: ScrapedForm with fields containing dict options
    print("\n[Test 4] ScrapedForm with dict options")
    scraped_form = ScrapedForm(
        url="http://example.com/form",
        page_title="Test Form",
        form_html="<form></form>",
        fields=[
            FormField(
                label="Gender",
                field_type="select",
                name="gender",
                selector="#gender",
                options=[
                    {"value": "Male", "label": "Male"},
                    {"value": "Female", "label": "Female"},
                    {"value": "Other", "label": "Other"}
                ]
            ),
            FormField(
                label="Name",
                field_type="text",
                name="name",
                selector="#name"
            )
        ],
        submit_button_selector="#submit",
        has_captcha=False,
        has_file_upload=False,
        scraped_at=datetime.utcnow()
    )
    print(f"ScrapedForm created with {len(scraped_form.fields)} fields")
    print(f"Gender field options: {scraped_form.fields[0].options}")
    assert len(scraped_form.fields[0].options) == 3
    assert all(isinstance(opt, dict) for opt in scraped_form.fields[0].options)
    print("✓ ScrapedForm accepts dict options without validation error")
    
    print("\n" + "=" * 80)
    print("All tests passed! ✓")
    print("=" * 80)

if __name__ == "__main__":
    test_formfield_options()
