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

    if clio_token:
        return jsonify({
            "status": "connected",
            "message": "GHL to Clio bridge is active and authenticated with Clio"
        })
    else:
        auth_url = f"{CLIO_AUTH_URL}?response_type=code&client_id={CLIO_CLIENT_ID}&redirect_uri={CLIO_REDIRECT_URI}"
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
        state = ""

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

        # Check if we're authenticated with Clio (either via session or database)
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

        if clio_token:
            # Create contact in Clio
            contact_data = create_clio_contact(full_name, email, phone, state)

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

# Clio API Functions
def create_clio_contact(full_name, email, phone, state):
    """Create a contact in Clio"""
    # Parse name
    name_parts = full_name.split(' ')
    first_name = name_parts[0] if name_parts else ""
    last_name = ' '.join(name_parts[1:]) if len(name_parts) > 1 else ""

    # Prepare contact data - with the correct structure for specifying person type
    contact_data = {
        "data": {
            "type": "contacts",
            "attributes": {
                "name": f"{first_name} {last_name}",
                "first_name": first_name,
                "last_name": last_name,
                "title": "",
                "prefix": "",
                "is_client": True,
                "contact_type_id": 1,  # 1 for Person, 2 for Company
                "email_addresses": [
                    {
                        "name": "Work",
                        "address": email
                    }
                ],
                "phone_numbers": [
                    {
                        "name": "Work",
                        "number": phone
                    }
                ]
            }
        }
    }

    # Add state if available
    if state:
        contact_data["data"]["attributes"]["addresses"] = [
            {
                "name": "Home",
                "state": state,
                "country": "US"
            }
        ]

    # Make API request to Clio
    headers = {
        "Authorization": f"Bearer {session['clio_token']}",
        "Content-Type": "application/json"
    }

    # Debug output
    print(f"✅ Sending contact data to Clio: {json.dumps(contact_data, indent=2)}")

    response = requests.post(
        f"{CLIO_API_BASE}/contacts",
        headers=headers,
        json=contact_data
    )

    # Log the response for debugging
    print(f"✅ Clio API response status: {response.status_code}")
    print(f"✅ Clio API response: {response.text}")

    if response.status_code not in [200, 201]:
        print(f"❌ Error creating Clio contact: {response.text}")
        return {"error": "Failed to create contact", "details": response.text}

    return response.json()

def create_clio_matter(contact_data, practice_area, description):
    """Create a matter in Clio"""
    # Check if we have a valid contact
    if "error" in contact_data:
        return {"error": "Cannot create matter without valid contact"}

    # Extract contact ID
    contact_id = contact_data.get("data", {}).get("id")
    if not contact_id:
        return {"error": "Contact ID not found"}

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

    response = requests.post(
        f"{CLIO_API_BASE}/matters",
        headers=headers,
        json=matter_data
    )

    if response.status_code not in [200, 201]:
        print(f"❌ Error creating Clio matter: {response.text}")
        return {"error": "Failed to create matter", "details": response.text}

    return response.json()

# Main entry point
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)