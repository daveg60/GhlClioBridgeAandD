# app.py
from flask import Flask, request, jsonify, redirect, session, url_for
import requests
import os
import json
from functools import wraps
import secrets

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(16))

# Configuration
CLIO_CLIENT_ID = os.environ.get('CLIO_CLIENT_ID')
CLIO_CLIENT_SECRET = os.environ.get('CLIO_CLIENT_SECRET')
CLIO_REDIRECT_URI = 'https://ghl-clio-bridge-LawLeaders.replit.app/api/clio-callback'
CLIO_AUTH_URL = 'https://app.clio.com/oauth/authorize'
CLIO_TOKEN_URL = 'https://app.clio.com/oauth/token'
CLIO_API_BASE = 'https://app.clio.com/api/v4'

# Helper functions
def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'clio_token' not in session:
            return redirect(url_for('authorize'))
        return f(*args, **kwargs)
    return decorated

def extract_practice_area(description):
    """Extract practice area from description text"""
    if not description:
        return "Other"

    description_lower = description.lower()

    # Check for personal injury keywords
    personal_injury_keywords = ["personal injury", "accident", "injury", "hurt", "slip and fall", 
                               "car accident", "medical malpractice", "wrongful death"]
    for keyword in personal_injury_keywords:
        if keyword in description_lower:
            return "Personal Injury"

    # Check for family law keywords
    family_law_keywords = ["divorce", "custody", "child support", "alimony", "marriage", 
                          "separation", "adoption", "family", "spouse"]
    for keyword in family_law_keywords:
        if keyword in description_lower:
            return "Family Law"

    # Check for criminal law keywords
    criminal_law_keywords = ["criminal", "arrest", "charge", "offense", "crime", "dui", "dwi", 
                            "theft", "assault", "probation", "jail", "prison", "criminal attorney"]
    for keyword in criminal_law_keywords:
        if keyword in description_lower:
            return "Criminal Law"

    # Check for estate planning keywords
    estate_planning_keywords = ["estate", "will", "trust", "inheritance", "probate", 
                              "executor", "beneficiary", "death", "asset"]
    for keyword in estate_planning_keywords:
        if keyword in description_lower:
            return "Estate Planning"

    # If no match is found, return "Other"
    return "Other"

def parse_transcription_to_case_summary(transcription):
    """Parse transcription to extract key case details without full conversation"""
    if not transcription:
        return ""
    
    # Look for key legal phrases and extract relevant details
    summary_parts = []
    transcription_lower = transcription.lower()
    
    # Extract incident details
    if "accident" in transcription_lower:
        summary_parts.append("Incident: Motor vehicle accident")
    elif "slip" in transcription_lower and "fall" in transcription_lower:
        summary_parts.append("Incident: Slip and fall")
    elif "divorce" in transcription_lower:
        summary_parts.append("Matter: Divorce proceedings")
    elif "custody" in transcription_lower:
        summary_parts.append("Matter: Child custody")
    elif "arrest" in transcription_lower or "charge" in transcription_lower:
        summary_parts.append("Matter: Criminal charges")
    elif "will" in transcription_lower or "estate" in transcription_lower:
        summary_parts.append("Matter: Estate planning")
    
    # Extract injury details
    injuries = []
    if "injury" in transcription_lower or "injured" in transcription_lower:
        if "back" in transcription_lower:
            injuries.append("back injury")
        if "neck" in transcription_lower or "whiplash" in transcription_lower:
            injuries.append("neck/whiplash")
        if "broken" in transcription_lower or "fracture" in transcription_lower:
            injuries.append("fracture")
        if "head" in transcription_lower:
            injuries.append("head injury")
    
    if injuries:
        summary_parts.append(f"Injuries: {', '.join(injuries)}")
    
    # Extract timeframe
    import re
    time_patterns = [
        r"(\d+)\s+(day|week|month|year)s?\s+ago",
        r"last\s+(week|month|year)",
        r"yesterday",
        r"today"
    ]
    
    for pattern in time_patterns:
        match = re.search(pattern, transcription_lower)
        if match:
            summary_parts.append(f"Timeframe: {match.group(0)}")
            break
    
    # Extract if seeking specific outcomes
    if "compensation" in transcription_lower or "damages" in transcription_lower:
        summary_parts.append("Seeking: Compensation/damages")
    elif "medical" in transcription_lower and "bill" in transcription_lower:
        summary_parts.append("Seeking: Medical bill coverage")
    
    # Join all parts or return truncated transcription
    if summary_parts:
        return " | ".join(summary_parts)
    else:
        # Fallback: return first 200 characters of transcription
        return transcription[:200] + "..." if len(transcription) > 200 else transcription

