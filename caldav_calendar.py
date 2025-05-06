import os
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import json
import uuid

import caldav
from caldav.elements import dav, cdav

logger = logging.getLogger(__name__)

class CalDAVCalendarAPI:
    """CalDAV protocol integration for Apple Calendar and other CalDAV servers"""
    
    def __init__(self):
        self.credentials_file = 'credentials/caldav_credentials.json'
        self.client = None
        self.principal = None
    
    async def authenticate(self, url: str = None, username: str = None, password: str = None) -> bool:
        """Authenticate with CalDAV server"""
        # If credentials are provided, use them
        if url and username and password:
            try:
                self.client = caldav.DAVClient(
                    url=url,
                    username=username,
                    password=password
                )
                self.principal = self.client.principal()
                
                # Save credentials to file
                os.makedirs(os.path.dirname(self.credentials_file), exist_ok=True)
                with open(self.credentials_file, 'w') as f:
                    json.dump({
                        'url': url,
                        'username': username,
                        # In a real app, we would encrypt the password
                        'password': password
                    }, f)
                
                return True
            except Exception as e:
                logger.error(f"Error authenticating with CalDAV server: {str(e)}")
                return False
        
        # Otherwise, try to load credentials from file
        if os.path.exists(self.credentials_file):
            try:
                with open(self.credentials_file, 'r') as f:
                    credentials = json.load(f)
                
                self.client = caldav.DAVClient(
                    url=credentials['url'],
                    username=credentials['username'],
                    password=credentials['password']
                )
                self.principal = self.client.principal()
                
                return True
            except Exception as e:
                logger.error(f"Error loading CalDAV credentials: {str(e)}")
                return False
        
        return False
    
    async def get_calendars(self) -> List[Dict[str, Any]]:
        """Get list of user's calendars"""
        if not self.client:
            if not await self.authenticate():
                raise Exception("Not authenticated with CalDAV server")
        
        try:
            calendars = self.principal.calendars()
            result = []
            
            for calendar in calendars:
                # Generate a unique ID for the calendar
                calendar_id = f"caldav_{uuid.uuid4().hex}"
                
                # Try to get calendar properties
                try:
                    display_name = calendar.get_properties([dav.DisplayName()])['{DAV:}displayname']
                except:
                    display_name = "Calendar"
                
                result.append({
                    'id': calendar_id,
                    'name': display_name,
                    'provider': 'CalDAV',
                    'url': calendar.url,
                    'color': '#FF9500'  # Default Apple Calendar orange
                })
            
            return result
        except Exception as e:
            logger.error(f"Error getting CalDAV calendars: {str(e)}")
            raise
    
    async def get_events(self, calendar_url: str, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """Get events from a calendar within a time range"""
        if not self.client:
            if not await self.authenticate():
                raise Exception("Not authenticated with CalDAV server")
        
        try:
            # Get the calendar by URL
            calendar = self.client.calendar(url=calendar_url)
            
            # Get events in the time range
            events = calendar.date_search(
                start=start_time,
                end=end_time,
                expand=True
            )
            
            result = []
            for event in events:
                event_data = event.data
                ical_data = event.icalendar_component
                
                # Extract event details from iCalendar data
                summary = str(ical_data.get('summary', 'No Title'))
                description = str(ical_data.get('description', ''))
                location = str(ical_data.get('location', ''))
                
                # Get start and end times
                dtstart = ical_data.get('dtstart')
                dtend = ical_data.get('dtend')
                
                if dtstart and dtend:
                    start_dt = dtstart.dt
                    end_dt = dtend.dt
                    
                    # Convert to string format
                    if hasattr(start_dt, 'isoformat'):
                        start_str = start_dt.isoformat()
                        end_str = end_dt.isoformat()
                    else:
                        # All-day event
                        start_str = start_dt.isoformat()
                        end_str = end_dt.isoformat()
                else:
                    # Default values if no start/end found
                    start_str = datetime.now().isoformat()
                    end_str = (datetime.now() + timedelta(hours=1)).isoformat()
                
                # Get attendees
                attendees = []
                for attendee in ical_data.get('attendee', []):
                    if hasattr(attendee, 'params') and 'EMAIL' in attendee.params:
                        attendees.append(attendee.params['EMAIL'])
                    elif hasattr(attendee, 'value'):
                        # Extract email from mailto: URI
                        email = attendee.value
                        if email.startswith('mailto:'):
                            email = email[7:]
                        attendees.append(email)
                
                result.append({
                    'id': event.id,
                    'summary': summary,
                    'description': description,
                    'location': location,
                    'start': start_str,
                    'end': end_str,
                    'attendees': attendees,
                    'url': event.url
                })
            
            return result
        except Exception as e:
            logger.error(f"Error getting CalDAV events: {str(e)}")
            raise
    
    async def create_event(self, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new event in the calendar"""
        if not self.client:
            if not await self.authenticate():
                raise Exception("Not authenticated with CalDAV server")
        
        try:
            # Get the calendar URL from event data
            calendar_url = event_data.get('calendar_url')
            if not calendar_url:
                raise Exception("Calendar URL is required")
            
            # Get the calendar by URL
            calendar = self.client.calendar(url=calendar_url)
            
            # Create iCalendar component
            ical_data = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Calendar AI Agent//EN
BEGIN:VEVENT
UID:{uuid.uuid4()}
DTSTAMP:{datetime.now().strftime('%Y%m%dT%H%M%SZ')}
DTSTART:{event_data.get('start').replace('-', '').replace(':', '')}
DTEND:{event_data.get('end').replace('-', '').replace(':', '')}
SUMMARY:{event_data.get('summary', 'New Event')}
DESCRIPTION:{event_data.get('description', '')}
LOCATION:{event_data.get('location', '')}"""
            
            # Add attendees if provided
            if 'attendees' in event_data and event_data['attendees']:
                for attendee in event_data['attendees']:
                    ical_data += f"\nATTENDEE;ROLE=REQ-PARTICIPANT;PARTSTAT=NEEDS-ACTION;RSVP=TRUE:mailto:{attendee}"
            
            ical_data += """\nEND:VEVENT
END:VCALENDAR"""
            
            # Create the event
            event = calendar.save_event(ical_data)
            
            logger.info(f"CalDAV event created: {event.id}")
            return {
                'id': event.id,
                'url': event.url
            }
        except Exception as e:
            logger.error(f"Error creating CalDAV event: {str(e)}")
            raise
    
    async def update_event(self, event_url: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing event in the calendar"""
        if not self.client:
            if not await self.authenticate():
                raise Exception("Not authenticated with CalDAV server")
        
        try:
            # Get the event by URL
            event = self.client.event(url=event_url)
            
            # Get current event data
            ical_data = event.icalendar_component
            
            # Update event properties
            if 'summary' in updates:
                ical_data['summary'] = updates['summary']
            
            if 'description' in updates:
                ical_data['description'] = updates['description']
            
            if 'location' in updates:
                ical_data['location'] = updates['location']
            
            if 'start' in updates:
                start_dt = datetime.fromisoformat(updates['start'].replace('Z', '+00:00'))
                ical_data['dtstart'].dt = start_dt
            
            if 'end' in updates:
                end_dt = datetime.fromisoformat(updates['end'].replace('Z', '+00:00'))
                ical_data['dtend'].dt = end_dt
            
            # Update attendees if provided
            if 'attendees' in updates:
                # Remove existing attendees
                if 'attendee' in ical_data:
                    del ical_data['attendee']
                
                # Add new attendees
                for attendee in updates['attendees']:
                    ical_data.add('attendee', f"mailto:{attendee}")
            
            # Save the updated event
            event.icalendar_component = ical_data
            event.save()
            
            logger.info(f"CalDAV event updated: {event.id}")
            return {
                'id': event.id,
                'url': event.url
            }
        except Exception as e:
            logger.error(f"Error updating CalDAV event: {str(e)}")
            raise
    
    async def delete_event(self, event_url: str) -> bool:
        """Delete an event from the calendar"""
        if not self.client:
            if not await self.authenticate():
                raise Exception("Not authenticated with CalDAV server")
        
        try:
            # Get the event by URL
            event = self.client.event(url=event_url)
            
            # Delete the event
            event.delete()
            
            logger.info(f"CalDAV event deleted: {event_url}")
            return True
        except Exception as e:
            logger.error(f"Error deleting CalDAV event: {str(e)}")
            raise
