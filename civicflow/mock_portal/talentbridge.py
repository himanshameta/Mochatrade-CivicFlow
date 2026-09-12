import os
import uuid
import urllib.request
import urllib.parse
import json
from datetime import datetime
from flask import Blueprint, request, render_template_string, redirect, url_for, flash, jsonify

talentbridge_bp = Blueprint('talentbridge', __name__)

STORAGE_DIR = os.path.join(os.path.dirname(__file__), 'storage', 'resumes')
os.makedirs(STORAGE_DIR, exist_ok=True)

# -----------------------------------------------------------------------------
# HTML Templates
# -----------------------------------------------------------------------------

TALENTBRIDGE_BASE_CSS = """
<style>
    :root {
        --primary: #2563eb;
        --primary-hover: #1d4ed8;
        --bg-main: #f8fafc;
        --card-bg: #ffffff;
        --text-main: #0f172a;
        --text-muted: #64748b;
        --border-color: #cbd5e1;
        --focus-ring: rgba(37, 99, 235, 0.25);
        --error-bg: #fef2f2;
        --error-border: #fca5a5;
        --error-text: #991b1b;
        --success-bg: #ecfdf5;
        --success-border: #6ee7b7;
        --success-text: #065f46;
    }

    * {
        box-sizing: border-box;
        margin: 0;
        padding: 0;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    }

    body {
        background-color: var(--bg-main);
        color: var(--text-main);
        line-height: 1.5;
        padding-bottom: 60px;
    }

    /* Navbar */
    .tb-navbar {
        background: #0f172a;
        color: #ffffff;
        padding: 16px 32px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1);
    }
    .tb-brand {
        display: flex;
        align-items: center;
        gap: 12px;
        font-weight: 700;
        font-size: 1.25rem;
        letter-spacing: -0.025em;
    }
    .tb-brand-icon {
        width: 32px;
        height: 32px;
        background: linear-gradient(135deg, #3b82f6, #1d4ed8);
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: 900;
    }
    .tb-nav-links {
        display: flex;
        gap: 24px;
        font-size: 0.9rem;
        color: #94a3b8;
    }

    /* Container */
    .tb-container {
        max-width: 800px;
        margin: 40px auto;
        padding: 0 20px;
    }

    /* Header Card */
    .tb-job-card {
        background: var(--card-bg);
        border-radius: 12px;
        border: 1px solid var(--border-color);
        padding: 28px 32px;
        margin-bottom: 28px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .tb-job-badge {
        display: inline-block;
        background: #eff6ff;
        color: var(--primary);
        font-size: 0.8rem;
        font-weight: 600;
        padding: 4px 10px;
        border-radius: 9999px;
        margin-bottom: 12px;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    .tb-job-title {
        font-size: 1.875rem;
        font-weight: 800;
        color: var(--text-main);
        margin-bottom: 8px;
    }
    .tb-job-meta {
        display: flex;
        gap: 20px;
        font-size: 0.9rem;
        color: var(--text-muted);
        margin-bottom: 16px;
    }
    .tb-job-desc {
        color: #334155;
        font-size: 0.95rem;
        border-top: 1px solid #f1f5f9;
        padding-top: 16px;
    }

    /* Form Layout */
    .tb-form-section {
        background: var(--card-bg);
        border-radius: 12px;
        border: 1px solid var(--border-color);
        padding: 28px 32px;
        margin-bottom: 24px;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .tb-section-title {
        font-size: 1.15rem;
        font-weight: 700;
        color: #1e293b;
        margin-bottom: 20px;
        padding-bottom: 10px;
        border-bottom: 2px solid #f1f5f9;
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .tb-section-num {
        background: var(--primary);
        color: white;
        width: 24px;
        height: 24px;
        border-radius: 50%;
        font-size: 0.75rem;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    /* Form Fields */
    .tb-field {
        margin-bottom: 20px;
    }
    .tb-field:last-child {
        margin-bottom: 0;
    }
    .tb-label {
        display: block;
        font-weight: 600;
        font-size: 0.9rem;
        color: #334155;
        margin-bottom: 6px;
    }
    .tb-label .required {
        color: #ef4444;
        margin-left: 3px;
    }
    .tb-input, .tb-select, .tb-textarea {
        width: 100%;
        padding: 10px 14px;
        font-size: 0.95rem;
        border: 1px solid var(--border-color);
        border-radius: 8px;
        background: #ffffff;
        color: var(--text-main);
        transition: border-color 0.15s ease, box-shadow 0.15s ease;
    }
    .tb-input:focus, .tb-select:focus, .tb-textarea:focus {
        outline: none;
        border-color: var(--primary);
        box-shadow: 0 0 0 3px var(--focus-ring);
    }
    .tb-textarea {
        resize: vertical;
        min-height: 90px;
    }

    /* Radio buttons */
    .tb-radio-group {
        display: flex;
        flex-wrap: wrap;
        gap: 16px;
        margin-top: 6px;
    }
    .tb-radio-option {
        display: flex;
        align-items: center;
        gap: 8px;
        background: #f8fafc;
        border: 1px solid var(--border-color);
        padding: 8px 16px;
        border-radius: 8px;
        cursor: pointer;
        font-size: 0.9rem;
        transition: background 0.15s ease;
    }
    .tb-radio-option:hover {
        background: #f1f5f9;
    }
    .tb-radio-option input[type="radio"] {
        accent-color: var(--primary);
        width: 16px;
        height: 16px;
    }

    /* File input */
    .tb-file-input {
        padding: 8px;
        border: 2px dashed var(--border-color);
        background: #f8fafc;
        border-radius: 8px;
        cursor: pointer;
    }
    .tb-file-input:hover {
        border-color: var(--primary);
    }

    /* CAPTCHA Box */
    .tb-captcha-wrapper {
        margin-top: 10px;
    }
    .tb-mock-captcha {
        display: inline-flex;
        align-items: center;
        gap: 16px;
        background: #f9f9f9;
        border: 1px solid #d3d3d3;
        border-radius: 4px;
        padding: 12px 16px;
        box-shadow: 0 0 4px rgba(0,0,0,0.08);
        min-width: 300px;
    }
    .tb-mock-captcha-check {
        display: flex;
        align-items: center;
        gap: 10px;
    }
    .tb-mock-captcha-check input[type="checkbox"] {
        width: 24px;
        height: 24px;
        cursor: pointer;
        accent-color: var(--primary);
    }
    .tb-mock-captcha-text {
        font-size: 0.85rem;
        font-family: Roboto, helvetica, arial, sans-serif;
        color: #222;
        font-weight: 500;
    }
    .tb-mock-captcha-logo {
        margin-left: auto;
        display: flex;
        flex-direction: column;
        align-items: center;
        font-size: 0.65rem;
        color: #555;
    }
    .tb-mock-captcha-logo svg {
        width: 28px;
        height: 28px;
        margin-bottom: 2px;
    }

    /* Submit Button */
    .tb-submit-btn {
        width: 100%;
        background: var(--primary);
        color: #ffffff;
        font-size: 1.05rem;
        font-weight: 700;
        padding: 14px 24px;
        border: none;
        border-radius: 8px;
        cursor: pointer;
        transition: background-color 0.15s ease, transform 0.1s ease;
        box-shadow: 0 2px 4px rgba(37, 99, 235, 0.2);
    }
    .tb-submit-btn:hover {
        background: var(--primary-hover);
    }
    .tb-submit-btn:active {
        transform: translateY(1px);
    }

    /* Alert Banner */
    .tb-alert {
        background: var(--error-bg);
        border: 1px solid var(--error-border);
        color: var(--error-text);
        padding: 14px 18px;
        border-radius: 8px;
        margin-bottom: 24px;
        font-size: 0.9rem;
    }

    /* Success Page */
    .tb-success-card {
        background: var(--card-bg);
        border-radius: 12px;
        border: 1px solid var(--success-border);
        padding: 40px 32px;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);
    }
    .tb-success-icon {
        width: 64px;
        height: 64px;
        background: var(--success-bg);
        color: #10b981;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        margin: 0 auto 20px;
        font-size: 2rem;
    }
    .tb-success-title {
        font-size: 1.75rem;
        font-weight: 800;
        color: #065f46;
        margin-bottom: 8px;
    }
    .tb-app-id-box {
        background: #f0fdf4;
        border: 2px dashed #a7f3d0;
        padding: 16px 24px;
        border-radius: 8px;
        display: inline-block;
        margin: 20px 0;
    }
    .tb-app-id-label {
        font-size: 0.8rem;
        text-transform: uppercase;
        color: #047857;
        letter-spacing: 0.05em;
        font-weight: 700;
    }
    .tb-app-id-val {
        font-size: 1.5rem;
        font-weight: 900;
        color: #064e3b;
        letter-spacing: 0.05em;
        font-family: monospace;
    }
    .tb-details-table {
        margin: 24px auto 0;
        max-width: 500px;
        text-align: left;
        border-collapse: collapse;
        width: 100%;
        font-size: 0.9rem;
    }
    .tb-details-table td {
        padding: 8px 12px;
        border-bottom: 1px solid #e2e8f0;
    }
    .tb-details-table td:first-child {
        font-weight: 600;
        color: #475569;
        width: 40%;
    }
</style>
"""