# Routes
@app.route('/')
def index():
    """Homepage with status and login link"""
    clio_token = None

    # First check session
    if 'clio_token' in session:
        clio_token = session['clio_token']
    else:
        # Then check database
        try:
            import psycopg2
            db_url = os.environ.get("DATABASE_URL")
            conn = psycopg2.connect(db_url)
            cursor = conn.cursor()
            cursor.execute("SELECT oauth_token FROM api_configs WHERE service = 'clio' AND oauth_token IS NOT NULL")
            result = cursor.fetchone()
            if result and result[0]:
                clio_token = result[0]
                # Also store in session for future requests
                session['clio_token'] = clio_token
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Error checking database for Clio token: {str(e)}")

    # Generate auth URL for easy re-authentication
    auth_url = f"{CLIO_AUTH_URL}?response_type=code&client_id={CLIO_CLIENT_ID}&redirect_uri={CLIO_REDIRECT_URI}"
    
    if clio_token:
        return jsonify({
            "status": "connected",
            "message": "GHL to Clio bridge is active and authenticated with Clio",
            "reauth_url": auth_url  # Include re-auth URL even when connected
        })
    else:
        return jsonify({
            "status": "not_connected",
            "message": "Not authenticated with Clio",
            "auth_url": auth_url
        })

@app.route('/api/test-clio-credentials')
def test_clio_credentials():
    """Test Clio OAuth credentials without using mock data"""
    try:
        # Test the OAuth authorization URL generation
        if not CLIO_CLIENT_ID or not CLIO_CLIENT_SECRET:
            return jsonify({
                "status": "error",
                "message": "Missing Clio credentials - CLIO_CLIENT_ID or CLIO_CLIENT_SECRET not set"
            }), 400

        # Generate authorization URL to test client ID
        auth_url = f"{CLIO_AUTH_URL}?response_type=code&client_id={CLIO_CLIENT_ID}&redirect_uri={CLIO_REDIRECT_URI}"
        
        # Test if we can reach Clio's OAuth endpoint
        test_response = requests.get(CLIO_AUTH_URL, timeout=10)
        
        if test_response.status_code == 200:
            return jsonify({
                "status": "success",
                "message": "Clio OAuth credentials configured correctly",
                "details": {
                    "client_id": CLIO_CLIENT_ID[:8] + "..." if CLIO_CLIENT_ID else "Not set",
                    "client_secret": "Set" if CLIO_CLIENT_SECRET else "Not set",
                    "auth_url": auth_url,
                    "redirect_uri": CLIO_REDIRECT_URI,
                    "clio_auth_endpoint": "Reachable"
                }
            })
        else:
            return jsonify({
                "status": "warning",
                "message": "Credentials configured but Clio endpoint unreachable",
                "clio_status": test_response.status_code
            }), 200
            
    except requests.exceptions.RequestException as e:
        return jsonify({
            "status": "error", 
            "message": f"Network error testing Clio connection: {str(e)}"
        }), 500
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error testing credentials: {str(e)}"
        }), 500

