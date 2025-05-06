import os
import json
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import asyncio

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Import calendar integration modules
from calendar_integrations.google_calendar import GoogleCalendarAPI
from calendar_integrations.microsoft_calendar import MicrosoftCalendarAPI
from calendar_integrations.caldav_calendar import CalDAVCalendarAPI

# Import AI agent module
from agent.calendar_agent import CalendarAgent
from agent.speech_recognition import SpeechRecognizer

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("calendar_agent.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="Calendar AI Agent API")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize calendar APIs
google_calendar = GoogleCalendarAPI()
microsoft_calendar = MicrosoftCalendarAPI()
caldav_calendar = CalDAVCalendarAPI()

# Initialize AI agent
calendar_agent = CalendarAgent()

# Initialize speech recognizer
speech_recognizer = SpeechRecognizer(model_name=os.getenv("WHISPER_MODEL", "base"))

# Pydantic models
class PromptRequest(BaseModel):
    prompt: str

class PromptResponse(BaseModel):
    message: str
    actions: Optional[List[Dict[str, Any]]] = None

class Calendar(BaseModel):
    id: str
    name: str
    provider: str
    email: Optional[str] = None
    color: Optional[str] = None

# API routes
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/calendars", response_model=List[Calendar])
async def get_calendars():
    """Get all connected calendars"""
    try:
        # In a real app, we would fetch from database
        # For demo, return mock data
        calendars = [
            {
                "id": "google_primary",
                "name": "My Calendar",
                "provider": "Google",
                "email": "user@example.com",
                "color": "#4285F4"
            }
        ]
        return calendars
    except Exception as e:
        logger.error(f"Error fetching calendars: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/process-prompt", response_model=PromptResponse)
async def process_prompt(request: PromptRequest, background_tasks: BackgroundTasks):
    """Process a natural language prompt from the user"""
    try:
        # Process the prompt with the AI agent
        response = calendar_agent.process_prompt(request.prompt)
        
        # If the agent identified actions to take, execute them in the background
        if response.get("actions"):
            background_tasks.add_task(execute_calendar_actions, response["actions"])
        
        return response
    except Exception as e:
        logger.error(f"Error processing prompt: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def execute_calendar_actions(actions: List[Dict[str, Any]]):
    """Execute calendar actions in the background"""
    for action in actions:
        try:
            action_type = action.get("type")
            calendar_id = action.get("calendar_id")
            
            if action_type == "create_event":
                # Determine which calendar API to use based on the calendar_id
                if calendar_id.startswith("google_"):
                    await google_calendar.create_event(action["event"])
                elif calendar_id.startswith("microsoft_"):
                    await microsoft_calendar.create_event(action["event"])
                elif calendar_id.startswith("caldav_"):
                    await caldav_calendar.create_event(action["event"])
            
            elif action_type == "update_event":
                if calendar_id.startswith("google_"):
                    await google_calendar.update_event(action["event_id"], action["updates"])
                elif calendar_id.startswith("microsoft_"):
                    await microsoft_calendar.update_event(action["event_id"], action["updates"])
                elif calendar_id.startswith("caldav_"):
                    await caldav_calendar.update_event(action["event_id"], action["updates"])
            
            elif action_type == "delete_event":
                if calendar_id.startswith("google_"):
                    await google_calendar.delete_event(action["event_id"])
                elif calendar_id.startswith("microsoft_"):
                    await microsoft_calendar.delete_event(action["event_id"])
                elif calendar_id.startswith("caldav_"):
                    await caldav_calendar.delete_event(action["event_id"])
            
            logger.info(f"Successfully executed action: {action_type}")
        except Exception as e:
            logger.error(f"Error executing calendar action: {str(e)}")

@app.post("/auth/google/callback")
async def google_auth_callback():
    """Handle Google OAuth callback"""
    # In a real app, we would handle the OAuth callback
    return {"status": "success"}

@app.post("/auth/microsoft/callback")
async def microsoft_auth_callback():
    """Handle Microsoft OAuth callback"""
    # In a real app, we would handle the OAuth callback
    return {"status": "success"}

@app.post("/auth/caldav/connect")
async def caldav_connect():
    """Connect to CalDAV server"""
    # In a real app, we would handle the CalDAV connection
    return {"status": "success"}

@app.post("/speech-to-text")
async def speech_to_text(audio: UploadFile = File(...)):
    """Convert speech to text using Whisper"""
    try:
        # Initialize the speech recognizer if not already initialized
        if not speech_recognizer.initialized:
            await speech_recognizer.initialize()
        
        # Read the audio file
        audio_data = await audio.read()
        
        # Create a temporary file to save the audio
        temp_file_path = f"temp_{audio.filename}"
        with open(temp_file_path, "wb") as f:
            f.write(audio_data)
        
        try:
            # Process the audio file
            result = await speech_recognizer.transcribe_audio(temp_file_path)
            
            # If successful, process the transcribed text as a prompt
            if "text" in result and result["text"]:
                logger.info(f"Transcribed text: {result['text']}")
                
                # Optionally process the transcribed text as a prompt
                # This allows the voice input to be processed the same way as text input
                prompt_response = calendar_agent.process_prompt(result["text"])
                
                # Add the prompt response to the result
                result["prompt_response"] = prompt_response
            
            return result
        finally:
            # Clean up the temporary file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
    
    except Exception as e:
        logger.error(f"Error in speech-to-text: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
