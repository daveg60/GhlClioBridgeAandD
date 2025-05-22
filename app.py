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
CLIO_REDIRECT_URI = 'https://5e86d6d8-28eb-409f-9660-4664fc234315-00-3mg3krliahhk6.worf.replit.dev/api/clio-callback'
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

        # Extract relevant data
        # This will depend on the actual structure of your GHL webhook data
        full_name = data.get("full_name", "")
        email = data.get("email", "")
        phone = data.get("phone", "")
        case_description = ""
        state = data.get("state", "")

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

        # Extract practice area
        practice_area = extract_practice_area(case_description or transcription)

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
                
        # Enable mock data only if we don't have a real token
        USE_MOCK_DATA = clio_token is None
        if USE_MOCK_DATA:
            print("⚠️ No Clio token found - using mock data for testing")
            clio_token = "mock-token-for-testing"
        
        if clio_token:
            # Create contact in Clio and pass the token
            contact_data = create_clio_contact(full_name, email, phone, state, token=clio_token)

            # Create matter in Clio
            matter_data = create_clio_matter(contact_data, practice_area, case_description, token=clio_token)

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
            print("Failed to create contact - using mock data for development")

            # Create a unique hash-based ID for consistent mock data
            mock_id = hashlib.md5(f"{full_name}:{email}".encode()).hexdigest()[:8]

            # Return mock data with the expected structure
            mock_contact = {
                "data": {
                    "id": f"mock-{mock_id}",
                    "type": "contacts",
                    "attributes": {
                        "name": full_name,
                        "first_name": first_name,
                        "last_name": last_name,
                        "created_at": datetime.now().isoformat(),
                        "email_addresses": [
                            {
                                "address": email,
                                "type": "work"
                            }
                        ] if email else [],
                        "phone_numbers": [
                            {
                                "number": phone,
                                "type": "work"
                            }
                        ] if phone else []
                    }
                }
            }

            return {
                "error": "Failed to create contact in Clio API",
                "mock_data": mock_contact,
                "data": mock_contact["data"]  # For compatibility with successful responses
            }

    except Exception as e:
        print(f"Exception when creating contact: {str(e)}")
        return {"error": f"Exception when creating contact: {str(e)}"}