@app.route('/api/test-create-contact')
def test_create_contact():
    """Test creating a real contact in Clio using API key authentication"""
    try:
        # Try multiple authentication methods
        auth_header = None
        auth_method = None
        
        # Method 1: Check for OAuth token
        clio_token = session.get('clio_token')
        if not clio_token:
            try:
                import psycopg2
                db_url = os.environ.get("DATABASE_URL")
                conn = psycopg2.connect(db_url)
                cursor = conn.cursor()
                cursor.execute("SELECT oauth_token FROM api_configs WHERE service = 'clio' AND oauth_token IS NOT NULL")
                result = cursor.fetchone()
                if result and result[0]:
                    clio_token = result[0]
                cursor.close()
                conn.close()
            except Exception:
                pass
        
        if clio_token:
            auth_header = f"Bearer {clio_token}"
            auth_method = "OAuth Token"
        
        # Method 2: Check for API key
        elif os.environ.get('CLIO_API_KEY'):
            auth_header = f"Bearer {os.environ.get('CLIO_API_KEY')}"
            auth_method = "API Key"
        
        # Method 3: Use Client Credentials flow (if supported)
        elif CLIO_CLIENT_ID and CLIO_CLIENT_SECRET:
            try:
                # Try client credentials grant
                token_data = {
                    'grant_type': 'client_credentials',
                    'client_id': CLIO_CLIENT_ID,
                    'client_secret': CLIO_CLIENT_SECRET
                }
                token_response = requests.post(CLIO_TOKEN_URL, data=token_data, timeout=10)
                if token_response.status_code == 200:
                    token_info = token_response.json()
                    access_token = token_info.get('access_token')
                    if access_token:
                        auth_header = f"Bearer {access_token}"
                        auth_method = "Client Credentials"
            except Exception as e:
                pass
        
        if not auth_header:
            return jsonify({
                "status": "error",
                "message": "No valid Clio authentication available",
                "tried_methods": ["OAuth token (from session/database)", "API key", "Client credentials"],
                "solution": "Need either: 1) Complete OAuth authorization, 2) Provide CLIO_API_KEY, or 3) Use different Clio auth method"
            }), 401
        
        # Create test contact data
        test_contact = {
            "data": {
                "type": "Person",
                "first_name": "Test",
                "last_name": "Contact",
                "phone_numbers": [{
                    "number": "+1-555-123-4567",
                    "type": "work"
                }],
                "email_addresses": [{
                    "address": "test@example.com",
                    "type": "work"
                }]
            }
        }
        
        # Make API call to Clio
        headers = {
            "Authorization": f"Bearer {clio_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        response = requests.post(
            f"{CLIO_API_BASE}/contacts",
            headers=headers,
            json=test_contact,
            timeout=30
        )
        
        if response.status_code == 201:
            contact_data = response.json()
            return jsonify({
                "status": "success",
                "message": "Test contact created successfully in Clio!",
                "contact_id": contact_data.get("data", {}).get("id"),
                "contact_name": f"{test_contact['data']['first_name']} {test_contact['data']['last_name']}"
            })
        else:
            return jsonify({
                "status": "error",
                "message": f"Failed to create contact. Status: {response.status_code}",
                "response": response.text
            }), response.status_code
            
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": f"Error testing contact creation: {str(e)}"
        }), 500

@app.route('/authorize')
def authorize():
    """Redirect to Clio authorization"""
    auth_url = f"{CLIO_AUTH_URL}?response_type=code&client_id={CLIO_CLIENT_ID}&redirect_uri={CLIO_REDIRECT_URI}"
    return redirect(auth_url)

@app.route('/api/clio-callback')
def clio_callback():
    """Handle OAuth callback from Clio"""
    code = request.args.get('code')
    if not code:
        return jsonify({"error": "Authorization code not received"}), 400

    # Exchange code for token
    token_data = {
        'grant_type': 'authorization_code',
        'code': code,
        'client_id': CLIO_CLIENT_ID,
        'client_secret': CLIO_CLIENT_SECRET,
        'redirect_uri': CLIO_REDIRECT_URI
    }

    response = requests.post(CLIO_TOKEN_URL, data=token_data)
    if response.status_code != 200:
        return jsonify({"error": "Failed to get access token", "details": response.text}), 400

    token_info = response.json()
    access_token = token_info.get('access_token')
    refresh_token = token_info.get('refresh_token')

    # Store tokens in session
    session['clio_token'] = access_token
    session['clio_refresh_token'] = refresh_token

    # Store tokens in database using raw SQL to avoid circular imports
    import sqlite3
    import psycopg2
    import os

    # Use PostgreSQL connection from environment variable
    db_url = os.environ.get("DATABASE_URL")
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()

    # Check if Clio config exists
    cursor.execute("SELECT id FROM api_configs WHERE service = 'clio'")
    clio_config = cursor.fetchone()

    if clio_config:
        # Update existing config
        cursor.execute(
            "UPDATE api_configs SET oauth_token = %s, refresh_token = %s WHERE service = 'clio'",
            (access_token, refresh_token)
        )
    else:
        # Create new config
        cursor.execute(
            """INSERT INTO api_configs 
               (service, api_key, api_secret, base_url, oauth_token, refresh_token, is_active, created_at, updated_at) 
               VALUES (%s, %s, %s, %s, %s, %s, %s, NOW(), NOW())""",
            ('clio', CLIO_CLIENT_ID, CLIO_CLIENT_SECRET, CLIO_API_BASE, access_token, refresh_token, True)
        )

    # Save changes to database
    conn.commit()
    cursor.close()
    conn.close()

    return redirect(url_for('index'))