TALENTBRIDGE_APPLICATION_FORM_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Software Developer Intern - TalentBridge Careers</title>
    """ + TALENTBRIDGE_BASE_CSS + """
    {% if recaptcha_site_key %}
    <script src="https://www.google.com/recaptcha/api.js" async defer></script>
    {% endif %}
</head>
<body>
    <header class="tb-navbar">
        <div class="tb-brand">
            <div class="tb-brand-icon">TB</div>
            <span>TalentBridge</span>
        </div>
        <div class="tb-nav-links">
            <span>Jobs</span>
            <span>About Us</span>
            <span>Contact</span>
        </div>
    </header>

    <main class="tb-container">
        <!-- Job Banner -->
        <div class="tb-job-card">
            <span class="tb-job-badge">Engineering & Technology</span>
            <h1 class="tb-job-title">Software Developer Intern</h1>
            <div class="tb-job-meta">
                <span>📍 Remote / Hybrid (USA)</span>
                <span>💼 Full-Time Internship</span>
                <span>⏱️ Posted 2 days ago</span>
            </div>
            <div class="tb-job-desc">
                <p>TalentBridge is looking for an enthusiastic Software Developer Intern to join our core engineering team. You will work alongside senior developers to build scalable web APIs, automate workflow pipelines, and craft modern user interfaces.</p>
            </div>
        </div>

        {% if error_msg %}
        <div class="tb-alert">
            <strong>Application Error:</strong> {{ error_msg }}
        </div>
        {% endif %}

        <!-- Application Form -->
        <form method="POST" action="/talentbridge/apply" enctype="multipart/form-data" id="job_application_form">
            <!-- Section 1: Candidate Details -->
            <div class="tb-form-section">
                <h2 class="tb-section-title">
                    <span class="tb-section-num">1</span>
                    Personal Information
                </h2>

                <div class="tb-field">
                    <label class="tb-label" for="candidate_name">
                        Candidate Name <span class="required">*</span>
                    </label>
                    <input type="text" class="tb-input" id="candidate_name" name="candidate_name" placeholder="e.g. Jane Doe" required value="{{ form_data.get('candidate_name', '') }}">
                </div>

                <div class="tb-field">
                    <label class="tb-label">
                        Gender <span class="required">*</span>
                    </label>
                    <div class="tb-radio-group">
                        <label class="tb-radio-option">
                            <input type="radio" id="gender_male" name="gender" value="Male" {% if form_data.get('gender') == 'Male' %}checked{% endif %} required>
                            <span>Male</span>
                        </label>
                        <label class="tb-radio-option">
                            <input type="radio" id="gender_female" name="gender" value="Female" {% if form_data.get('gender') == 'Female' %}checked{% endif %}>
                            <span>Female</span>
                        </label>
                        <label class="tb-radio-option">
                            <input type="radio" id="gender_nonbinary" name="gender" value="Non-binary" {% if form_data.get('gender') == 'Non-binary' %}checked{% endif %}>
                            <span>Non-binary</span>
                        </label>
                        <label class="tb-radio-option">
                            <input type="radio" id="gender_prefer_not" name="gender" value="Prefer not to say" {% if form_data.get('gender') == 'Prefer not to say' %}checked{% endif %}>
                            <span>Prefer not to say</span>
                        </label>
                    </div>
                </div>
            </div>

            <!-- Section 2: Contact & Location -->
            <div class="tb-form-section">
                <h2 class="tb-section-title">
                    <span class="tb-section-num">2</span>
                    Contact & Address
                </h2>

                <div class="tb-field">
                    <label class="tb-label" for="email_address">
                        Email Address <span class="required">*</span>
                    </label>
                    <input type="email" class="tb-input" id="email_address" name="email_address" placeholder="e.g. jane.doe@example.com" required value="{{ form_data.get('email_address', '') }}">
                </div>

                <div class="tb-field">
                    <label class="tb-label" for="contact_number">
                        Contact Number <span class="required">*</span>
                    </label>
                    <input type="tel" class="tb-input" id="contact_number" name="contact_number" placeholder="e.g. +1 (555) 019-2834" required value="{{ form_data.get('contact_number', '') }}">
                </div>

                <div class="tb-field">
                    <label class="tb-label" for="residential_address">
                        Residential Address <span class="required">*</span>
                    </label>
                    <textarea class="tb-textarea" id="residential_address" name="residential_address" placeholder="Enter your street address, apartment or suite number" required>{{ form_data.get('residential_address', '') }}</textarea>
                </div>

                <div class="tb-field" style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
                    <div>
                        <label class="tb-label" for="city">
                            City <span class="required">*</span>
                        </label>
                        <input type="text" class="tb-input" id="city" name="city" placeholder="e.g. San Francisco" required value="{{ form_data.get('city', '') }}">
                    </div>
                    <div>
                        <label class="tb-label" for="state">
                            State <span class="required">*</span>
                        </label>
                        <select class="tb-select" id="state" name="state" required>
                            <option value="" disabled {% if not form_data.get('state') %}selected{% endif %}>-- Select State --</option>
                            <option value="California" {% if form_data.get('state') == 'California' %}selected{% endif %}>California</option>
                            <option value="New York" {% if form_data.get('state') == 'New York' %}selected{% endif %}>New York</option>
                            <option value="Texas" {% if form_data.get('state') == 'Texas' %}selected{% endif %}>Texas</option>
                            <option value="Washington" {% if form_data.get('state') == 'Washington' %}selected{% endif %}>Washington</option>
                            <option value="Illinois" {% if form_data.get('state') == 'Illinois' %}selected{% endif %}>Illinois</option>
                            <option value="Florida" {% if form_data.get('state') == 'Florida' %}selected{% endif %}>Florida</option>
                            <option value="Massachusetts" {% if form_data.get('state') == 'Massachusetts' %}selected{% endif %}>Massachusetts</option>
                            <option value="Other" {% if form_data.get('state') == 'Other' %}selected{% endif %}>Other</option>
                        </select>
                    </div>
                </div>
            </div>

            <!-- Section 3: Resume Upload -->
            <div class="tb-form-section">
                <h2 class="tb-section-title">
                    <span class="tb-section-num">3</span>
                    Application Materials
                </h2>

                <div class="tb-field">
                    <label class="tb-label" for="resume">
                        Resume / CV <span class="required">*</span>
                    </label>
                    <input type="file" class="tb-input tb-file-input" id="resume" name="resume" accept=".pdf,.doc,.docx" required>
                    <p style="font-size: 0.8rem; color: #64748b; margin-top: 6px;">Accepted formats: PDF, DOC, DOCX (Max 10MB)</p>
                </div>
            </div>

            <!-- Section 4: CAPTCHA Checkpoint -->
            <button type="submit" class="tb-submit-btn" id="submit_application_btn">
                Submit Application
            </button>
        </form>
    </main>