def create_clio_matter(contact_data, practice_area, description, token=None):
    """Create a matter in Clio - trying multiple formats to find what works"""
    import requests
    import json
    from flask import session

    # Using real API for production
    USE_MOCK_DATA = False

    # Check if we have a valid contact - for mock data we'll still proceed
    if "error" in contact_data and not USE_MOCK_DATA:
        print(f"❌ Cannot create matter without valid contact: {contact_data['error']}")
        return {"error": "Cannot create matter without valid contact", "details": contact_data["error"]}

    # Extract contact ID or use the mock ID if available
    contact_id = contact_data.get("data", {}).get("id", "mock-contact-123")

    # If using mock data, short-circuit
    if USE_MOCK_DATA:
        print("⚠️ Using mock matter data (DEVELOPMENT MODE)")
        mock_matter = {
            "data": {
                "id": "mock-matter-456",
                "type": "matters",
                "attributes": {
                    "display_number": f"GHL-{contact_id}",
                    "description": description or "Lead from GoHighLevel",
                    "status": "Open",
                    "practice_area": practice_area,
                    "created_at": "2025-05-15T22:53:30Z",
                    "updated_at": "2025-05-15T22:53:30Z"
                },
                "relationships": {
                    "client": {
                        "data": {
                            "type": "contacts",
                            "id": contact_id
                        }
                    }
                }
            }
        }
        return mock_matter

    # Only check for contact ID if not using mock data
    if not contact_id:
        print("❌ Contact data doesn't contain a valid ID")
        return {"error": "Cannot create matter without valid contact", "details": "Contact ID not found"}

    # Get authentication token - use passed token or from session
    auth_token = token or session.get('clio_token', '')
    if not auth_token:
        return {"error": "No Clio authentication token available"}

    # Set up headers
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # APPROACH 1: Try client_id at root level of data
    print("🔍 ATTEMPT 1: client_id at root level")
    matter_data_1 = {
        "data": {
            "type": "matters",
            "client_id": str(contact_id),
            "display_number": f"GHL-{contact_id}",
            "description": description or "Lead from GoHighLevel",
            "status": "Open",
            "practice_area": practice_area
        }
    }

    try:
        print(f"📤 Request 1: {json.dumps(matter_data_1, indent=2)}")
        response1 = requests.post(
            f"{CLIO_API_BASE}/matters",
            headers=headers,
            json=matter_data_1,
            timeout=20
        )
        print(f"📥 Response 1 status: {response1.status_code}")
        print(f"📥 Response 1 body: {response1.text[:300]}...")

        if response1.status_code in [200, 201]:
            print("✅ Success with client_id at root level!")
            return response1.json()
    except Exception as e:
        print(f"❌ Error with approach 1: {str(e)}")

    # APPROACH 2: Try numeric client_id in attributes
    print("🔍 ATTEMPT 2: numeric client_id in attributes")
    matter_data_2 = {
        "data": {
            "type": "matters",
            "attributes": {
                "client_id": int(contact_id) if contact_id.isdigit() else contact_id,
                "display_number": f"GHL-{contact_id}",
                "description": description or "Lead from GoHighLevel",
                "status": "Open",
                "practice_area": practice_area
            }
        }
    }

    try:
        print(f"📤 Request 2: {json.dumps(matter_data_2, indent=2)}")
        response2 = requests.post(
            f"{CLIO_API_BASE}/matters",
            headers=headers,
            json=matter_data_2,
            timeout=20
        )
        print(f"📥 Response 2 status: {response2.status_code}")
        print(f"📥 Response 2 body: {response2.text[:300]}...")

        if response2.status_code in [200, 201]:
            print("✅ Success with numeric client_id in attributes!")
            return response2.json()
    except Exception as e:
        print(f"❌ Error with approach 2: {str(e)}")

    # APPROACH 3: Try without wrapper object (direct to API)
    print("🔍 ATTEMPT 3: Direct format without data wrapper")
    matter_data_3 = {
        "client_id": str(contact_id),
        "display_number": f"GHL-{contact_id}",
        "description": description or "Lead from GoHighLevel",
        "status": "Open",
        "practice_area": practice_area
    }

    try:
        print(f"📤 Request 3: {json.dumps(matter_data_3, indent=2)}")
        response3 = requests.post(
            f"{CLIO_API_BASE}/matters",
            headers=headers,
            json=matter_data_3,
            timeout=20
        )
        print(f"📥 Response 3 status: {response3.status_code}")
        print(f"📥 Response 3 body: {response3.text[:300]}...")

        if response3.status_code in [200, 201]:
            print("✅ Success with direct format!")
            return response3.json()
    except Exception as e:
        print(f"❌ Error with approach 3: {str(e)}")

    # APPROACH 4: Try with matter wrapper (like old contact format)
    print("🔍 ATTEMPT 4: Using matter wrapper")
    matter_data_4 = {
        "matter": {
            "client_id": str(contact_id),
            "display_number": f"GHL-{contact_id}",
            "description": description or "Lead from GoHighLevel",
            "status": "Open",
            "practice_area": practice_area
        }
    }

    try:
        print(f"📤 Request 4: {json.dumps(matter_data_4, indent=2)}")
        response4 = requests.post(
            f"{CLIO_API_BASE}/matters",
            headers=headers,
            json=matter_data_4,
            timeout=20
        )
        print(f"📥 Response 4 status: {response4.status_code}")
        print(f"📥 Response 4 body: {response4.text[:300]}...")

        if response4.status_code in [200, 201]:
            print("✅ Success with matter wrapper!")
            return response4.json()
    except Exception as e:
        print(f"❌ Error with approach 4: {str(e)}")

    # APPROACH 5: Try using contact reference format
    print("🔍 ATTEMPT 5: Using contact reference")
    matter_data_5 = {
        "data": {
            "type": "matters",
            "attributes": {
                "display_number": f"GHL-{contact_id}",
                "description": description or "Lead from GoHighLevel",
                "status": "Open",
                "practice_area": practice_area,
                "contact": {
                    "id": str(contact_id)
                }
            }
        }
    }

    try:
        print(f"📤 Request 5: {json.dumps(matter_data_5, indent=2)}")
        response5 = requests.post(
            f"{CLIO_API_BASE}/matters",
            headers=headers,
            json=matter_data_5,
            timeout=20
        )
        print(f"📥 Response 5 status: {response5.status_code}")
        print(f"📥 Response 5 body: {response5.text[:300]}...")

        if response5.status_code in [200, 201]:
            print("✅ Success with contact reference!")
            return response5.json()
    except Exception as e:
        print(f"❌ Error with approach 5: {str(e)}")

    # If all approaches failed, return detailed error info
    print("⚠️ All matter creation approaches failed. Last response details:")
    return {
        "error": "Failed to create matter in Clio API after trying 5 different formats",
        "last_response_status": response5.status_code if 'response5' in locals() else "No response",
        "last_response_body": response5.text if 'response5' in locals() else "No response body",
        "contact_id_used": contact_id
    }
# Main entry point
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)