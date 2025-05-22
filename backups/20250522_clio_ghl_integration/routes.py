import logging
from flask import render_template, request, jsonify, flash, redirect, url_for
from sqlalchemy import desc
from app import app, db
from models import Transaction, ErrorLog, ApiConfig, DataMapping
from services.ghl_service import GHLService
from services.clio_service import ClioService
from services.integration_service import IntegrationService

logger = logging.getLogger(__name__)

# Initialize services
ghl_service = GHLService()
clio_service = ClioService()
integration_service = IntegrationService(ghl_service, clio_service)


@app.route('/')
def index():
    """Home page with overview of the API integration portal"""
    return render_template('index.html')


@app.route('/dashboard')
def dashboard():
    """Dashboard with key metrics and status information"""
    # Get transaction stats
    total_transactions = Transaction.query.count()
    successful_transactions = Transaction.query.filter_by(success=True).count()
    failed_transactions = Transaction.query.filter_by(success=False).count()
    
    # Success rate calculation
    success_rate = 0
    if total_transactions > 0:
        success_rate = (successful_transactions / total_transactions) * 100
    
    # Recent errors
    recent_errors = ErrorLog.query.order_by(desc(ErrorLog.created_at)).limit(5).all()
    
    # API configuration status
    ghl_config = ApiConfig.query.filter_by(service='ghl').first()
    clio_config = ApiConfig.query.filter_by(service='clio').first()
    
    return render_template(
        'dashboard.html',
        total_transactions=total_transactions,
        successful_transactions=successful_transactions,
        failed_transactions=failed_transactions,
        success_rate=success_rate,
        recent_errors=recent_errors,
        ghl_config=ghl_config,
        clio_config=clio_config
    )


@app.route('/transactions')
def view_transactions():
    """View and search transaction logs"""
    # Get query parameters for filtering
    source = request.args.get('source')
    destination = request.args.get('destination')
    status = request.args.get('status')
    
    # Build query with filters
    query = Transaction.query
    
    if source:
        query = query.filter_by(source=source)
    if destination:
        query = query.filter_by(destination=destination)
    if status:
        if status == 'success':
            query = query.filter_by(success=True)
        elif status == 'failure':
            query = query.filter_by(success=False)
    
    # Get paginated results
    page = request.args.get('page', 1, type=int)
    per_page = 20
    transactions = query.order_by(desc(Transaction.created_at)).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('transactions.html', transactions=transactions)


@app.route('/logs')
def view_logs():
    """View error logs"""
    # Get query parameters for filtering
    error_type = request.args.get('error_type')
    
    # Build query with filters
    query = ErrorLog.query
    
    if error_type:
        query = query.filter_by(error_type=error_type)
    
    # Get paginated results
    page = request.args.get('page', 1, type=int)
    per_page = 20
    logs = query.order_by(desc(ErrorLog.created_at)).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    # Get unique error types for filter dropdown
    error_types = db.session.query(ErrorLog.error_type).distinct().all()
    error_types = [et[0] for et in error_types]
    
    return render_template('logs.html', logs=logs, error_types=error_types)


@app.route('/settings', methods=['GET', 'POST'])
def settings():
    """View and update API configuration settings"""
    if request.method == 'POST':
        service = request.form.get('service')
        
        if service == 'ghl':
            # Update GHL configuration
            ghl_config = ApiConfig.query.filter_by(service='ghl').first()
            if not ghl_config:
                ghl_config = ApiConfig(service='ghl')
                db.session.add(ghl_config)
            
            ghl_config.api_key = request.form.get('ghl_api_key')
            ghl_config.base_url = request.form.get('ghl_base_url')
            ghl_config.is_active = 'ghl_is_active' in request.form
            
            # Additional config as JSON
            additional_config = {}
            if request.form.get('ghl_location_id'):
                additional_config['location_id'] = request.form.get('ghl_location_id')
            ghl_config.additional_config = additional_config
            
            db.session.commit()
            flash('GoHighLevel API configuration updated successfully', 'success')
        
        elif service == 'clio':
            # Update Clio configuration
            clio_config = ApiConfig.query.filter_by(service='clio').first()
            if not clio_config:
                clio_config = ApiConfig(service='clio')
                db.session.add(clio_config)
            
            clio_config.api_key = request.form.get('clio_api_key')
            clio_config.api_secret = request.form.get('clio_api_secret')
            clio_config.base_url = request.form.get('clio_base_url')
            clio_config.is_active = 'clio_is_active' in request.form
            
            db.session.commit()
            flash('Clio API configuration updated successfully', 'success')
        
        return redirect(url_for('settings'))
    
    # GET method
    ghl_config = ApiConfig.query.filter_by(service='ghl').first()
    clio_config = ApiConfig.query.filter_by(service='clio').first()
    
    # Data mappings
    mappings = DataMapping.query.all()
    
    return render_template(
        'settings.html',
        ghl_config=ghl_config,
        clio_config=clio_config,
        mappings=mappings
    )