</body>
</html>
"""

TALENTBRIDGE_SUCCESS_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Application Submitted - TalentBridge Careers</title>
    """ + TALENTBRIDGE_BASE_CSS + """
</head>
<body>
    <header class="tb-navbar">
        <div class="tb-brand">
            <div class="tb-brand-icon">TB</div>
            <span>TalentBridge</span>
        </div>
        <div class="tb-nav-links">
            <span>Jobs</span>
            <span>About Us</span>
            <span>Contact</span>
        </div>
    </header>

    <main class="tb-container" data-civicflow-success="true" id="talentbridge_success_container">
        <div class="tb-success-card">
            <div class="tb-success-icon">✓</div>
            <h1 class="tb-success-title" data-civicflow-success="true">Application Submitted Successfully</h1>
            <p style="color: #475569;">Thank you for applying for the <strong>Software Developer Intern</strong> role at TalentBridge. We have received your application materials.</p>

            <div class="tb-app-id-box">
                <div class="tb-app-id-label">Your Application Reference Number</div>
                <div class="tb-app-id-val" id="application_id_display">{{ application_id }}</div>
            </div>

            <table class="tb-details-table">
                <tr>
                    <td>Candidate Name:</td>
                    <td>{{ app_data.candidate_name }}</td>
                </tr>
                <tr>
                    <td>Email Address:</td>
                    <td>{{ app_data.email_address }}</td>
                </tr>
                <tr>
                    <td>Contact Number:</td>
                    <td>{{ app_data.contact_number }}</td>
                </tr>
                <tr>
                    <td>Location:</td>
                    <td>{{ app_data.city }}, {{ app_data.state }}</td>
                </tr>
                <tr>
                    <td>Resume File:</td>
                    <td>{{ app_data.resume_filename }}</td>
                </tr>
                <tr>
                    <td>Submitted At:</td>
                    <td>{{ app_data.submitted_at }}</td>
                </tr>
            </table>

            <div style="margin-top: 32px;">
                <a href="/talentbridge" style="display: inline-block; background: #0f172a; color: white; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-weight: 600; font-size: 0.9rem;">Submit Another Application</a>
            </div>
        </div>
    </main>
</body>
</html>
"""

