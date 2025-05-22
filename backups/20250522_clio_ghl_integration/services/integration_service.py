import logging
import json
from datetime import datetime
from app import db
from models import Transaction, ErrorLog, DataMapping

logger = logging.getLogger(__name__)

class IntegrationService:
    """Service for integrating GHL and Clio data"""
    
    def __init__(self, ghl_service, clio_service):
        self.ghl_service = ghl_service
        self.clio_service = clio_service
    
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
    
    def _get_field_mappings(self, mapping_type='direct'):
        """Get field mappings from database"""
        try:
            mappings = DataMapping.query.filter_by(
                is_active=True, 
                mapping_type=mapping_type
            ).all()
            
            mapping_dict = {}
            for mapping in mappings:
                mapping_dict[mapping.ghl_field] = mapping.clio_field
            
            return mapping_dict
        except Exception as e:
            logger.error(f"Error getting field mappings: {str(e)}", exc_info=True)
            return {}
    
    def _map_ghl_to_clio_contact(self, ghl_contact):
        """Map GHL contact data to Clio contact format"""
        try:
            # Get field mappings
            direct_mappings = self._get_field_mappings('direct')
            
            # Start with basic mapping structure for Clio
            clio_contact = {
                "data": {
                    "type": "contacts",
                    "attributes": {}
                }
            }
            
            # Apply direct field mappings
            for ghl_field, clio_field in direct_mappings.items():
                if ghl_field in ghl_contact and ghl_contact[ghl_field] is not None:
                    clio_contact["data"]["attributes"][clio_field] = ghl_contact[ghl_field]
            
            # Handle special mappings
            # Name fields
            if 'firstName' in ghl_contact:
                clio_contact["data"]["attributes"]["first_name"] = ghl_contact["firstName"]
            if 'lastName' in ghl_contact:
                clio_contact["data"]["attributes"]["last_name"] = ghl_contact["lastName"]
            
            # Email fields
            if 'email' in ghl_contact and ghl_contact['email']:
                clio_contact["data"]["attributes"]["emails"] = [
                    {
                        "name": "Primary",
                        "address": ghl_contact["email"]
                    }
                ]
            
            # Phone fields
            if 'phone' in ghl_contact and ghl_contact['phone']:
                clio_contact["data"]["attributes"]["phone_numbers"] = [
                    {
                        "name": "Primary",
                        "number": ghl_contact["phone"]
                    }
                ]
            
            return clio_contact
        except Exception as e:
            logger.error(f"Error mapping GHL to Clio contact: {str(e)}", exc_info=True)
            return None
    
    def _map_clio_to_ghl_contact(self, clio_contact):
        """Map Clio contact data to GHL contact format"""
        try:
            # Extract data from Clio's nested structure
            if 'data' in clio_contact:
                contact_data = clio_contact['data']
                attributes = contact_data.get('attributes', {})
            else:
                attributes = clio_contact
            
            # Start with basic mapping structure for GHL
            ghl_contact = {}
            
            # Map basic fields
            ghl_contact["firstName"] = attributes.get("first_name", "")
            ghl_contact["lastName"] = attributes.get("last_name", "")
            
            # Map email addresses
            emails = attributes.get("emails", [])
            if emails and len(emails) > 0:
                ghl_contact["email"] = emails[0].get("address", "")
            
            # Map phone numbers
            phone_numbers = attributes.get("phone_numbers", [])
            if phone_numbers and len(phone_numbers) > 0:
                ghl_contact["phone"] = phone_numbers[0].get("number", "")
            
            # Map address if available
            addresses = attributes.get("addresses", [])
            if addresses and len(addresses) > 0:
                address = addresses[0]
                ghl_contact["address1"] = address.get("street", "")
                ghl_contact["city"] = address.get("city", "")
                ghl_contact["state"] = address.get("province", "")
                ghl_contact["postalCode"] = address.get("postal_code", "")
                ghl_contact["country"] = address.get("country", "")
            
            # Additional fields that might be useful
            ghl_contact["companyName"] = attributes.get("company", "")
            
            return ghl_contact
        except Exception as e:
            logger.error(f"Error mapping Clio to GHL contact: {str(e)}", exc_info=True)
            return None
    
    def process_ghl_webhook(self, webhook_data):
        """Process a webhook from GHL and forward relevant data to Clio"""
        try:
            # Let GHL service process the webhook first
            ghl_result = self.ghl_service.process_webhook(webhook_data)
            
            if not ghl_result['success']:
                return ghl_result
            
            # Extract event type and resource from GHL webhook
            event_type = webhook_data.get('event', '')
            resource = webhook_data.get('resource', {})
            
            transaction_id = ghl_result.get('transaction_id')
            
            # Handle different event types
            if event_type == 'contact_created' or event_type == 'contact_updated':
                # Get the contact ID and fetch full contact data
                contact_id = resource.get('id')
                if not contact_id:
                    error_message = "Contact ID missing in webhook data"
                    self._log_error(transaction_id, "Webhook Processing Error", error_message)
                    return {'success': False, 'error': error_message}
                
                # Fetch complete contact data from GHL
                contact_result = self.ghl_service.get_contact(contact_id)
                if not contact_result['success']:
                    error_message = f"Failed to fetch contact from GHL: {contact_result.get('data', {}).get('message', 'Unknown error')}"
                    self._log_error(transaction_id, "API Error", error_message)
                    return {'success': False, 'error': error_message}
                
                # Map GHL contact data to Clio format
                contact_data = contact_result['data'].get('contact', {})
                clio_contact = self._map_ghl_to_clio_contact(contact_data)
                
                if not clio_contact:
                    error_message = "Failed to map GHL contact to Clio format"
                    self._log_error(transaction_id, "Data Mapping Error", error_message)
                    return {'success': False, 'error': error_message}
                
                # Create or update contact in Clio
                if event_type == 'contact_created':
                    clio_result = self.clio_service.create_contact(clio_contact)
                else:  # contact_updated
                    # First check if contact exists in Clio by email
                    email = contact_data.get('email')
                    if email:
                        search_result = self.clio_service.get_contacts(params={'query': email})
                        if search_result['success'] and search_result['data'].get('data'):
                            # Contact exists, get ID and update
                            clio_contact_id = search_result['data']['data'][0]['id']
                            clio_result = self.clio_service.update_contact(clio_contact_id, clio_contact)
                        else:
                            # Contact doesn't exist, create new
                            clio_result = self.clio_service.create_contact(clio_contact)
                    else:
                        # No email to search by, attempt to create
                        clio_result = self.clio_service.create_contact(clio_contact)
                
                if not clio_result['success']:
                    error_message = f"Failed to create/update contact in Clio: {clio_result.get('data', {}).get('message', 'Unknown error')}"
                    self._log_error(transaction_id, "API Error", error_message)
                    return {'success': False, 'error': error_message}
                
                return {
                    'success': True,
                    'message': f"Successfully processed {event_type} webhook",
                    'ghl_contact_id': contact_id,
                    'clio_result': clio_result['data']
                }
            
            # Handle other event types
            return {
                'success': True,
                'message': f"Webhook received but no action taken for event type: {event_type}"
            }
        
        except Exception as e:
            error_message = f"Error processing GHL webhook: {str(e)}"
            logger.error(error_message, exc_info=True)
            
            # Log error
            transaction_id = self._log_transaction(
                'ghl', 'internal', 'POST', 'webhook/process',
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
                'error': error_message,
                'transaction_id': transaction_id
            }
    
    def process_clio_webhook(self, webhook_data):
        """Process a webhook from Clio and forward relevant data to GHL"""
        try:
            # Let Clio service process the webhook first
            clio_result = self.clio_service.process_webhook(webhook_data)
            
            if not clio_result['success']:
                return clio_result
            
            # Extract event type and resource from Clio webhook
            event_type = webhook_data.get('type', '')
            resource = webhook_data.get('data', {})
            
            transaction_id = clio_result.get('transaction_id')
            
            # Handle different event types
            if event_type == 'Contact.created' or event_type == 'Contact.updated':
                # Get the contact ID and fetch full contact data if needed
                contact_id = resource.get('id')
                if not contact_id:
                    error_message = "Contact ID missing in webhook data"
                    self._log_error(transaction_id, "Webhook Processing Error", error_message)
                    return {'success': False, 'error': error_message}
                
                # Check if we need to fetch more data or if webhook contains all we need
                contact_data = resource
                if not resource.get('attributes'):
                    # Fetch complete contact data from Clio
                    contact_result = self.clio_service.get_contact(contact_id)
                    if not contact_result['success']:
                        error_message = f"Failed to fetch contact from Clio: {contact_result.get('data', {}).get('message', 'Unknown error')}"
                        self._log_error(transaction_id, "API Error", error_message)
                        return {'success': False, 'error': error_message}
                    contact_data = contact_result['data']
                
                # Map Clio contact data to GHL format
                ghl_contact = self._map_clio_to_ghl_contact(contact_data)
                
                if not ghl_contact:
                    error_message = "Failed to map Clio contact to GHL format"
                    self._log_error(transaction_id, "Data Mapping Error", error_message)
                    return {'success': False, 'error': error_message}
                
                # Create or update contact in GHL
                # First check if contact exists in GHL by email
                email = ghl_contact.get('email')
                if email:
                    search_result = self.ghl_service.get_contacts(params={'query': email})
                    if search_result['success'] and search_result['data'].get('contacts'):
                        # Contact exists, get ID and update
                        ghl_contact_id = search_result['data']['contacts'][0]['id']
                        ghl_result = self.ghl_service.update_contact(ghl_contact_id, ghl_contact)
                    else:
                        # Contact doesn't exist, create new
                        ghl_result = self.ghl_service.create_contact(ghl_contact)
                else:
                    # No email to search by, attempt to create
                    ghl_result = self.ghl_service.create_contact(ghl_contact)
                
                if not ghl_result['success']:
                    error_message = f"Failed to create/update contact in GHL: {ghl_result.get('data', {}).get('message', 'Unknown error')}"
                    self._log_error(transaction_id, "API Error", error_message)
                    return {'success': False, 'error': error_message}
                
                return {
                    'success': True,
                    'message': f"Successfully processed {event_type} webhook",
                    'clio_contact_id': contact_id,
                    'ghl_result': ghl_result['data']
                }
            
            # Handle other event types
            return {
                'success': True,
                'message': f"Webhook received but no action taken for event type: {event_type}"
            }
        
        except Exception as e:
            error_message = f"Error processing Clio webhook: {str(e)}"
            logger.error(error_message, exc_info=True)
            
            # Log error
            transaction_id = self._log_transaction(
                'clio', 'internal', 'POST', 'webhook/process',
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
                'error': error_message,
                'transaction_id': transaction_id
            }
    
    def sync_ghl_to_clio(self, entity_type, entity_id=None):
        """Sync data from GHL to Clio"""
        try:
            if entity_type == 'contact':
                if entity_id:
                    # Sync specific contact
                    contact_result = self.ghl_service.get_contact(entity_id)
                    if not contact_result['success']:
                        error_message = f"Failed to fetch contact from GHL: {contact_result.get('data', {}).get('message', 'Unknown error')}"
                        logger.error(error_message)
                        return {'success': False, 'error': error_message}
                    
                    # Map GHL contact data to Clio format
                    contact_data = contact_result['data'].get('contact', {})
                    clio_contact = self._map_ghl_to_clio_contact(contact_data)
                    
                    if not clio_contact:
                        error_message = "Failed to map GHL contact to Clio format"
                        logger.error(error_message)
                        return {'success': False, 'error': error_message}
                    
                    # Create contact in Clio
                    clio_result = self.clio_service.create_contact(clio_contact)
                    
                    if not clio_result['success']:
                        error_message = f"Failed to create contact in Clio: {clio_result.get('data', {}).get('message', 'Unknown error')}"
                        logger.error(error_message)
                        return {'success': False, 'error': error_message}
                    
                    return {
                        'success': True,
                        'message': "Successfully synced contact from GHL to Clio",
                        'ghl_contact_id': entity_id,
                        'clio_result': clio_result['data']
                    }
                else:
                    # Sync all contacts (paginated)
                    # This is just an example, would need pagination handling for production
                    contacts_result = self.ghl_service.get_contacts()
                    if not contacts_result['success']:
                        error_message = f"Failed to fetch contacts from GHL: {contacts_result.get('data', {}).get('message', 'Unknown error')}"
                        logger.error(error_message)
                        return {'success': False, 'error': error_message}
                    
                    # Process each contact
                    sync_results = []
                    contacts = contacts_result['data'].get('contacts', [])
                    
                    for contact in contacts:
                        # Map GHL contact data to Clio format
                        clio_contact = self._map_ghl_to_clio_contact(contact)
                        
                        if clio_contact:
                            # Create contact in Clio
                            clio_result = self.clio_service.create_contact(clio_contact)
                            
                            sync_results.append({
                                'ghl_contact_id': contact.get('id'),
                                'success': clio_result['success'],
                                'result': clio_result['data']
                            })
                    
                    return {
                        'success': True,
                        'message': f"Synced {len(sync_results)} contacts from GHL to Clio",
                        'results': sync_results
                    }
            else:
                error_message = f"Unsupported entity type: {entity_type}"
                logger.error(error_message)
                return {'success': False, 'error': error_message}
        
        except Exception as e:
            error_message = f"Error syncing GHL to Clio: {str(e)}"
            logger.error(error_message, exc_info=True)
            
            # Log error
            transaction_id = self._log_transaction(
                'internal', 'internal', 'POST', 'sync/ghl-to-clio',
                {}, {"entity_type": entity_type, "entity_id": entity_id}, 
                500, {}, {"error": str(e)}, 0, False
            )
            
            self._log_error(
                transaction_id,
                "Sync Error",
                error_message,
                {"entity_type": entity_type, "entity_id": entity_id}
            )
            
            return {
                'success': False,
                'error': error_message,
                'transaction_id': transaction_id
            }
    
    def sync_clio_to_ghl(self, entity_type, entity_id=None):
        """Sync data from Clio to GHL"""
        try:
            if entity_type == 'contact':
                if entity_id:
                    # Sync specific contact
                    contact_result = self.clio_service.get_contact(entity_id)
                    if not contact_result['success']:
                        error_message = f"Failed to fetch contact from Clio: {contact_result.get('data', {}).get('message', 'Unknown error')}"
                        logger.error(error_message)
                        return {'success': False, 'error': error_message}
                    
                    # Map Clio contact data to GHL format
                    ghl_contact = self._map_clio_to_ghl_contact(contact_result['data'])
                    
                    if not ghl_contact:
                        error_message = "Failed to map Clio contact to GHL format"
                        logger.error(error_message)
                        return {'success': False, 'error': error_message}
                    
                    # Create contact in GHL
                    ghl_result = self.ghl_service.create_contact(ghl_contact)
                    
                    if not ghl_result['success']:
                        error_message = f"Failed to create contact in GHL: {ghl_result.get('data', {}).get('message', 'Unknown error')}"
                        logger.error(error_message)
                        return {'success': False, 'error': error_message}
                    
                    return {
                        'success': True,
                        'message': "Successfully synced contact from Clio to GHL",
                        'clio_contact_id': entity_id,
                        'ghl_result': ghl_result['data']
                    }
                else:
                    # Sync all contacts (paginated)
                    # This is just an example, would need pagination handling for production
                    contacts_result = self.clio_service.get_contacts()
                    if not contacts_result['success']:
                        error_message = f"Failed to fetch contacts from Clio: {contacts_result.get('data', {}).get('message', 'Unknown error')}"
                        logger.error(error_message)
                        return {'success': False, 'error': error_message}
                    
                    # Process each contact
                    sync_results = []
                    contacts = contacts_result['data'].get('data', [])
                    
                    for contact in contacts:
                        # Map Clio contact data to GHL format
                        ghl_contact = self._map_clio_to_ghl_contact({'data': contact})
                        
                        if ghl_contact:
                            # Create contact in GHL
                            ghl_result = self.ghl_service.create_contact(ghl_contact)
                            
                            sync_results.append({
                                'clio_contact_id': contact.get('id'),
                                'success': ghl_result['success'],
                                'result': ghl_result['data']
                            })
                    
                    return {
                        'success': True,
                        'message': f"Synced {len(sync_results)} contacts from Clio to GHL",
                        'results': sync_results
                    }
            else:
                error_message = f"Unsupported entity type: {entity_type}"
                logger.error(error_message)
                return {'success': False, 'error': error_message}
        
        except Exception as e:
            error_message = f"Error syncing Clio to GHL: {str(e)}"
            logger.error(error_message, exc_info=True)
            
            # Log error
            transaction_id = self._log_transaction(
                'internal', 'internal', 'POST', 'sync/clio-to-ghl',
                {}, {"entity_type": entity_type, "entity_id": entity_id}, 
                500, {}, {"error": str(e)}, 0, False
            )
            
            self._log_error(
                transaction_id,
                "Sync Error",
                error_message,
                {"entity_type": entity_type, "entity_id": entity_id}
            )
            
            return {
                'success': False,
                'error': error_message,
                'transaction_id': transaction_id
            }
