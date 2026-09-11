# CivicFlow Registration Fix Summary

## Problem Identified
The 422 error on `POST /auth/register` was caused by:
1. **Missing field in frontend payload**: `parent_user_id` was not being sent
2. **Phone field handling**: Empty strings needed to be converted to `null`
3. **HTTPException detail format**: Backend was using dict instead of string for error details

## Changes Made

### 1. Frontend (`civicflow/frontend/js/app.js`)

#### Fixed register() function:
```javascript
async function register(e) {
  e.preventDefault();
  const btn = document.getElementById('btnRegister');
  setLoading(btn, true);
  try {
    const res = await api('/auth/register', 'POST', {
      name:           document.getElementById('regName').value.trim() || document.getElementById('regEmail').value.split('@')[0],
      email:          document.getElementById('regEmail').value,
      phone:          document.getElementById('regPhone').value || null,  // ✓ Convert empty to null
      password:       document.getElementById('regPassword').value,
      role:           _role,
      parent_user_id: null,  // ✓ Added this field
    });
    // ... rest of the code
  }
}
```

#### Enhanced error handling:
```javascript
async function api(path, method = 'GET', body = null, isForm = false) {
  // ... 
  if (!res.ok) {
    // Enhanced 422 error debugging
    if (res.status === 422 && data.errors) {
      console.error('[422 Validation Error]', data.errors);
      const fieldErrors = data.errors.map(e => `${e.loc.join('.')}: ${e.msg}`).join('; ');
      throw new Error(`Validation failed: ${fieldErrors}`);
    }
    throw new Error(data.detail?.message || data.message || data.detail || 'Server error');
  }
  // ...
}
```

### 2. Backend (`civicflow/backend/models/user_models.py`)

#### Added phone validator to RegisterRequestV2:
```python
class RegisterRequestV2(BaseModel):
    name: str
    email: str
    password: str
    phone: Optional[str] = None
    role: Literal["primary", "relative"] = "primary"
    parent_user_id: Optional[str] = None

    @field_validator("phone")
    @classmethod
    def normalize_phone(cls, v):
        if v == "" or v is None:
            return None
        return v.strip() if v else None
    
    # ... other validators
```

### 3. Backend (`civicflow/backend/api/auth.py`)

#### Added debug logging to register endpoint:
```python
@router.post("/register", summary="Create a new account")
async def register(request: RegisterRequestV2):
    try:
        print(f"[Auth API] Register request received: email={request.email}, role={request.role}, phone={request.phone}, parent_user_id={request.parent_user_id}")
        # ... registration logic
        print(f"[Auth API] User registered successfully: user_id={user.user_id}, email={email}")
        return ok("User registered successfully", data=_to_public(user).model_dump())
    except Exception as e:
        print(f"[Auth API] Registration error: {type(e).__name__}: {str(e)}")
        raise
```

#### Fixed HTTPException format in login:
```python
@router.post("/login", summary="Login and get JWT token")
async def login(request: LoginRequest, req: Request):
    await check_login_rate_limit(req)
    email = request.email.lower().strip()
    user = await _get_user_by_email(email)

    if not user or not verify_password(request.password, user.password_hash):
        print(f"[Auth API] Login failed for email: {email}")
        raise HTTPException(status_code=401, detail="Invalid email or password")  # ✓ String, not dict
    
    # ... rest of login logic
```

### 4. Backend (`civicflow/backend/main.py`)

#### Enhanced 422 error handler:
```python
@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError):
    errors = exc.errors()
    logger.error(f"[422 Validation Error] {request.method} {request.url.path}")
    logger.error(f"Request body: {await request.body()}")
    for e in errors:
        logger.error(f"  - Field: {e['loc']}, Error: {e['msg']}, Type: {e['type']}")
    
    msg = "; ".join(f"{e['loc'][-1]}: {e['msg']}" for e in errors)
    return JSONResponse(
        status_code=422,
        content={
            "success": False, 
            "message": f"Validation error: {msg}", 
            "data": {},
            "errors": errors  # Include full error details for debugging
        },
    )
```

## Expected Payloads

### POST /auth/register - Request
```json
{
  "name": "John Doe",
  "email": "john@example.com",
  "phone": null,
  "password": "password123",
  "role": "primary",
  "parent_user_id": null
}
```

### POST /auth/register - Success Response (200)
```json
{
  "success": true,
  "message": "User registered successfully",
  "data": {
    "user_id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "john@example.com",
    "phone": null,
    "role": "primary",
    "is_verified": false,
    "linked_user_ids": [],
    "telegram_chat_id": null,
    "created_at": "2024-01-15T10:30:00",
    "last_login": null
  }
}
```

### POST /auth/register - Validation Error (422)
```json
{
  "success": false,
  "message": "Validation error: email: Invalid email address",
  "data": {},
  "errors": [
    {
      "type": "value_error",
      "loc": ["body", "email"],
      "msg": "Invalid email address",
      "input": "invalid-email",
      "ctx": {"error": {}}
    }
  ]
}
```

### POST /auth/login - Request
```json
{
  "email": "john@example.com",
  "password": "password123"
}
```

### POST /auth/login - Success Response (200)
```json
{
  "success": true,
  "message": "Login successful",
  "data": {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
    "token_type": "bearer",
    "user": {
      "user_id": "550e8400-e29b-41d4-a716-446655440000",
      "email": "john@example.com",
      "phone": null,
      "role": "primary",
      "is_verified": false,
      "linked_user_ids": [],
      "telegram_chat_id": null,
      "created_at": "2024-01-15T10:30:00",
      "last_login": "2024-01-15T10:35:00"
    }
  }
}
```

### POST /auth/login - Error Response (401)
```json
{
  "detail": "Invalid email or password"
}
```

## Testing

### Manual Test
1. Open the frontend: `http://localhost:5500/civicflow/frontend/index.html`
2. Click "Register" tab
3. Fill in the form:
   - Name: Test User
   - Email: test@example.com
   - Phone: (leave empty or enter number)
   - Password: password123
4. Click "Create Account"
5. Check browser console for detailed logs
6. Check backend terminal for debug logs

### Automated Test
Run the test script:
```bash
cd civicflow/backend
python test_register.py
```

## Debugging 422 Errors

If you still get a 422 error, check:

1. **Browser Console**: Look for `[422 Validation Error]` with field details
2. **Backend Logs**: Check for validation errors with field names and types
3. **Request Body**: Verify Content-Type is `application/json`
4. **Field Types**: Ensure all fields match the Pydantic schema exactly

## Architecture Notes

### Registration Flow
1. **Minimal registration**: Only email, password, phone, role, parent_user_id
2. **Profile setup later**: Full name, DOB, address collected in profile-setup flow
3. **Optional fields**: phone and parent_user_id can be null
4. **Name field**: Uses email prefix as default if not provided

### Error Handling
1. **422 Validation Errors**: Logged with full field details
2. **401 Auth Errors**: Simple string message
3. **Consistent Format**: All success responses use `{success, message, data}`
4. **Debug Mode**: Enhanced logging in both frontend and backend