@app.route('/api/ghl-webhook', methods=['POST'])
def ghl_webhook():
    """Handle webhook from GoHighLevel"""
    try:
        data = request.json
        print("✅ Incoming webhook data from GHL:", data)

        # Extract relevant data with multiple fallback methods
        full_name = data.get("full_name", "")
        first_name = data.get("first_name", "")
        last_name = data.get("last_name", "")
        email = data.get("email", "")
        phone = data.get("phone", "")
        case_description = ""
        state = data.get("state", "")
        
        # Try to extract from GHL contact object structure
        if "contact" in data and isinstance(data["contact"], dict):
            contact_obj = data["contact"]
            if not first_name:
                first_name = contact_obj.get("first_name", "")
            if not last_name:
                last_name = contact_obj.get("last_name", "")
            if not full_name and (first_name or last_name):
                full_name = f"{first_name} {last_name}".strip()
            if not email:
                email = contact_obj.get("email", "")
            if not phone:
                phone = contact_obj.get("phone", "")
        
        # Try to extract from other common webhook structures
        if "firstName" in data and not first_name:
            first_name = data.get("firstName", "")
        if "lastName" in data and not last_name:
            last_name = data.get("lastName", "")
        if "name" in data and not full_name:
            full_name = data.get("name", "")
            
        # Build full_name if we have parts but not the whole
        if not full_name and (first_name or last_name):
            full_name = f"{first_name} {last_name}".strip()
            
        # Extract first/last from full_name if we only have that
        if full_name and not first_name and not last_name:
            name_parts = full_name.split(' ', 1)
            first_name = name_parts[0] if name_parts else ""
            last_name = name_parts[1] if len(name_parts) > 1 else ""
            
        print(f"🔍 Debug - Final extracted names: first='{first_name}', last='{last_name}', full='{full_name}'")

        # Try to extract case description from customData
        if "customData" in data and isinstance(data["customData"], dict):
            custom_data = data["customData"]
            if not full_name:
                full_name = custom_data.get("full_name", "")
            if not email:
                email = custom_data.get("email", "")
            if not phone:
                phone = custom_data.get("phone", "")
            case_description = custom_data.get("case_description", "")

        # Check for transcription
        transcription = data.get("transcription", "")

        # Parse transcription into structured case summary
        if transcription:
            final_case_description = parse_transcription_to_case_summary(transcription)
        else:
            final_case_description = case_description

        # Extract practice area from transcription first, then case_description
        practice_area = extract_practice_area(transcription or case_description)

        # Get the real Clio token from session or database
        clio_token = None
        
        # Try to get token from session first
        if 'clio_token' in session:
            clio_token = session['clio_token']
            print("✅ Using Clio token from session")
        else:
            # Then try to get token from database
            try:
                import psycopg2
                db_url = os.environ.get("DATABASE_URL")
                # Use connection pooling to avoid rate limit issues
                conn = psycopg2.connect(db_url, connect_timeout=5)
                cursor = conn.cursor()
                cursor.execute("SELECT oauth_token FROM api_configs WHERE service = 'clio' AND oauth_token IS NOT NULL LIMIT 1")
                result = cursor.fetchone()
                if result and result[0]:
                    clio_token = result[0]
                    print("✅ Using Clio token from database")
                cursor.close()
                conn.close()
            except Exception as e:
                print(f"⚠️ Database error (will use mock data): {str(e)}")
                
        # Debug token status
        if clio_token:
            print(f"✅ Found Clio token: {clio_token[:20]}...")
        else:
            print("❌ No Clio token found - this will cause API failures")
        
        if clio_token:
            # Create contact in Clio and pass the token
            contact_data = create_clio_contact(full_name, email, phone, state, token=clio_token)

            # Create matter in Clio
            matter_data = create_clio_matter(contact_data, practice_area, final_case_description, token=clio_token)

            return jsonify({
                "status": "success",
                "message": "Data forwarded to Clio",
                "clio_contact": contact_data,
                "clio_matter": matter_data
            })
        else:
            return jsonify({
                "status": "error",
                "message": "Not authenticated with Clio"
            }), 401

    except Exception as e:
        print(f"❌ Error processing webhook: {str(e)}")
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/clio-webhook', methods=['POST'])
def clio_webhook():
    """Handle webhook from Clio (for future use)"""
    # This can be implemented later if needed
    return jsonify({"status": "received"})

