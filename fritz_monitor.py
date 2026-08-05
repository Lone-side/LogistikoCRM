# -*- coding: utf-8 -*-
"""
fritz_monitor.py - PRODUCTION VERSION
Author: ddiplas
Version: 3.5 - Fixed DISCONNECT event parsing
Date: 2025-12-06

FIXES:
- Proper timezone-aware datetime handling
- Smart ticket creation (only for missed calls)
- Extended timeout with retry logic
- API Key authentication via X-API-Key header
- Now loads FRITZ_API_TOKEN from .env file (same as Django)
- Fixed parsing of DISCONNECT events (different format than RING/CALL)
"""

import socket
import re
import logging
import requests
import json
from datetime import datetime, timezone as dt_timezone
from typing import Optional, Dict, Any
import time
import os

# ============================================
# ENVIRONMENT LOADING - Must be BEFORE any os.environ.get()
# ============================================
from dotenv import load_dotenv

# Load .env file from project root
_dotenv_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
_dotenv_loaded = load_dotenv(_dotenv_path)

# ============================================
# LOGGING CONFIGURATION
# ============================================
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# ============================================
# CONFIGURATION
# ============================================
_DEFAULT_TOKEN = 'change-this-token-in-production'

class Config:
    # Fritz!Box
    FRITZ_HOST = 'fritz.box'
    FRITZ_PORT = 1012

    # CRM API
    CRM_BASE_URL = 'http://127.0.0.1:8000/accounting/api'
    # API Key for authentication with CRM API
    # Set via environment variable or .env file: FRITZ_API_TOKEN=your-secret-key
    FRITZ_API_TOKEN = os.environ.get('FRITZ_API_TOKEN', _DEFAULT_TOKEN)

    @classmethod
    def log_token_status(cls):
        """Log API token configuration status at startup"""
        if cls.FRITZ_API_TOKEN == _DEFAULT_TOKEN:
            logger.warning("⚠️  SECURITY: Using DEFAULT API token! Set FRITZ_API_TOKEN in .env file")
            logger.warning("⚠️  Create .env file with: FRITZ_API_TOKEN=your-secure-random-token")
        else:
            # Κανένα τμήμα του token στα logs
            if _dotenv_loaded:
                logger.info("✅ API token loaded from .env file")
            else:
                logger.info("✅ API token loaded from environment")

    # Timeouts & Retries
    API_TIMEOUT = 30
    API_MAX_RETRIES = 3
    RETRY_DELAY = 2

    # Statistics
    STATS_INTERVAL = 600

# ============================================
# HELPER FUNCTIONS
# ============================================
def get_now() -> datetime:
    """Get current timezone-aware datetime in UTC"""
    return datetime.now(dt_timezone.utc)

def format_datetime(dt: datetime) -> str:
    """Format datetime as ISO string with timezone"""
    return dt.isoformat()

# ============================================
# API CLIENT με RETRY LOGIC
# ============================================
class CRMAPIClient:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'X-API-Key': Config.FRITZ_API_TOKEN,
        })
        
        self.stats = {
            'total_calls': 0,
            'answered': 0,
            'missed': 0,
            'outgoing': 0,
            'errors': 0,
            'tickets_created': 0,
            'start_time': get_now(),
            'last_call_time': None,
            'active_calls': 0
        }
    
    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None, 
                     retries: int = Config.API_MAX_RETRIES) -> Optional[Dict]:
        """Make API request with retry logic"""
        url = f"{Config.CRM_BASE_URL}/{endpoint}"
        
        for attempt in range(retries):
            try:
                if method == 'POST':
                    response = self.session.post(url, json=data, timeout=Config.API_TIMEOUT)
                elif method == 'PATCH':
                    response = self.session.patch(url, json=data, timeout=Config.API_TIMEOUT)
                elif method == 'GET':
                    response = self.session.get(url, timeout=Config.API_TIMEOUT)
                else:
                    raise ValueError(f"Unsupported method: {method}")
                
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.Timeout:
                logger.warning(f"⏰ Timeout on attempt {attempt + 1}/{retries}")
                if attempt < retries - 1:
                    time.sleep(Config.RETRY_DELAY)
                    continue
                logger.error(f"❌ Failed after {retries} attempts: Timeout")
                self.stats['errors'] += 1
                return None
                
            except requests.exceptions.RequestException as e:
                logger.error(f"❌ Request failed: {e}")
                if attempt < retries - 1:
                    time.sleep(Config.RETRY_DELAY)
                    continue
                self.stats['errors'] += 1
                return None
        
        return None
    
    def create_call(self, call_data: Dict) -> Optional[Dict]:
        """Create new call record"""
        result = self._make_request('POST', 'voip-calls/', call_data)
        if result:
            logger.info(f"✅ Call created in CRM: #{result.get('id')} - {result.get('client_name', 'Unknown')}")
        else:
            logger.error(f"❌ Failed to create call in CRM")
            logger.error(f"Payload: {call_data}")
        return result
    
    def update_call(self, call_id: str, update_data: Dict) -> Optional[Dict]:
        """Update existing call record"""
        result = self._make_request('PATCH', f'voip-calls/{call_id}/', update_data)
        if result:
            logger.info(f"✅ Call updated in CRM: #{call_id} → {update_data.get('status')}")
            if update_data.get('create_ticket'):
                self.stats['tickets_created'] += 1
                logger.info(f"🎫 Smart ticket will be created for follow-up")
        else:
            logger.error(f"❌ Failed to update call status")
            logger.error(f"Payload: {update_data}")
        return result
    
    def print_stats(self):
        """Print current statistics"""
        uptime = get_now() - self.stats['start_time']
        hours, remainder = divmod(int(uptime.total_seconds()), 3600)
        minutes, _ = divmod(remainder, 60)
        
        last_call = "Never"
        if self.stats['last_call_time']:
            delta = get_now() - self.stats['last_call_time']
            last_call = f"{int(delta.total_seconds())}s ago"
        
        logger.info("=" * 60)
        logger.info(f"📊 STATISTICS - Uptime: {hours}h {minutes}m")
        logger.info(f"Total Calls: {self.stats['total_calls']}")
        logger.info(f"  ✅ Answered: {self.stats['answered']}")
        logger.info(f"  ❌ Missed: {self.stats['missed']}")
        logger.info(f"  ☎️ Outgoing: {self.stats['outgoing']}")
        logger.info(f"Active Calls: {self.stats['active_calls']}")
        logger.info(f"🎫 Tickets Created: {self.stats['tickets_created']}")
        logger.info(f"CRM Errors: {self.stats['errors']}")
        logger.info(f"Last Call: {last_call}")
        logger.info("=" * 60)

