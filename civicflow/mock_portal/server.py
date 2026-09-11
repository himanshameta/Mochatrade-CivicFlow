import os
from flask import Flask, request, jsonify, render_template_string
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
app.secret_key = "mock_secret"

# -----------------------------------------------------------------------------
# Route: Base CAPTCHA Form
# -----------------------------------------------------------------------------
CAPTCHA_FORM_HTML = """
<!DOCTYPE html>
<html>
<head><title>Mock Portal - CAPTCHA</title></head>
<body>
    <h2>Mock Service Registration</h2>
    <form method="POST" action="/">
        <label>Full Name:</label>
        <input type="text" name="fullName" required><br><br>
        
        <label>Verification Code:</label>
        <!-- Mock CAPTCHA image (placeholder) -->
        <div style="background:#eee; width:120px; height:40px; text-align:center; line-height:40px; font-weight:bold; font-family:monospace; margin-bottom:10px;">
            H7X9K
        </div>
        <input type="text" name="captcha" placeholder="Enter code above" required><br><br>
        
        <button type="submit">Submit</button>
    </form>
</body>
</html>
"""

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        captcha = request.form.get("captcha")
        if captcha != "H7X9K":
            return "Invalid CAPTCHA", 400
        return "Success!"
    return render_template_string(CAPTCHA_FORM_HTML)

# -----------------------------------------------------------------------------
# Route: Anti-Paste Form
# -----------------------------------------------------------------------------
ANTI_PASTE_HTML = """
<!DOCTYPE html>
<html>
<head><title>Mock Portal - Anti-Paste</title></head>
<body>
    <h2>Anti-Paste Demo</h2>
    <p>This form aggressively blocks pasting to test human-typing simulation.</p>
    <form method="POST" action="/anti-paste-form">
        <label>Full Name:</label>
        <input type="text" name="fullName" id="name_field" onpaste="return false;" required><br><br>
        
        <label>Address:</label>
        <textarea name="address" id="address_field" required></textarea><br><br>
        
        <button type="submit">Submit</button>
    </form>

    <script>
        // Aggressive paste blocker
        document.getElementById('address_field').addEventListener('paste', function(e) {
            e.preventDefault();
            alert("Pasting is disabled on this field for security reasons.");
        });
        
        // Disable right click to prevent context menu paste
        document.addEventListener('contextmenu', event => event.preventDefault());
    </script>
</body>
</html>
"""

@app.route("/anti-paste-form", methods=["GET", "POST"])
def anti_paste():
    if request.method == "POST":
        return "Anti-Paste Form Submitted successfully!"
    return render_template_string(ANTI_PASTE_HTML)

# -----------------------------------------------------------------------------
# Route: OTP Form
# -----------------------------------------------------------------------------
OTP_FORM_HTML = """
<!DOCTYPE html>
<html>
<head><title>Mock Portal - OTP Auth</title></head>
<body>
    <h2>Login via OTP</h2>
    {% if step == 'phone' %}
    <form method="POST" action="/otp-form">
        <input type="hidden" name="step" value="request_otp">
        <label>Phone Number:</label>
        <input type="tel" name="phone" required><br><br>
        <button type="submit" id="send_otp_btn">Send OTP</button>
    </form>
    {% elif step == 'verify' %}
    <p>OTP sent to {{ phone }}</p>
    <form method="POST" action="/otp-form">
        <input type="hidden" name="step" value="verify_otp">
        <input type="hidden" name="phone" value="{{ phone }}">
        <label>Enter OTP:</label>
        <input type="text" name="otp" required><br><br>
        <button type="submit" id="verify_otp_btn">Verify</button>
    </form>
    {% endif %}
</body>
</html>
"""

@app.route("/otp-form", methods=["GET", "POST"])
def otp_form():
    if request.method == "POST":
        step = request.form.get("step")
        if step == "request_otp":
            phone = request.form.get("phone")
            print(f"\n[Mock SMS] OTP for {phone} is: 123456\n")
            return render_template_string(OTP_FORM_HTML, step="verify", phone=phone)
        elif step == "verify_otp":
            otp = request.form.get("otp")
            if otp == "123456":
                return "Logged in successfully!"
            return "Invalid OTP", 401
            
    return render_template_string(OTP_FORM_HTML, step="phone")

# -----------------------------------------------------------------------------
# Route: Multi-Section Form
# -----------------------------------------------------------------------------
MULTI_SECTION_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Mock Portal - Multi-Section</title>
    <style>fieldset { margin-bottom: 20px; }</style>
</head>
<body>
    <h2>Comprehensive Registration</h2>
    <form method="POST" action="/multi-section">
        <fieldset>
            <legend>Personal Information</legend>
            <label>First Name:</label> <input type="text" name="first_name"><br>
            <label>Last Name:</label> <input type="text" name="last_name"><br>
        </fieldset>
        
        <fieldset>
            <legend>Contact Details</legend>
            <label>Email:</label> <input type="email" name="email"><br>
            <label>Phone:</label> <input type="tel" name="phone"><br>
        </fieldset>
        
        <fieldset>
            <legend>Address</legend>
            <label>Street:</label> <input type="text" name="street"><br>
            <label>City:</label> <input type="text" name="city"><br>
            <label>Pincode:</label> <input type="text" name="pincode"><br>
        </fieldset>
        
        <button type="submit">Submit Application</button>
    </form>
</body>
</html>
"""

@app.route("/multi-section", methods=["GET", "POST"])
def multi_section():
    if request.method == "POST":
        return "Multi-section form submitted!"
    return render_template_string(MULTI_SECTION_HTML)


if __name__ == "__main__":
    port = int(os.getenv("MOCK_PORTAL_PORT", 5001))
    print(f"Starting mock portal on port {port}")
    app.run(host="0.0.0.0", port=port, debug=True)
