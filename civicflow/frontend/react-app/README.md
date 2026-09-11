# CivicFlow React Frontend

Complete React application for CivicFlow form automation system.

## Features

✅ **Authentication** - Login/Register with JWT tokens
✅ **Dashboard** - View sessions and quick actions
✅ **Form Search** - Search forms by description or paste URL
✅ **Form Review** - Review and edit mapped form data
✅ **Execution** - Live WebSocket updates during form filling
✅ **Profile Setup** - Complete user profile management
✅ **Document Upload** - Upload and extract data from documents
✅ **Document Management** - View and manage uploaded documents
✅ **AI Chat** - Sahayak AI assistant for help
✅ **Session Detail** - View detailed session information

## API Endpoints Used

### Authentication (`/api/auth`)
- `POST /auth/register` - Create new account
- `POST /auth/login` - Login and get JWT token
- `GET /auth/me` - Get current user profile
- `POST /auth/profile` - Update user profile

### Sessions (`/api`)
- `POST /start` - Create new session and start analysis
- `GET /sessions` - List all sessions
- `GET /sessions/{id}/status` - Get session status
- `GET /sessions/{id}/confirm-data` - Get form review data
- `POST /sessions/{id}/confirm` - Confirm form data
- `POST /sessions/{id}/execute` - Execute form filling
- `POST /sessions/{id}/resume` - Resume after CAPTCHA/OTP

### Documents (`/api/documents`)
- `POST /documents/upload` - Upload and process document
- `GET /documents/list` - List uploaded documents
- `GET /documents/{id}/fields` - Get document fields
- `POST /documents/confirm/{id}` - Confirm and save document
- `DELETE /documents/{id}` - Delete document

### Search (`/api/search`)
- `POST /search/form` - Search for forms by description
- `POST /search/verify` - Verify form URL

### Chat (`/api/chat`)
- `POST /chat` - Send message to AI counsellor
- `GET /chat/history/{session_id}` - Get chat history

### WebSocket
- `ws://localhost:8000/ws/{session_id}` - Live execution updates

## Components

### Core
- **App.jsx** - Main app with routing and auth
- **Header.jsx** - Navigation header
- **Toast.jsx** - Toast notifications

### Pages
- **Login.jsx** - Login/register page
- **Dashboard.jsx** - Main dashboard
- **FormSearch.jsx** - Form search page
- **FormReview.jsx** - Form review and edit
- **ExecutionView.jsx** - Live execution monitoring
- **ProfileSetup.jsx** - User profile management
- **SessionDetail.jsx** - Session details page
- **DocumentUpload.jsx** - Document upload page
- **DocumentList.jsx** - Document management
- **ChatBot.jsx** - AI assistant chat

## Setup

1. Install dependencies:
```bash
npm install
```

2. Start development server:
```bash
npm run dev
```

3. Build for production:
```bash
npm run build
```

## Configuration

- **Base URL**: `/api` (proxied to `http://localhost:8000` in dev)
- **WebSocket**: `ws://localhost:8000/ws/{session_id}`
- **Port**: 3000

## State Management

- User authentication state in App.jsx
- Token stored in localStorage
- Axios default headers for JWT
- Session state per component

## Styling

- **App.css** - Original glassmorphism design
- **components-styles.css** - Additional component styles
- Sage green color scheme preserved
- Responsive design for mobile/desktop

## API Response Format

All backend responses follow:
```json
{
  "success": true,
  "message": "...",
  "data": { ... }
}
```

## WebSocket Events

- `status_change` - Session status updated
- `field_filled` - Field filled successfully
- `captcha_detected` - CAPTCHA requires manual intervention
- `otp_required` - OTP verification needed
- `error` - Execution error occurred

## Browser Support

- Chrome/Edge (recommended)
- Firefox
- Safari
- Mobile browsers

## Development Notes

- Hot reload enabled in dev mode
- Proxy configured for API calls
- WebSocket connection auto-reconnect
- Toast notifications for user feedback
- Loading states for async operations
