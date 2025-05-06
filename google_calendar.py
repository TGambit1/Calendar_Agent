import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

logger = logging.getLogger(__name__)

class GoogleCalendarAPI:
    """Google Calendar API integration"""
    
    def __init__(self):
        self.scopes = ['https://www.googleapis.com/auth/calendar']
        self.credentials_file = 'credentials/google_credentials.json'
        self.token_file = 'credentials/google_token.json'
        self.service = None
    
    async def authenticate(self):
        """Authenticate with Google Calendar API"""
        creds = None
        
        # Check if token file exists
        if os.path.exists(self.token_file):
            with open(self.token_file, 'r') as token:
                creds = Credentials.from_authorized_user_info(json.load(token), self.scopes)
        
        # If credentials don't exist or are invalid, get new ones
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_file, self.scopes)
                creds = flow.run_local_server(port=0)
            
            # Save the credentials for the next run
            os.makedirs(os.path.dirname(self.token_file), exist_ok=True)
            with open(self.token_file, 'w') as token:
                token.write(creds.to_json())
        
        # Build the service
        self.service = build('calendar', 'v3', credentials=creds)
        return True
    
    async def get_calendars(self) -> List[Dict[str, Any]]:
        """Get list of user's calendars"""
        if not self.service:
            await self.authenticate()
        
        try:
            calendar_list = self.service.calendarList().list().execute()
            calendars = []
            
            for calendar in calendar_list.get('items', []):
                calendars.append({
                    'id': f"google_{calendar['id']}",
                    'name': calendar['summary'],
                    'provider': 'Google',
                    'email': calendar.get('id'),
                    'color': calendar.get('backgroundColor')
                })
            
            return calendars
        except Exception as e:
            logger.error(f"Error getting Google calendars: {str(e)}")
            raise
    
    async def get_events(self, calendar_id: str, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get events from a calendar within a time range"""
        if not self.service:
            await self.authenticate()
        
        # Remove the 'google_' prefix from calendar_id
        if calendar_id.startswith('google_'):
            calendar_id = calendar_id[7:]
        
        try:
            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=start_time.isoformat() + 'Z',
                timeMax=end_time.isoformat() + 'Z',
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = []
            for event in events_result.get('items', []):
                start = event['start'].get('dateTime', event['start'].get('date'))
                end = event['end'].get('dateTime', event['end'].get('date'))
                
                events.append({
                    'id': event['id'],
                    'summary': event['summary'],
                    'start': start,
                    'end': end,
                    'location': event.get('location', ''),
                    'description': event.get('description', ''),
                    'attendees': [attendee.get('email') for attendee in event.get('attendees', [])]
                })
            
            return events
        except Exception as e:
            logger.error(f"Error getting Google calendar events: {str(e)}")
            raise
    
    async def create_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new event in the calendar"""
        if not self.service:
            await self.authenticate()
        
        # Extract calendar_id and remove the 'google_' prefix
        calendar_id = event_data.pop('calendar_id', 'primary')
        if calendar_id.startswith('google_'):
            calendar_id = calendar_id[7:]
        
        # Format the event for Google Calendar API
        event = {
            'summary': event_data.get('summary', 'New Event'),
            'location': event_data.get('location', ''),
            'description': event_data.get('description', ''),
            'start': {
                'dateTime': event_data.get('start'),
                'timeZone': event_data.get('timeZone', 'UTC'),
            },
            'end': {
                'dateTime': event_data.get('end'),
                'timeZone': event_data.get('timeZone', 'UTC'),
            }
        }
        
        # Add attendees if provided
        if 'attendees' in event_data and event_data['attendees']:
            event['attendees'] = [{'email': email} for email in event_data['attendees']]
        
        try:
            created_event = self.service.events().insert(
                calendarId=calendar_id,
                body=event
            ).execute()
            
            logger.info(f"Event created: {created_event.get('htmlLink')}")
            return {
                'id': created_event['id'],
                'link': created_event.get('htmlLink')
            }
        except Exception as e:
            logger.error(f"Error creating Google calendar event: {str(e)}")
            raise
    
    async def update_event(self, event_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing event in the calendar"""
        if not self.service:
            await self.authenticate()
        
        # Extract calendar_id and remove the 'google_' prefix
        calendar_id = updates.pop('calendar_id', 'primary')
        if calendar_id.startswith('google_'):
            calendar_id = calendar_id[7:]
        
        try:
            # First get the existing event
            event = self.service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            # Update the event with the new data
            if 'summary' in updates:
                event['summary'] = updates['summary']
            if 'location' in updates:
                event['location'] = updates['location']
            if 'description' in updates:
                event['description'] = updates['description']
            if 'start' in updates:
                event['start']['dateTime'] = updates['start']
            if 'end' in updates:
                event['end']['dateTime'] = updates['end']
            if 'attendees' in updates:
                event['attendees'] = [{'email': email} for email in updates['attendees']]
            
            updated_event = self.service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event
            ).execute()
            
            logger.info(f"Event updated: {updated_event.get('htmlLink')}")
            return {
                'id': updated_event['id'],
                'link': updated_event.get('htmlLink')
            }
        except Exception as e:
            logger.error(f"Error updating Google calendar event: {str(e)}")
            raise
    
    async def delete_event(self, event_id: str, calendar_id: str = 'primary') -> bool:
        """Delete an event from the calendar"""
        if not self.service:
            await self.authenticate()
        
        # Remove the 'google_' prefix from calendar_id
        if calendar_id.startswith('google_'):
            calendar_id = calendar_id[7:]
        
        try:
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            logger.info(f"Event deleted: {event_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting Google calendar event: {str(e)}")
            raise
