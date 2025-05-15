import os
import logging
import json
import requests
from datetime import datetime
from app import db
from models import Transaction, ErrorLog, ApiConfig

logger = logging.getLogger(__name__)

class ClioService:
    """Service for interacting with Clio API"""
    
    def __init__(self):
        self.base_url = None
        self.api_key = None
        self.api_secret = None
        self.access_token = None
        self._load_config()
    
    def _load_config(self):
        """Load Clio configuration from database"""
        try:
            config = ApiConfig.query.filter_by(service='clio').first()
            if config:
                self.base_url = config.base_url or 'https://app.clio.com/api/v4/'
                self.api_key = config.api_key
                self.api_secret = config.api_secret
                self.access_token = config.oauth_token
            else:
                # Set defaults if no config found
                self.base_url = 'https://app.clio.com/api/v4/'
                self.api_key = os.environ.get('CLIO_API_KEY')
                self.api_secret = os.environ.get('CLIO_API_SECRET')
                self.access_token = os.environ.get('CLIO_ACCESS_TOKEN')
        except Exception as e:
            logger.error(f"Error loading Clio configuration: {str(e)}")
            # Set defaults on error
            self.base_url = 'https://app.clio.com/api/v4/'
            self.api_key = os.environ.get('CLIO_API_KEY')
            self.api_secret = os.environ.get('CLIO_API_SECRET')
            self.access_token = os.environ.get('CLIO_ACCESS_TOKEN')
    
    def _get_headers(self):
        """Get API request headers"""
        if self.access_token:
            return {
                'Authorization': f'Bearer {self.access_token}',
                'Content-Type': 'application/json'
            }
        else:
            return {
                'Content-Type': 'application/json'
            }
    
    def _log_transaction(self, source, destination, method, url, request_headers, request_body, 
                        response_status, response_headers, response_body, duration_ms, success):
        """Log API transaction to the database"""
        try:
            # Create transaction record
            transaction = Transaction(
                source=source,
                destination=destination,
                request_method=method,
                request_url=url,
                request_headers=request_headers,
                request_body=request_body,
                response_status=response_status,
                response_headers=response_headers,
                response_body=response_body,
                duration_ms=duration_ms,
                success=success,
                created_at=datetime.now()
            )
            db.session.add(transaction)
            db.session.commit()
            return transaction.id
        except Exception as e:
            logger.error(f"Error logging transaction: {str(e)}", exc_info=True)
            db.session.rollback()
            return None
    
    def _log_error(self, transaction_id, error_type, error_message, error_details=None):
        """Log error to the database"""
        try:
            error_log = ErrorLog(
                transaction_id=transaction_id,
                error_type=error_type,
                error_message=error_message,
                error_details=error_details,
                created_at=datetime.now()
            )
            db.session.add(error_log)
            db.session.commit()
        except Exception as e:
            logger.error(f"Error logging error: {str(e)}", exc_info=True)
            db.session.rollback()
    
    def make_request(self, method, endpoint, data=None, params=None):
        """Make a request to the Clio API"""
        self._load_config()  # Reload config before each request
        
        if not self.access_token and not (self.api_key and self.api_secret):
            error_message = "Clio API credentials not configured"
            logger.error(error_message)
            transaction_id = self._log_transaction(
                'internal', 'clio', method, f"{self.base_url}{endpoint}",
                {}, data, None, {}, {"error": error_message}, 0, False
            )
            self._log_error(transaction_id, "Configuration Error", error_message)
            raise ValueError(error_message)
        
        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers()
        
        # Convert data to JSON string if it's a dict
        request_body = json.dumps(data) if data and isinstance(data, dict) else data
        
        start_time = datetime.now()
        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, params=params)
            elif method.upper() == 'POST':
                response = requests.post(url, headers=headers, json=data, params=params)
            elif method.upper() == 'PUT':
                response = requests.put(url, headers=headers, json=data, params=params)
            elif method.upper() == 'PATCH':
                response = requests.patch(url, headers=headers, json=data, params=params)
            elif method.upper() == 'DELETE':
                response = requests.delete(url, headers=headers, params=params)
            else:
                error_message = f"Unsupported HTTP method: {method}"
                logger.error(error_message)
                transaction_id = self._log_transaction(
                    'internal', 'clio', method, url,
                    headers, request_body, None, {}, {"error": error_message}, 0, False
                )
                self._log_error(transaction_id, "Request Error", error_message)
                raise ValueError(error_message)
            
            # Calculate request duration
            end_time = datetime.now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            # Extract response data
            try:
                response_body = response.json()
            except ValueError:
                response_body = {"text": response.text}
            
            # Determine success based on status code
            success = 200 <= response.status_code < 300
            
            # Convert headers to dict for storage
            response_headers_dict = dict(response.headers)
            request_headers_dict = dict(headers)
            
            # Log transaction
            transaction_id = self._log_transaction(
                'internal', 'clio', method, url,
                request_headers_dict, data, response.status_code, response_headers_dict, 
                response_body, duration_ms, success
            )
            
            # Log error if request failed
            if not success:
                error_message = f"Clio API request failed: {response.status_code} - {response.text}"
                self._log_error(
                    transaction_id, 
                    "API Response Error", 
                    error_message,
                    {"status_code": response.status_code, "response": response_body}
                )
                logger.error(error_message)
            
            return {
                'success': success,
                'status_code': response.status_code,
                'data': response_body,
                'headers': response_headers_dict
            }
        
        except requests.exceptions.RequestException as e:
            # Calculate duration for failed requests
            end_time = datetime.now()
            duration_ms = int((end_time - start_time).total_seconds() * 1000)
            
            error_message = f"Clio API request exception: {str(e)}"
            logger.error(error_message, exc_info=True)
            
            # Log transaction
            transaction_id = self._log_transaction(
                'internal', 'clio', method, url,
                headers, request_body, None, {}, {"error": str(e)}, duration_ms, False
            )
            
            # Log error
            self._log_error(
                transaction_id,
                "Request Exception",
                error_message,
                {"exception_type": type(e).__name__}
            )
            
            return {
                'success': False,
                'status_code': None,
                'data': {"error": str(e)},
                'headers': {}
            }
    
    def test_connection(self):
        """Test connection to Clio API"""
        try:
            response = self.make_request('GET', 'users/who_am_i')
            if response['success']:
                return {'success': True, 'message': 'Connection successful'}
            else:
                return {
                    'success': False, 
                    'message': f"Connection failed: {response['status_code']} - {response['data'].get('message', 'Unknown error')}"
                }
        except Exception as e:
            error_message = f"Error testing Clio connection: {str(e)}"
            logger.error(error_message, exc_info=True)
            return {'success': False, 'message': error_message}
    
    def get_contacts(self, params=None):
        """Get contacts from Clio"""
        endpoint = "contacts"
        return self.make_request('GET', endpoint, params=params)
    
    def get_contact(self, contact_id):
        """Get a specific contact from Clio"""
        endpoint = f"contacts/{contact_id}"
        return self.make_request('GET', endpoint)
    
    def create_contact(self, contact_data):
        """Create a new contact in Clio"""
        endpoint = "contacts"
        return self.make_request('POST', endpoint, data=contact_data)
    
    def update_contact(self, contact_id, contact_data):
        """Update an existing contact in Clio"""
        endpoint = f"contacts/{contact_id}"
        return self.make_request('PATCH', endpoint, data=contact_data)
    
    def create_matter(self, matter_data):
        """Create a new matter in Clio"""
        endpoint = "matters"
        return self.make_request('POST', endpoint, data=matter_data)
    
    def create_task(self, task_data):
        """Create a new task in Clio"""
        endpoint = "tasks"
        return self.make_request('POST', endpoint, data=task_data)
    
    def create_note(self, note_data):
        """Create a new note in Clio"""
        endpoint = "notes"
        return self.make_request('POST', endpoint, data=note_data)
    
    def process_webhook(self, webhook_data):
        """Process incoming webhook data from Clio"""
        try:
            # Extract event type and resource details from webhook
            event_type = webhook_data.get('type', '')
            resource = webhook_data.get('data', {})
            
            logger.info(f"Processing Clio webhook: {event_type}")
            
            # Log webhook receipt as transaction
            transaction_id = self._log_transaction(
                'clio', 'internal', 'POST', 'webhook/clio',
                {}, webhook_data, 200, {}, {"status": "received"}, 0, True
            )
            
            return {
                'success': True,
                'event_type': event_type,
                'resource': resource,
                'transaction_id': transaction_id
            }
        
        except Exception as e:
            error_message = f"Error processing Clio webhook: {str(e)}"
            logger.error(error_message, exc_info=True)
            
            # Log error
            transaction_id = self._log_transaction(
                'clio', 'internal', 'POST', 'webhook/clio',
                {}, webhook_data, 500, {}, {"error": str(e)}, 0, False
            )
            
            self._log_error(
                transaction_id,
                "Webhook Processing Error",
                error_message,
                {"webhook_data": webhook_data}
            )
            
            return {
                'success': False,
                'error': str(e),
                'transaction_id': transaction_id
            }
