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
            matter_data = create_clio_matter(contact_data, practice_area, case_description)

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
def create_clio_contact(full_name, email, phone, state, token=None):
    """Create a contact in Clio using the exact format required by Clio API"""
    # Using real API with fallback to mock for testing
    USE_MOCK_DATA = False

    # Parse name 
    name_parts = full_name.split(' ')
    first_name = name_parts[0] if name_parts else ""
    last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ""

    # Short-circuit for development/testing
    if USE_MOCK_DATA:
        print("⚠️ Using mock contact data (DEVELOPMENT MODE)")
        mock_contact = {
            "data": {
                "id": "mock-contact-123",
                "type": "contacts",
                "attributes": {"name": full_name}
            }
        }
        return mock_contact

    # Get token - use passed token or from session
    auth_token = token or session.get('clio_token', '')
    if not auth_token:
        return {"error": "No Clio token available"}

    # Try multiple approaches one by one until one works

    # Headers for all requests
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json"
    }

    # Try approach 1: Direct to /people endpoint
    person_data = {
        "data": {
            "type": "people",
            "attributes": {
                "first_name": first_name,
                "last_name": last_name,
                "is_client": True
            }
        }
    }

    # Add email if provided
    if email:
        person_data["data"]["attributes"]["email_addresses"] = [
            {
                "name": "Work",
                "address": email
            }
        ]

    # Add phone if provided
    if phone:
        person_data["data"]["attributes"]["phone_numbers"] = [
            {
                "name": "Work",
                "number": phone
            }
        ]

    # Add state if available
    if state:
        person_data["data"]["attributes"]["addresses"] = [
            {
                "name": "Home",
                "state": state,
                "country": "US"
            }
        ]

    print(f"📤 Approach 1: Using /people endpoint")
    print(json.dumps(person_data, indent=2))

    people_response = requests.post(
        f"{CLIO_API_BASE}/people",
        headers=headers,
        json=person_data
    )

    print(f"📥 People endpoint response: {people_response.status_code}")

    if people_response.status_code in [200, 201]:
        print("✅ Success with people endpoint!")
        return people_response.json()

    # Try approach 2: Using contact_type_id
    contact_type_data = {
        "data": {
            "type": "contacts",
            "attributes": {
                "first_name": first_name,
                "last_name": last_name,
                "contact_type_id": 1,  # 1 = Person, 2 = Company in many systems
                "is_client": True
            }
        }
    }

    # Add email/phone/state same as before
    if email:
        contact_type_data["data"]["attributes"]["email_addresses"] = person_data["data"]["attributes"].get("email_addresses", [])
    if phone:
        contact_type_data["data"]["attributes"]["phone_numbers"] = person_data["data"]["attributes"].get("phone_numbers", [])
    if state:
        contact_type_data["data"]["attributes"]["addresses"] = person_data["data"]["attributes"].get("addresses", [])

    print(f"📤 Approach 2: Using contact_type_id")
    print(json.dumps(contact_type_data, indent=2))

    type_id_response = requests.post(
        f"{CLIO_API_BASE}/contacts",
        headers=headers,
        json=contact_type_data
    )

    print(f"📥 Contact type id response: {type_id_response.status_code}")

    if type_id_response.status_code in [200, 201]:
        print("✅ Success with contact_type_id approach!")
        return type_id_response.json()

    # Try approach 3: Using entity_type
    entity_type_data = {
        "data": {
            "type": "contacts",
            "attributes": {
                "first_name": first_name,
                "last_name": last_name,
                "entity_type": "Person",
                "is_client": True
            }
        }
    }

    # Add email/phone/state same as before
    if email:
        entity_type_data["data"]["attributes"]["email_addresses"] = person_data["data"]["attributes"].get("email_addresses", [])
    if phone:
        entity_type_data["data"]["attributes"]["phone_numbers"] = person_data["data"]["attributes"].get("phone_numbers", [])
    if state:
        entity_type_data["data"]["attributes"]["addresses"] = person_data["data"]["attributes"].get("addresses", [])

    print(f"📤 Approach 3: Using entity_type")
    print(json.dumps(entity_type_data, indent=2))

    entity_response = requests.post(
        f"{CLIO_API_BASE}/contacts",
        headers=headers,
        json=entity_type_data
    )

    print(f"📥 Entity type response: {entity_response.status_code}")

    if entity_response.status_code in [200, 201]:
        print("✅ Success with entity_type approach!")
        return entity_response.json()

    # Try approach 4: Using meta type
    meta_type_data = {
        "data": {
            "type": "contacts",
            "meta": {
                "type": "Person"
            },
            "attributes": {
                "first_name": first_name,
                "last_name": last_name,
                "is_client": True
            }
        }
    }

    # Add email/phone/state same as before
    if email:
        meta_type_data["data"]["attributes"]["email_addresses"] = person_data["data"]["attributes"].get("email_addresses", [])
    if phone:
        meta_type_data["data"]["attributes"]["phone_numbers"] = person_data["data"]["attributes"].get("phone_numbers", [])
    if state:
        meta_type_data["data"]["attributes"]["addresses"] = person_data["data"]["attributes"].get("addresses", [])

    print(f"📤 Approach 4: Using meta type")
    print(json.dumps(meta_type_data, indent=2))

    meta_response = requests.post(
        f"{CLIO_API_BASE}/contacts",
        headers=headers,
        json=meta_type_data
    )

    print(f"📥 Meta type response: {meta_response.status_code}")

    if meta_response.status_code in [200, 201]:
        print("✅ Success with meta type approach!")
        return meta_response.json()

    # All approaches failed, try to analyze responses to figure out why
    print("❌ All approaches failed to create contact")
    print(f"People endpoint error: {people_response.text[:200]}...")
    print(f"Contact type id error: {type_id_response.text[:200]}...")
    print(f"Entity type error: {entity_response.text[:200]}...")
    print(f"Meta type error: {meta_response.text[:200]}...")

    # Return the response that gave the most information
    for resp in [people_response, type_id_response, entity_response, meta_response]:
        try:
            error_json = resp.json()
            if 'errors' in error_json or 'error' in error_json:
                return {"error": "Failed to create contact", "details": resp.text}
        except:
            pass

    # If we couldn't parse any error, just return the last one
    return {"error": "Failed to create contact", "details": meta_response.text}
def create_clio_matter(contact_data, practice_area, description):
    """Create a matter in Clio"""
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
        # For testing purposes, create a mock matter response
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

    # Prepare matter data
    matter_data = {
        "data": {
            "type": "matters",
            "attributes": {
                "display_number": f"GHL-{contact_id}",
                "description": description or "Lead from GoHighLevel",
                "status": "Open",
                "practice_area": practice_area
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

    # Make API request to Clio
    headers = {
        "Authorization": f"Bearer {session['clio_token']}",
        "Content-Type": "application/json"
    }

    print(f"📤 Sending matter creation request: {json.dumps(matter_data, indent=2)}")
    response = requests.post(
        f"{CLIO_API_BASE}/matters",
        headers=headers,
        json=matter_data
    )

    print(f"📥 Matter creation response status: {response.status_code}")
    print(f"📥 Matter creation response: {response.text[:200]}...")

    if response.status_code not in [200, 201]:
        print(f"❌ Failed to create matter in Clio")
        return {
            "error": "Failed to create matter", 
            "details": response.text
        }

    return response.json()

# Main entry point
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)