# ============================================
# VOIP MONITOR
# ============================================
class VoIPMonitor:
    def __init__(self):
        self.api = CRMAPIClient()
        self.active_calls = {}
        self.last_stats_time = get_now()
    
    def connect_fritz(self) -> socket.socket:
        """Connect to Fritz!Box CallMonitor"""
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((Config.FRITZ_HOST, Config.FRITZ_PORT))
        logger.info(f"✅ Connected to Fritz!Box at {Config.FRITZ_HOST}:{Config.FRITZ_PORT}")
        return sock
    
    def parse_call_event(self, line: str) -> Optional[dict]:
        """
        Parse Fritz!Box call event.

        Fritz!Box CallMonitor formats:
        - RING:       timestamp;RING;connId;caller;called;lineId;
        - CALL:       timestamp;CALL;connId;extension;called;lineId;
        - CONNECT:    timestamp;CONNECT;connId;extension;number;
        - DISCONNECT: timestamp;DISCONNECT;connId;duration;
        """
        parts = line.strip().rstrip(';').split(';')

        if len(parts) < 4:
            return None

        timestamp, event, connection_id = parts[0], parts[1], parts[2]

        if event == 'RING':
            # RING: timestamp;RING;connId;caller;called;lineId
            if len(parts) >= 5:
                return {'event': event, 'connection_id': connection_id, 'caller': parts[3], 'called': parts[4]}

        elif event == 'CALL':
            # CALL: timestamp;CALL;connId;extension;called;lineId
            if len(parts) >= 5:
                return {'event': event, 'connection_id': connection_id, 'caller': parts[3], 'called': parts[4]}

        elif event == 'CONNECT':
            # CONNECT: timestamp;CONNECT;connId;extension;number
            return {'event': event, 'connection_id': connection_id}

        elif event == 'DISCONNECT':
            # DISCONNECT: timestamp;DISCONNECT;connId;duration
            duration = int(parts[3]) if len(parts) > 3 and parts[3].isdigit() else 0
            return {'event': event, 'connection_id': connection_id, 'duration': duration}

        logger.debug(f"Unknown event format: {line}")
        return None
    
    def generate_call_id(self, connection_id: str) -> str:
        """Generate unique call_id with timestamp"""
        timestamp = int(get_now().timestamp())
        return f"{connection_id}_{timestamp}"
    
    def handle_ring(self, connection_id: str, caller: str, called: str):
        """Handle incoming call ring"""
        logger.info(f"📞 INCOMING RING: {caller} → {called}")
        
        now = get_now()
        call_id = self.generate_call_id(connection_id)
        call_data = {
            'call_id': call_id,
            'phone_number': caller,
            'direction': 'incoming',
            'status': 'active',
            'started_at': format_datetime(now)  # ← Timezone-aware!
        }
        
        result = self.api.create_call(call_data)
        if result:
            self.active_calls[connection_id] = {
                'id': result.get('id'),
                'call_id': call_id,
                'phone_number': caller,
                'client_name': result.get('client_name', 'Unknown'),
                'direction': 'incoming',
                'started_at': now,  # Store as datetime object
                'status': 'active'
            }
            self.api.stats['total_calls'] += 1
            self.api.stats['active_calls'] += 1
            self.api.stats['last_call_time'] = now
            
            logger.info(f"NEW|{caller}|{self.active_calls[connection_id]['client_name']}|incoming|active")
            
            # Print stats every 10 minutes
            if (get_now() - self.last_stats_time).total_seconds() >= Config.STATS_INTERVAL:
                self.api.print_stats()
                self.last_stats_time = get_now()
    
    def handle_connect(self, connection_id: str):
        """Handle call answered"""
        if connection_id in self.active_calls:
            call = self.active_calls[connection_id]
            update_data = {
                'status': 'completed'
            }
            self.api.update_call(call['id'], update_data)
            call['status'] = 'completed'
            self.api.stats['answered'] += 1
            logger.info(f"✅ CALL CONNECTED: {call['phone_number']}")
    
    def handle_disconnect(self, connection_id: str):
        """Handle call ended - Smart ticket creation"""
        if connection_id not in self.active_calls:
            return
        
        call = self.active_calls[connection_id]
        now = get_now()
        duration = int((now - call['started_at']).total_seconds())
        
        # CRITICAL: Only create ticket if call was MISSED
        if call['status'] == 'active':
            # Call was never answered → MISSED
            update_data = {
                'status': 'missed',
                'create_ticket': True,  # ✅ Χρειάζεται follow-up!
                'ended_at': format_datetime(now)  # ← Timezone-aware!
            }
            self.api.update_call(call['id'], update_data)
            self.api.stats['missed'] += 1
            logger.warning(f"❌ Call MISSED: {call['phone_number']} (rang {duration}s)")
            logger.info(f"END|{call['phone_number']}|MISSED|{duration}s|{call['direction']}")
        
        else:
            # Call was answered → COMPLETED
            update_data = {
                'status': 'completed',
                'create_ticket': False,  # ✅ Λύθηκε στο τηλέφωνο!
                'ended_at': format_datetime(now)  # ← Timezone-aware!
            }
            self.api.update_call(call['id'], update_data)
            logger.info(f"✅ Call COMPLETED: {call['phone_number']} (duration: {duration}s)")
            logger.info(f"✅ No ticket needed - issue resolved on call")
            logger.info(f"END|{call['phone_number']}|COMPLETED|{duration}s|{call['direction']}")
        
        self.api.stats['active_calls'] -= 1
        del self.active_calls[connection_id]
    
    def handle_outgoing_call(self, connection_id: str, called: str):
        """Handle outgoing call"""
        logger.info(f"📞 OUTGOING CALL: → {called}")
        
        now = get_now()
        call_id = self.generate_call_id(connection_id)
        call_data = {
            'call_id': call_id,
            'phone_number': called,
            'direction': 'outgoing',
            'status': 'active',
            'started_at': format_datetime(now)  # ← Timezone-aware!
        }
        
        result = self.api.create_call(call_data)
        if result:
            self.active_calls[connection_id] = {
                'id': result.get('id'),
                'call_id': call_id,
                'phone_number': called,
                'client_name': result.get('client_name', 'Unknown'),
                'direction': 'outgoing',
                'started_at': now,  # Store as datetime object
                'status': 'active'
            }
            self.api.stats['total_calls'] += 1
            self.api.stats['outgoing'] += 1
            self.api.stats['active_calls'] += 1
            self.api.stats['last_call_time'] = now
            logger.info(f"NEW|{called}|{self.active_calls[connection_id]['client_name']}|outgoing|active")
    
    def run(self):
        """Main monitoring loop"""
        logger.info("=" * 60)
        logger.info("🚀 Fritz!Box VoIP Monitor - PRODUCTION v3.5")
        logger.info(f"Fritz: {Config.FRITZ_HOST}:{Config.FRITZ_PORT}")
        logger.info(f"CRM: {Config.CRM_BASE_URL}/voip-calls/")
        logger.info(f"🔐 API Auth: X-API-Key header enabled")
        Config.log_token_status()  # Show token configuration status
        logger.info(f"🎫 Smart Tickets: Only for MISSED calls")
        logger.info(f"⏰ Timezone: UTC (timezone-aware)")
        logger.info("=" * 60)
        
        while True:
            try:
                logger.info("🚀 Starting VoIP Monitor...")
                sock = self.connect_fritz()
                
                while True:
                    data = sock.recv(1024).decode('utf-8').strip()
                    if not data:
                        continue

                    parsed = self.parse_call_event(data)
                    if not parsed:
                        continue

                    event = parsed['event']
                    connection_id = parsed['connection_id']

                    if event == 'RING':
                        self.handle_ring(connection_id, parsed['caller'], parsed['called'])
                    elif event == 'CALL':
                        self.handle_outgoing_call(connection_id, parsed['called'])
                    elif event == 'CONNECT':
                        self.handle_connect(connection_id)
                    elif event == 'DISCONNECT':
                        self.handle_disconnect(connection_id)
            
            except KeyboardInterrupt:
                logger.info("\n👋 Shutting down gracefully...")
                self.api.print_stats()
                break
            except Exception as e:
                logger.error(f"❌ Error: {e}")
                logger.info("🔄 Reconnecting in 5 seconds...")
                time.sleep(5)

# ============================================
# MAIN
# ============================================
if __name__ == '__main__':
    monitor = VoIPMonitor()
    monitor.run()