@app.route('/ping', methods=['GET'])
def ping():
    """Simple health check endpoint"""
    return jsonify({"status": "ok", "message": "Service is running"}), 200


@app.route('/api/logs', methods=['GET'])
def view_logs():
    """View transaction logs"""
    try:
        # Connect to the database
        import psycopg2
        db_url = os.environ.get("DATABASE_URL")
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()

        # Get transaction count
        cursor.execute("SELECT COUNT(*) FROM transactions")
        total_count = cursor.fetchone()[0]

        # Get recent transactions
        cursor.execute(
            """SELECT id, source, destination, request_method, request_url, 
                     response_status, success, created_at 
              FROM transactions 
              ORDER BY created_at DESC
              LIMIT 10"""
        )

        transactions = []
        for t in cursor.fetchall():
            t_id, source, dest, method, url, status, success, created = t
            transactions.append({
                "id": t_id,
                "source": source,
                "destination": dest,
                "method": method,
                "url": url,
                "status": status,
                "success": success,
                "created_at": created.isoformat() if created else None
            })

        # Get error count
        cursor.execute("SELECT COUNT(*) FROM error_logs")
        error_count = cursor.fetchone()[0]

        # Get recent errors
        cursor.execute(
            """SELECT id, transaction_id, error_type, error_message, created_at 
              FROM error_logs 
              ORDER BY created_at DESC
              LIMIT 5"""
        )

        errors = []
        for e in cursor.fetchall():
            e_id, t_id, e_type, message, created = e
            errors.append({
                "id": e_id,
                "transaction_id": t_id,
                "type": e_type,
                "message": message,
                "created_at": created.isoformat() if created else None
            })

        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "total_transactions": total_count,
            "total_errors": error_count,
            "recent_transactions": transactions,
            "recent_errors": errors
        })

    except Exception as e:
        print(f"Error getting logs: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error getting logs: {str(e)}"
        }), 500


@app.route('/api/add-test-transaction', methods=['POST'])
def add_test_transaction():
    """Add a test transaction for development purposes"""
    try:
        import psycopg2
        import json
        from datetime import datetime

        # Connect to the database
        db_url = os.environ.get("DATABASE_URL")
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()

        # Get data from request or use defaults
        data = request.json or {}
        source = data.get('source', 'ghl')
        destination = data.get('destination', 'clio')

        # Insert a test transaction
        cursor.execute(
            """INSERT INTO transactions
               (source, destination, request_method, request_url, request_headers,
                request_body, response_status, response_body, duration_ms, success, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id""",
            (source, destination, 'POST', '/api/test-endpoint', 
             json.dumps({"Content-Type": "application/json"}),
             json.dumps({"name": "Test User", "email": "test@example.com"}),
             200, json.dumps({"id": "test-123", "status": "created"}),
             150, True, datetime.now())
        )

        transaction_id = cursor.fetchone()[0]

        # Commit the transaction
        conn.commit()
        cursor.close()
        conn.close()

        return jsonify({
            "status": "success",
            "message": f"Added test transaction with ID: {transaction_id}"
        })

    except Exception as e:
        print(f"Error adding test transaction: {str(e)}")
        return jsonify({
            "status": "error",
            "message": f"Error adding test transaction: {str(e)}"
        }), 500

