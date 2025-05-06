import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json
import re

from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
from langchain_openai import ChatOpenAI
from langchain.output_parsers import PydanticOutputParser
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# Define output schemas for the LLM
class CalendarAction(BaseModel):
    """Action to perform on a calendar"""
    type: str = Field(description="Type of action to perform (create_event, update_event, delete_event, or query)")
    calendar_id: Optional[str] = Field(None, description="ID of the calendar to perform the action on")
    event_id: Optional[str] = Field(None, description="ID of the event to update or delete")
    event: Optional[Dict[str, Any]] = Field(None, description="Event data for create or update actions")
    updates: Optional[Dict[str, Any]] = Field(None, description="Updates to apply to an event")
    query_params: Optional[Dict[str, Any]] = Field(None, description="Parameters for a calendar query")

class AgentResponse(BaseModel):
    """Response from the calendar agent"""
    message: str = Field(description="Human-readable response to the user's prompt")
    actions: List[CalendarAction] = Field(default_factory=list, description="List of actions to perform")
    confidence: float = Field(description="Confidence level in the interpretation (0.0 to 1.0)")

class CalendarAgent:
    """AI agent for processing natural language prompts about calendar management"""
    
    def __init__(self):
        # Initialize the language model
        self.llm = ChatOpenAI(
            model_name=os.getenv("OPENAI_MODEL_NAME", "gpt-4o"),
            temperature=0.1,
            api_key=os.getenv("OPENAI_API_KEY")
        )
        
        # Initialize the output parser
        self.parser = PydanticOutputParser(pydantic_object=AgentResponse)
        
        # Create the prompt template
        self.prompt_template = PromptTemplate(
            template="""
            You are an AI assistant that helps users manage their calendars. Your task is to interpret the user's request
            and determine what calendar actions to take.
            
            User's prompt: {prompt}
            
            Current date and time: {current_time}
            
            Available calendars:
            {calendars}
            
            Based on the user's prompt, determine what calendar actions to take. Possible actions include:
            - create_event: Create a new event on a calendar
            - update_event: Update an existing event on a calendar
            - delete_event: Delete an existing event from a calendar
            - query: Query the calendar for information
            
            For each action, provide the necessary details such as event title, start time, end time, etc.
            
            {format_instructions}
            """,
            input_variables=["prompt", "current_time", "calendars"],
            partial_variables={"format_instructions": self.parser.get_format_instructions()}
        )
        
        # Create the LLM chain
        self.chain = LLMChain(llm=self.llm, prompt=self.prompt_template)
    
    def process_prompt(self, prompt: str, calendars: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Process a natural language prompt and determine calendar actions"""
        try:
            # Get current time
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # If no calendars provided, use a default one
            if not calendars:
                calendars = [
                    {
                        "id": "google_primary",
                        "name": "My Calendar",
                        "provider": "Google"
                    }
                ]
            
            # Format calendars for the prompt
            calendars_str = "\n".join([f"- {cal['name']} (ID: {cal['id']}, Provider: {cal['provider']})" for cal in calendars])
            
            # Run the chain
            result = self.chain.run(
                prompt=prompt,
                current_time=current_time,
                calendars=calendars_str
            )
            
            # Parse the result
            try:
                parsed_result = self.parser.parse(result)
                return {
                    "message": parsed_result.message,
                    "actions": [action.dict(exclude_none=True) for action in parsed_result.actions],
                    "confidence": parsed_result.confidence
                }
            except Exception as e:
                logger.error(f"Error parsing LLM output: {str(e)}")
                # Fallback to a simpler parsing approach
                return self._fallback_parsing(result, prompt)
        
        except Exception as e:
            logger.error(f"Error processing prompt: {str(e)}")
            return {
                "message": f"I'm sorry, I couldn't process your request. Error: {str(e)}",
                "actions": [],
                "confidence": 0.0
            }
    
    def _fallback_parsing(self, result: str, prompt: str) -> Dict[str, Any]:
        """Fallback method for parsing LLM output if the structured parser fails"""
        # Extract the message (first paragraph)
        message_match = re.search(r'^(.*?)(?=\n\n|\Z)', result, re.DOTALL)
        message = message_match.group(1).strip() if message_match else "I've processed your request."
        
        # Try to identify actions based on keywords in the prompt and result
        actions = []
        
        # Check for event creation
        if any(keyword in prompt.lower() for keyword in ["create", "add", "schedule", "new"]):
            # Extract potential event details
            summary = self._extract_event_title(prompt)
            start_time, end_time = self._extract_datetime(prompt)
            
            if summary:
                actions.append({
                    "type": "create_event",
                    "calendar_id": "google_primary",  # Default to primary calendar
                    "event": {
                        "summary": summary,
                        "start": start_time.isoformat() if start_time else (datetime.now() + timedelta(days=1)).replace(hour=9, minute=0).isoformat(),
                        "end": end_time.isoformat() if end_time else (datetime.now() + timedelta(days=1)).replace(hour=10, minute=0).isoformat(),
                        "description": "",
                        "location": self._extract_location(prompt)
                    }
                })
        
        # Check for event updates
        elif any(keyword in prompt.lower() for keyword in ["update", "change", "modify", "reschedule", "move"]):
            # This is a simplified approach - in a real app, we would need to identify the specific event
            actions.append({
                "type": "update_event",
                "calendar_id": "google_primary",
                "event_id": "placeholder_id",  # In a real app, we would need to find the actual event ID
                "updates": {
                    "summary": self._extract_event_title(prompt),
                    "start": self._extract_datetime(prompt)[0].isoformat() if self._extract_datetime(prompt)[0] else None,
                    "end": self._extract_datetime(prompt)[1].isoformat() if self._extract_datetime(prompt)[1] else None,
                    "location": self._extract_location(prompt)
                }
            })
        
        # Check for event deletion
        elif any(keyword in prompt.lower() for keyword in ["delete", "remove", "cancel"]):
            actions.append({
                "type": "delete_event",
                "calendar_id": "google_primary",
                "event_id": "placeholder_id"  # In a real app, we would need to find the actual event ID
            })
        
        return {
            "message": message,
            "actions": actions,
            "confidence": 0.7  # Lower confidence for fallback parsing
        }
    
    def _extract_event_title(self, text: str) -> Optional[str]:
        """Extract a potential event title from text"""
        # This is a simplified approach - in a real app, we would use more sophisticated NLP
        title_patterns = [
            r'(?:meeting|appointment|event|call) (?:with|about) ([^\.]+)',
            r'(?:schedule|add|create) (?:a|an) ([^\.]+)',
            r'(?:titled|called|named) "([^"]+)"'
        ]
        
        for pattern in title_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return "New Event"  # Default title
    
    def _extract_datetime(self, text: str) -> tuple[Optional[datetime], Optional[datetime]]:
        """Extract potential start and end times from text"""
        # This is a simplified approach - in a real app, we would use more sophisticated NLP
        # For example, we might use a library like dateparser
        
        # For now, return None to indicate we couldn't extract times
        return None, None
    
    def _extract_location(self, text: str) -> Optional[str]:
        """Extract a potential location from text"""
        # This is a simplified approach - in a real app, we would use more sophisticated NLP
        location_patterns = [
            r'(?:at|in) ([^\.]+)',
            r'(?:location|place): ([^\.]+)'
        ]
        
        for pattern in location_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1).strip()
        
        return ""  # Default empty location
