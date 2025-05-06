# Calendar AI Agent

A desktop application that runs an AI agent in the background with access to your calendars. The agent can adjust events on any calendar based on your prompts.

## Tech Stack

### Frontend
- Electron (desktop application wrapper)
- React.js (UI framework)

### Backend
- Python with FastAPI
- LangChain for AI agent capabilities
- Calendar API integrations (Google Calendar, Microsoft Graph, CalDAV)

### Database
- SQLite for local storage

## Features
- Connect to multiple calendar services
- Natural language processing for calendar management
- Background agent that can autonomously manage your calendar
- Secure OAuth authentication for calendar access

## Setup Instructions
1. Install dependencies:
   ```bash
   # Install Node.js dependencies
   npm install

   # Install Python dependencies
   cd backend
   pip install -r requirements.txt
   cd ..
   ```

2. Configure API keys:
   - Rename `backend/.env.example` to `backend/.env`
   - Add your OpenAI API key
   - Configure OAuth credentials for Google and Microsoft calendars

3. Run the application:
   ```bash
   # Development mode (runs both backend and frontend)
   npm run dev

   # Or run separately
   # Backend only
   npm run start-backend
   
   # Frontend only
   npm run start
   ```

## Development
This application uses:

### Frontend
- Electron for desktop application packaging
- React for the user interface

### Backend
- Python FastAPI for the API server
- LangChain for AI agent capabilities
- SQLite for local data storage

### Calendar Integrations
- Google Calendar API
- Microsoft Graph API
- CalDAV protocol (for Apple Calendar and others)

## Building for Distribution
```bash
# Build for your platform
npm run build

# The packaged application will be in the 'dist' folder
```

## Security
- All API keys and tokens are stored locally
- OAuth is used for secure calendar access
- No calendar data is sent to external servers except the necessary API calls