@app.route('/api/ghl-webhook', methods=['POST'])
def ghl_webhook():
    """Endpoint for receiving webhooks from GoHighLevel"""
    try:
        webhook_data = request.json
        logger.info(f"Received GHL webhook: {webhook_data}")
        
        # Process the webhook data and forward to Clio if needed
        result = integration_service.process_ghl_webhook(webhook_data)
        
        return jsonify({"status": "success", "message": "Webhook processed successfully"})
    
    except Exception as e:
        logger.error(f"Error processing GHL webhook: {str(e)}", exc_info=True)
        
        # Log the error to database
        error_log = ErrorLog(
            error_type="GHL Webhook Error",
            error_message=str(e),
            error_details={"request_data": request.json} if request.is_json else {"request_data": request.data.decode('utf-8')}
        )
        db.session.add(error_log)
        db.session.commit()
        
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/clio-webhook', methods=['POST'])
def clio_webhook():
    """Endpoint for receiving webhooks from Clio"""
    try:
        webhook_data = request.json
        logger.info(f"Received Clio webhook: {webhook_data}")
        
        # Process the webhook data and forward to GHL if needed
        result = integration_service.process_clio_webhook(webhook_data)
        
        return jsonify({"status": "success", "message": "Webhook processed successfully"})
    
    except Exception as e:
        logger.error(f"Error processing Clio webhook: {str(e)}", exc_info=True)
        
        # Log the error to database
        error_log = ErrorLog(
            error_type="Clio Webhook Error",
            error_message=str(e),
            error_details={"request_data": request.json} if request.is_json else {"request_data": request.data.decode('utf-8')}
        )
        db.session.add(error_log)
        db.session.commit()
        
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/sync-data', methods=['POST'])
def sync_data():
    """Endpoint to manually trigger data synchronization between GHL and Clio"""
    try:
        direction = request.json.get('direction', 'ghl_to_clio')
        entity_type = request.json.get('entity_type', 'contact')
        entity_id = request.json.get('entity_id')
        
        if direction == 'ghl_to_clio':
            result = integration_service.sync_ghl_to_clio(entity_type, entity_id)
        else:
            result = integration_service.sync_clio_to_ghl(entity_type, entity_id)
        
        return jsonify({"status": "success", "result": result})
    
    except Exception as e:
        logger.error(f"Error syncing data: {str(e)}", exc_info=True)
        
        # Log the error to database
        error_log = ErrorLog(
            error_type="Data Sync Error",
            error_message=str(e),
            error_details={
                "request_data": request.json,
                "direction": request.json.get('direction'),
                "entity_type": request.json.get('entity_type'),
                "entity_id": request.json.get('entity_id')
            }
        )
        db.session.add(error_log)
        db.session.commit()
        
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/test-connection', methods=['POST'])
def test_connection():
    """Endpoint to test API connections to GHL and Clio"""
    service = request.json.get('service')
    
    try:
        if service == 'ghl':
            result = ghl_service.test_connection()
        elif service == 'clio':
            result = clio_service.test_connection()
        else:
            return jsonify({"status": "error", "message": "Invalid service specified"}), 400
        
        if result['success']:
            return jsonify({
                "status": "success", 
                "message": f"Successfully connected to {service.upper()}"
            })
        else:
            return jsonify({
                "status": "error", 
                "message": result['message']
            }), 400
    
    except Exception as e:
        logger.error(f"Error testing {service} connection: {str(e)}", exc_info=True)
        
        # Log the error to database
        error_log = ErrorLog(
            error_type=f"{service.upper()} Connection Test Error",
            error_message=str(e),
            error_details={"service": service}
        )
        db.session.add(error_log)
        db.session.commit()
        
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route('/api/data-mappings', methods=['GET', 'POST', 'PUT', 'DELETE'])
def manage_data_mappings():
    """API endpoint to manage data field mappings"""
    if request.method == 'GET':
        mappings = DataMapping.query.all()
        return jsonify([{
            'id': m.id,
            'ghl_field': m.ghl_field,
            'clio_field': m.clio_field,
            'mapping_type': m.mapping_type,
            'transform_logic': m.transform_logic,
            'is_active': m.is_active
        } for m in mappings])
    
    elif request.method == 'POST':
        try:
            data = request.json
            mapping = DataMapping(
                ghl_field=data['ghl_field'],
                clio_field=data['clio_field'],
                mapping_type=data.get('mapping_type', 'direct'),
                transform_logic=data.get('transform_logic'),
                is_active=data.get('is_active', True)
            )
            db.session.add(mapping)
            db.session.commit()
            return jsonify({
                "status": "success",
                "message": "Mapping created successfully",
                "id": mapping.id
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)}), 400
    
    elif request.method == 'PUT':
        try:
            data = request.json
            mapping = DataMapping.query.get(data['id'])
            if not mapping:
                return jsonify({"status": "error", "message": "Mapping not found"}), 404
            
            mapping.ghl_field = data.get('ghl_field', mapping.ghl_field)
            mapping.clio_field = data.get('clio_field', mapping.clio_field)
            mapping.mapping_type = data.get('mapping_type', mapping.mapping_type)
            mapping.transform_logic = data.get('transform_logic', mapping.transform_logic)
            mapping.is_active = data.get('is_active', mapping.is_active)
            
            db.session.commit()
            return jsonify({
                "status": "success",
                "message": "Mapping updated successfully"
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)}), 400
    
    elif request.method == 'DELETE':
        try:
            mapping_id = request.json.get('id')
            mapping = DataMapping.query.get(mapping_id)
            if not mapping:
                return jsonify({"status": "error", "message": "Mapping not found"}), 404
            
            db.session.delete(mapping)
            db.session.commit()
            return jsonify({
                "status": "success",
                "message": "Mapping deleted successfully"
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"status": "error", "message": str(e)}), 400
