import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json

import msal
import requests

logger = logging.getLogger(__name__)

class MicrosoftCalendarAPI:
    """Microsoft Graph API integration for Calendar access"""
    
    def __init__(self):
        self.app_id = os.getenv('MS_APP_ID', '')
        self.app_secret = os.getenv('MS_APP_SECRET', '')
        self.tenant_id = os.getenv('MS_TENANT_ID', 'common')
        self.scopes = ['Calendars.ReadWrite', 'Calendars.Read']
        self.redirect_uri = os.getenv('MS_REDIRECT_URI', 'http://localhost:5000/auth/microsoft/callback')
        self.token_file = 'credentials/microsoft_token.json'
        self.access_token = None
        self.app = None
    
    async def authenticate(self):
        """Authenticate with Microsoft Graph API"""
        # Initialize MSAL app
        self.app = msal.ConfidentialClientApplication(
            self.app_id,
            authority=f"https://login.microsoftonline.com/{self.tenant_id}",
            client_credential=self.app_secret,
        )
        
        # Check if token file exists
        if os.path.exists(self.token_file):
            with open(self.token_file, 'r') as token_file:
                token_data = json.load(token_file)
                if token_data.get('access_token'):
                    self.access_token = token_data['access_token']
                    # Check if token is valid by making a test request
                    if await self._test_token():
                        return True
        
        # If no valid token, we need to go through OAuth flow
        # This would typically be handled by the frontend
        logger.warning("No valid Microsoft token found. User needs to authenticate.")
        return False
    
    async def _test_token(self) -> bool:
        """Test if the access token is valid"""
        if not self.access_token:
            return False
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.get(
                'https://graph.microsoft.com/v1.0/me/calendars',
                headers=headers
            )
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Error testing Microsoft token: {str(e)}")
            return False
    
    async def get_auth_url(self) -> str:
        """Get the authorization URL for OAuth flow"""
        if not self.app:
            self.app = msal.ConfidentialClientApplication(
                self.app_id,
                authority=f"https://login.microsoftonline.com/{self.tenant_id}",
                client_credential=self.app_secret,
            )
        
        auth_url = self.app.get_authorization_request_url(
            self.scopes,
            redirect_uri=self.redirect_uri,
            state="12345"  # Should be a random state for security
        )
        
        return auth_url
    
    async def get_token_from_code(self, auth_code: str) -> bool:
        """Get access token from authorization code"""
        if not self.app:
            self.app = msal.ConfidentialClientApplication(
                self.app_id,
                authority=f"https://login.microsoftonline.com/{self.tenant_id}",
                client_credential=self.app_secret,
            )
        
        result = self.app.acquire_token_by_authorization_code(
            auth_code,
            scopes=self.scopes,
            redirect_uri=self.redirect_uri
        )
        
        if "access_token" in result:
            self.access_token = result["access_token"]
            
            # Save token to file
            os.makedirs(os.path.dirname(self.token_file), exist_ok=True)
            with open(self.token_file, 'w') as token_file:
                json.dump(result, token_file)
            
            return True
        else:
            logger.error(f"Error getting Microsoft token: {result.get('error')}")
            return False
    
    async def get_calendars(self) -> List[Dict[str, Any]]:
        """Get list of user's calendars"""
        if not self.access_token and not await self.authenticate():
            raise Exception("Not authenticated with Microsoft Graph API")
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        try:
            response = requests.get(
                'https://graph.microsoft.com/v1.0/me/calendars',
                headers=headers
            )
            
            if response.status_code != 200:
                logger.error(f"Error getting Microsoft calendars: {response.text}")
                raise Exception(f"Error getting Microsoft calendars: {response.status_code}")
            
            calendars_data = response.json()
            calendars = []
            
            for calendar in calendars_data.get('value', []):
                calendars.append({
                    'id': f"microsoft_{calendar['id']}",
                    'name': calendar['name'],
                    'provider': 'Microsoft',
                    'email': calendar.get('owner', {}).get('address', ''),
                    'color': calendar.get('color', '#0078D4')  # Default Microsoft blue
                })
            
            return calendars
        except Exception as e:
            logger.error(f"Error getting Microsoft calendars: {str(e)}")
            raise
    
    async def get_events(self, calendar_id: str, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get events from a calendar within a time range"""
        if not self.access_token and not await self.authenticate():
            raise Exception("Not authenticated with Microsoft Graph API")
        
        # Remove the 'microsoft_' prefix from calendar_id
        if calendar_id.startswith('microsoft_'):
            calendar_id = calendar_id[10:]
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json',
            'Prefer': 'outlook.timezone="UTC"'
        }
        
        # Format times for Microsoft Graph API
        start_time_str = start_time.isoformat() + 'Z'
        end_time_str = end_time.isoformat() + 'Z'
        
        try:
            url = f'https://graph.microsoft.com/v1.0/me/calendars/{calendar_id}/calendarView'
            params = {
                'startDateTime': start_time_str,
                'endDateTime': end_time_str,
                '$select': 'id,subject,start,end,location,body,attendees'
            }
            
            response = requests.get(url, headers=headers, params=params)
            
            if response.status_code != 200:
                logger.error(f"Error getting Microsoft calendar events: {response.text}")
                raise Exception(f"Error getting Microsoft calendar events: {response.status_code}")
            
            events_data = response.json()
            events = []
            
            for event in events_data.get('value', []):
                events.append({
                    'id': event['id'],
                    'summary': event['subject'],
                    'start': event['start']['dateTime'],
                    'end': event['end']['dateTime'],
                    'location': event.get('location', {}).get('displayName', ''),
                    'description': event.get('body', {}).get('content', ''),
                    'attendees': [attendee.get('emailAddress', {}).get('address') 
                                 for attendee in event.get('attendees', [])]
                })
            
            return events
        except Exception as e:
            logger.error(f"Error getting Microsoft calendar events: {str(e)}")
            raise
    
    async def create_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new event in the calendar"""
        if not self.access_token and not await self.authenticate():
            raise Exception("Not authenticated with Microsoft Graph API")
        
        # Extract calendar_id and remove the 'microsoft_' prefix
        calendar_id = event_data.pop('calendar_id', None)
        if calendar_id and calendar_id.startswith('microsoft_'):
            calendar_id = calendar_id[10:]
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        # Format the event for Microsoft Graph API
        event = {
            'subject': event_data.get('summary', 'New Event'),
            'body': {
                'contentType': 'HTML',
                'content': event_data.get('description', '')
            },
            'start': {
                'dateTime': event_data.get('start'),
                'timeZone': event_data.get('timeZone', 'UTC')
            },
            'end': {
                'dateTime': event_data.get('end'),
                'timeZone': event_data.get('timeZone', 'UTC')
            },
            'location': {
                'displayName': event_data.get('location', '')
            }
        }
        
        # Add attendees if provided
        if 'attendees' in event_data and event_data['attendees']:
            event['attendees'] = [
                {
                    'emailAddress': {
                        'address': email
                    },
                    'type': 'required'
                }
                for email in event_data['attendees']
            ]
        
        try:
            # If calendar_id is provided, create event in that calendar
            if calendar_id:
                url = f'https://graph.microsoft.com/v1.0/me/calendars/{calendar_id}/events'
            else:
                # Otherwise create in default calendar
                url = 'https://graph.microsoft.com/v1.0/me/events'
            
            response = requests.post(url, headers=headers, json=event)
            
            if response.status_code not in [200, 201]:
                logger.error(f"Error creating Microsoft calendar event: {response.text}")
                raise Exception(f"Error creating Microsoft calendar event: {response.status_code}")
            
            created_event = response.json()
            
            logger.info(f"Microsoft event created: {created_event.get('id')}")
            return {
                'id': created_event['id'],
                'link': created_event.get('webLink', '')
            }
        except Exception as e:
            logger.error(f"Error creating Microsoft calendar event: {str(e)}")
            raise
    
    async def update_event(self, event_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing event in the calendar"""
        if not self.access_token and not await self.authenticate():
            raise Exception("Not authenticated with Microsoft Graph API")
        
        # Extract calendar_id and remove the 'microsoft_' prefix
        calendar_id = updates.pop('calendar_id', None)
        if calendar_id and calendar_id.startswith('microsoft_'):
            calendar_id = calendar_id[10:]
        
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }
        
        # Prepare the update payload
        update_data = {}
        
        if 'summary' in updates:
            update_data['subject'] = updates['summary']
        
        if 'description' in updates:
            update_data['body'] = {
                'contentType': 'HTML',
                'content': updates['description']
            }
        
        if 'start' in updates:
            update_data['start'] = {
                'dateTime': updates['start'],
                'timeZone': updates.get('timeZone', 'UTC')
            }
        
        if 'end' in updates:
            update_data['end'] = {
                'dateTime': updates['end'],
                'timeZone': updates.get('timeZone', 'UTC')
            }
        
        if 'location' in updates:
            update_data['location'] = {
                'displayName': updates['location']
            }
        
        if 'attendees' in updates:
            update_data['attendees'] = [
                {
                    'emailAddress': {
                        'address': email
                    },
                    'type': 'required'
                }
                for email in updates['attendees']
            ]
        
        try:
            # If calendar_id is provided, update event in that calendar
            if calendar_id:
                url = f'https://graph.microsoft.com/v1.0/me/calendars/{calendar_id}/events/{event_id}'
            else:
                # Otherwise update in default calendar
                url = f'https://graph.microsoft.com/v1.0/me/events/{event_id}'
            
            response = requests.patch(url, headers=headers, json=update_data)
            
            if response.status_code != 200:
                logger.error(f"Error updating Microsoft calendar event: {response.text}")
                raise Exception(f"Error updating Microsoft calendar event: {response.status_code}")
            
            updated_event = response.json()
            
            logger.info(f"Microsoft event updated: {updated_event.get('id')}")
            return {
                'id': updated_event['id'],
                'link': updated_event.get('webLink', '')
            }
        except Exception as e:
            logger.error(f"Error updating Microsoft calendar event: {str(e)}")
            raise
    
    async def delete_event(self, event_id: str, calendar_id: str = None) -> bool:
        """Delete an event from the calendar"""
        if not self.access_token and not await self.authenticate():
            raise Exception("Not authenticated with Microsoft Graph API")
        
        # Remove the 'microsoft_' prefix from calendar_id
        if calendar_id and calendar_id.startswith('microsoft_'):
            calendar_id = calendar_id[10:]
        
        headers = {
            'Authorization': f'Bearer {self.access_token}'
        }
        
        try:
            # If calendar_id is provided, delete event from that calendar
            if calendar_id:
                url = f'https://graph.microsoft.com/v1.0/me/calendars/{calendar_id}/events/{event_id}'
            else:
                # Otherwise delete from default calendar
                url = f'https://graph.microsoft.com/v1.0/me/events/{event_id}'
            
            response = requests.delete(url, headers=headers)
            
            if response.status_code not in [200, 204]:
                logger.error(f"Error deleting Microsoft calendar event: {response.text}")
                raise Exception(f"Error deleting Microsoft calendar event: {response.status_code}")
            
            logger.info(f"Microsoft event deleted: {event_id}")
            return True
        except Exception as e:
            logger.error(f"Error deleting Microsoft calendar event: {str(e)}")
            raise