# In-memory record for test reference
SUBMITTED_APPLICATIONS = {}

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------

@talentbridge_bp.route('/', methods=['GET'])
def application_form():
    return render_template_string(
        TALENTBRIDGE_APPLICATION_FORM_HTML,
        form_data={},
        error_msg=None
    )

@talentbridge_bp.route('/apply', methods=['POST'])
def submit_application():
    candidate_name = request.form.get('candidate_name', '').strip()
    contact_number = request.form.get('contact_number', '').strip()
    email_address = request.form.get('email_address', '').strip()
    residential_address = request.form.get('residential_address', '').strip()
    city = request.form.get('city', '').strip()
    state = request.form.get('state', '').strip()
    gender = request.form.get('gender', '').strip()

    form_data = {
        'candidate_name': candidate_name,
        'contact_number': contact_number,
        'email_address': email_address,
        'residential_address': residential_address,
        'city': city,
        'state': state,
        'gender': gender
    }

    # Validate required text fields
    missing_fields = []
    if not candidate_name: missing_fields.append('Candidate Name')
    if not contact_number: missing_fields.append('Contact Number')
    if not email_address: missing_fields.append('Email Address')
    if not residential_address: missing_fields.append('Residential Address')
    if not city: missing_fields.append('City')
    if not state: missing_fields.append('State')
    if not gender: missing_fields.append('Gender')

    if missing_fields:
        return render_template_string(
            TALENTBRIDGE_APPLICATION_FORM_HTML,
            form_data=form_data,
            error_msg=f"Please fill in all required fields: {', '.join(missing_fields)}"
        ), 400

    # Validate File Upload
    if 'resume' not in request.files:
        return render_template_string(
            TALENTBRIDGE_APPLICATION_FORM_HTML,
            form_data=form_data,
            error_msg="Please upload a valid Resume / CV file."
        ), 400

    resume_file = request.files['resume']
    if not resume_file or resume_file.filename == '':
        return render_template_string(
            TALENTBRIDGE_APPLICATION_FORM_HTML,
            form_data=form_data,
            error_msg="Please select a Resume / CV file to attach."
        ), 400

    # Save Resume File safely
    raw_filename = resume_file.filename
    safe_basename = "".join([c for c in raw_filename if c.isalnum() or c in "._-"]).strip()
    if not safe_basename:
        safe_basename = "resume.pdf"
    
    unique_file_id = str(uuid.uuid4())[:8]
    saved_filename = f"{unique_file_id}_{safe_basename}"
    file_path = os.path.join(STORAGE_DIR, saved_filename)
    resume_file.save(file_path)

    # Generate Application ID
    app_id_suffix = uuid.uuid4().hex[:4].upper()
    application_id = f"CF-2026-{app_id_suffix}"

    app_record = {
        'application_id': application_id,
        'candidate_name': candidate_name,
        'email_address': email_address,
        'contact_number': contact_number,
        'residential_address': residential_address,
        'city': city,
        'state': state,
        'gender': gender,
        'resume_filename': raw_filename,
        'saved_filepath': file_path,
        'submitted_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    SUBMITTED_APPLICATIONS[application_id] = app_record

    return render_template_string(
        TALENTBRIDGE_SUCCESS_HTML,
        application_id=application_id,
        app_data=app_record
    )