# Clio API Functions
def create_clio_contact(full_name, email, phone, state=None, token=None):
    """Create a contact in Clio using the Clio API documentation format"""
    import requests
    import json
    import hashlib
    from datetime import datetime
    from flask import session

    # Parse name 
    name_parts = full_name.split(' ')
    first_name = name_parts[0] if name_parts else ""
    last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ""

    # Get authentication token
    auth_token = token or session.get('clio_token', '')
    if not auth_token:
        return {"error": "No Clio authentication token available"}

    # API endpoint based on Clio documentation
    CLIO_API_BASE = "https://app.clio.com/api/v4"
    contacts_url = f"{CLIO_API_BASE}/contacts"

    # Set up request headers
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # APPROACH 1: Corrected format based on Clio support feedback
    # Using "data" wrapper instead of "contact" wrapper
    contact_data = {
        "data": {
            "type": "Person",
            "first_name": first_name,
            "last_name": last_name
        }
    }

    # Add email if provided
    if email:
        contact_data["data"]["email_addresses"] = [
            {
                "address": email,
                "type": "work"
            }
        ]

    # Add phone if provided
    if phone:
        contact_data["data"]["phone_numbers"] = [
            {
                "number": phone,
                "type": "work"
            }
        ]

    # Add state if provided
    if state:
        contact_data["data"]["addresses"] = [
            {
                "state": state,
                "country": "US",
                "type": "home"
            }
        ]

    try:
        print("Sending contact creation request to Clio API...")
        print(f"Request data: {json.dumps(contact_data, indent=2)}")

        response = requests.post(
            contacts_url,
            headers=headers,
            json=contact_data,
            timeout=20
        )

        print(f"Response status: {response.status_code}")
        print(f"Response body: {response.text[:200]}...")  # First 200 chars

        if response.status_code in [200, 201]:
            print("Successfully created contact in Clio")
            return response.json()
        else:
            print(f"❌ Failed to create contact in Clio. Status: {response.status_code}")
            print(f"❌ Response: {response.text}")
            return {
                "error": f"Failed to create contact in Clio API. Status: {response.status_code}",
                "response_body": response.text,
                "request_data": contact_data
            }

    except Exception as e:
        print(f"Exception when creating contact: {str(e)}")
        return {"error": f"Exception when creating contact: {str(e)}"}

def create_clio_matter(contact_data, practice_area, description, token=None):
    """Create a matter in Clio using the correct API format"""
    import requests
    import json
    from flask import session

    # Extract contact ID
    contact_id = contact_data.get("data", {}).get("id")
    if not contact_id:
        return {"error": "Cannot create matter without valid contact ID"}

    # Get authentication token
    auth_token = token or session.get('clio_token', '')
    if not auth_token:
        return {"error": "No Clio authentication token available"}

    # Set up headers
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # Use the correct Clio API format - based on their documentation
    matter_data = {
        "data": {
            "type": "Matter",
            "client": {
                "id": str(contact_id)
            },
            "display_number": f"GHL-{contact_id}",
            "description": description or "Lead from GoHighLevel",
            "status": "Pending",
            "practice_area": practice_area or "General"
        }
    }

    try:
        print(f"📤 Creating matter with data: {json.dumps(matter_data, indent=2)}")

        response = requests.post(
            f"{CLIO_API_BASE}/matters",
            headers=headers,
            json=matter_data,
            timeout=20
        )

        print(f"📥 Matter creation response status: {response.status_code}")
        print(f"📥 Matter creation response: {response.text}")

        if response.status_code in [200, 201]:
            print("✅ Successfully created matter in Clio")
            return response.json()
        else:
            # If this format fails, try the alternative endpoint
            print("🔄 Trying alternative endpoint: /contacts/{id}/matters")

            alternative_response = requests.post(
                f"{CLIO_API_BASE}/contacts/{contact_id}/matters",
                headers=headers,
                json={
                    "data": {
                        "type": "Matter",
                        "display_number": f"GHL-{contact_id}",
                        "description": description or "Lead from GoHighLevel",
                        "status": "Pending",
                        "practice_area": practice_area or "General"
                    }
                },
                timeout=20
            )

            print(f"📥 Alternative response status: {alternative_response.status_code}")
            print(f"📥 Alternative response: {alternative_response.text}")

            if alternative_response.status_code in [200, 201]:
                print("✅ Successfully created matter via alternative endpoint")
                return alternative_response.json()

            return {
                "error": "Failed to create matter",
                "main_response": response.text,
                "alternative_response": alternative_response.text,
                "contact_id": contact_id
            }

    except Exception as e:
        print(f"❌ Exception creating matter: {str(e)}")
        return {"error": f"Exception creating matter: {str(e)}"}
# Main entry point
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)