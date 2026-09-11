# CivicFlow Fixes Summary

## Issues Fixed

### 1. **422 Error on POST /auth/register** ✅
- **Problem**: Frontend payload didn't match backend `RegisterRequestV2` schema
- **Solution**: 
  - Added `parent_user_id: null` to frontend register payload
  - Added phone field validator to convert empty strings to `null`
  - Fixed response extraction in login/register functions
  - Added comprehensive console logging for debugging

### 2. **Frontend Login/Register Crash** ✅
- **Problem**: `cannot read properties of undefined (reading 'split')`
- **Solution**:
  - Replaced all `.split('@')` with `indexOf('@')` + `substring()`
  - Made `setUserUI()` null-safe
  - Made `register()` name generation null-safe
  - Added response validation before navigation

### 3. **JWT Token Expiry Issues** ✅
- **Problem**: Tokens were being created with ISO string timestamps instead of Unix timestamps
- **Solution**:
  - Changed `iat` and `exp` to use `int(datetime.utcnow().timestamp())`
  - Added backward compatibility for old ISO string tokens in decode function
  - Added debug logging for token creation

### 4. **MongoDB Truthiness Bug in Chat Flow** ✅
- **Problem**: `NotImplementedError: Database objects do not implement truth value testing`
- **Solution**:
  - Changed `if db:` → `if db is not None:` in all backend files
  - Changed `if not db:` → `if db is None:` in all backend files
  - Fixed in: `api/telegram.py`, `agents/counsellor.py`, `agents/doc_vault.py`

### 5. **404 Error on POST /auth/profile** ✅
- **Problem**: Profile update endpoint didn't exist
- **Solution**:
  - Created `/auth/profile` POST endpoint in `api/auth.py`
  - Handles `basic_info`, `contact`, `identity`, `education` sections
  - Saves to `user_profiles` collection in MongoDB
  - Returns updated profile data

### 6. **Chat Endpoint 500 Errors** ✅
- **Problem**: Chat endpoint was failing silently with 500 errors
- **Solution**:
  - Added graceful error handling in `/chat` endpoint
  - Returns friendly error messages instead of throwing 500
  - Checks for Gemini API key before processing
  - Added comprehensive error logging with traceback

## Files Changed

### Backend Files:
1. **`backend/utils/auth.py`**
   - Fixed JWT token creation to use Unix timestamps
   - Added backward compatibility in decode function
   - Line 113-118: Changed `iat` and `exp` to integers

2. **`backend/models/user_models.py`**
   - Added `normalize_phone` validator to RegisterRequestV2
   - Converts empty strings to None for phone field
   - Line 271-276: New validator

3. **`backend/api/auth.py`**
   - Added debug logging to register endpoint
   - Fixed HTTPException detail format
   - Added `/auth/profile` POST endpoint
   - Line 103-131: Registration logging
   - Line 225-290: New profile endpoint

4. **`backend/api/chat.py`**
   - Added graceful error handling
   - Checks for Gemini API key
   - Returns friendly errors instead of 500
   - Line 33-67: Enhanced error handling

5. **`backend/api/telegram.py`**
   - Fixed MongoDB truthiness checks
   - Line 77: `if not db:` → `if db is None:`
   - Line 137: `if db:` → `if db is not None:`
   - Line 157: `if db:` → `if db is not None:`

6. **`backend/agents/counsellor.py`**
   - Fixed MongoDB truthiness checks
   - Line 59: `if not db:` → `if db is None:`
   - Line 91: Already correct
   - Line 168: Already correct
   - Line 190: `if not db:` → `if db is None:`

7. **`backend/main.py`**
   - Enhanced 422 validation error handler
   - Logs request body and all field errors
   - Includes full error details in response
   - Line 91-106: Enhanced logging

### Frontend Files:
1. **`frontend/js/app.js`**
   - **Line 123-155**: Fixed `login()` function
     - Normalized response extraction
     - Added console logging
     - Added token validation
     - Fixed variable name (`res` instead of `loginRes`)
   
   - **Line 162-220**: Fixed `register()` function
     - Safe element access with optional chaining
     - Null-safe name generation using `indexOf()` + `substring()`
     - Added console logging
     - Normalized response extraction
     - Added token validation
   
   - **Line 231-239**: Fixed `setUserUI()` function
     - Null-safe email handling
     - Uses `indexOf('@')` + `substring()` instead of `split('@')`
     - Safe character extraction
   
   - **Line 25-52**: Enhanced `api()` helper
     - Added detailed 422 error parsing
     - Console logs validation errors
     - Displays field-specific error messages

## Expected Payloads

### POST /auth/register
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

### POST /auth/login
```json
{
  "email": "john@example.com",
  "password": "password123"
}
```

### POST /auth/profile
```json
{
  "basic_info": {
    "full_name": "John Doe",
    "dob": "1990-01-01",
    "gender": "Male"
  },
  "contact": {
    "address": "123 Main St",
    "pincode": "123456"
  }
}
```

## Testing Checklist

- [x] User can register with email and password
- [x] User can login successfully
- [x] Token is stored and used for authenticated requests
- [x] Dashboard loads after login
- [x] Profile setup page works
- [x] Profile update saves to database
- [x] Chat endpoint handles errors gracefully
- [x] MongoDB truthiness errors eliminated
- [x] No more `.split('@')` crashes

## Debug Commands

### Check backend logs:
```bash
# Look for these log messages:
[Auth API] Register request received: email=...
[Auth API] User registered successfully: user_id=...
[Auth API] Login successful for user_id=...
[Login] Response: {...}
[Login] Extracted: {...}
[Register] Payload: {...}
[Chat API] User ... sent message: ...
```

### Check browser console:
```javascript
// Should see:
[Login] Response: {success: true, data: {...}}
[Login] Extracted: {_token: "...", _userId: "...", _userEmail: "..."}
[Register] Payload: {name: "...", email: "...", ...}
```

## Next Steps

1. Add proper error toasts for failed operations
2. Add profile completion percentage calculation
3. Add document upload functionality
4. Configure Gemini API key for chat functionality
5. Add Telegram bot integration
6. Add form automation features
