# app.py
from flask import Flask, request, jsonify, redirect, session, url_for
import requests
import os
import json
from functools import wraps
import secrets
import psycopg2

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(16))

# Configuration
CLIO_CLIENT_ID = os.environ.get('CLIO_CLIENT_ID')
CLIO_CLIENT_SECRET = os.environ.get('CLIO_CLIENT_SECRET')
CLIO_REDIRECT_URI = 'https://ghl-clio-bridge-a-and-d-LawLeaders.replit.app/api/clio-callback'
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

def refresh_clio_token():
    """Automatically refresh expired Clio OAuth token"""
    try:
        # Get refresh token from database
        db_url = os.environ.get("DATABASE_URL")
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        cursor.execute("SELECT refresh_token FROM api_configs WHERE service = 'clio' AND refresh_token IS NOT NULL LIMIT 1")
        result = cursor.fetchone()

        if not result or not result[0]:
            print("❌ No refresh token found in database")
            cursor.close()
            conn.close()
            return None

        refresh_token = result[0]
        print(f"🔄 Refreshing Clio token using refresh token...")

        # Request new access token using refresh token
        token_data = {
            'grant_type': 'refresh_token',
            'refresh_token': refresh_token,
            'client_id': CLIO_CLIENT_ID,
            'client_secret': CLIO_CLIENT_SECRET
        }

        response = requests.post(CLIO_TOKEN_URL, data=token_data, timeout=10)

        if response.status_code == 200:
            token_info = response.json()
            new_access_token = token_info.get('access_token')
            new_refresh_token = token_info.get('refresh_token', refresh_token)  # Use new refresh token if provided

            # Update tokens in database
            cursor.execute(
                "UPDATE api_configs SET oauth_token = %s, refresh_token = %s, updated_at = NOW() WHERE service = 'clio'",
                (new_access_token, new_refresh_token)
            )
            conn.commit()

            # Also update session
            session['clio_token'] = new_access_token
            session['clio_refresh_token'] = new_refresh_token

            print(f"✅ Successfully refreshed Clio token")
            cursor.close()
            conn.close()
            return new_access_token
        else:
            print(f"❌ Failed to refresh token: {response.status_code} - {response.text}")
            cursor.close()
            conn.close()
            return None

    except Exception as e:
        print(f"❌ Error refreshing Clio token: {str(e)}")
        return None

def extract_practice_area(description):
    """Extract practice area from description text - ONLY for Trust/Will Litigation"""
    if not description:
        return "Other"

    description_lower = description.lower()

    # Check ONLY for trust/will litigation keywords
    trust_will_keywords = [
        "trust litigation", "will litigation", "contest will", "contest trust",
        "contested will", "contested trust", "trust contest", "will contest",
        "vested rights", "trustee removal", "trust termination", 
        "probate", "estate litigation", "beneficiary dispute",
        "trust", "will", "estate", "inheritance", "executor", 
        "trustee", "beneficiary", "decedent", "probate court"
    ]

    for keyword in trust_will_keywords:
        if keyword in description_lower:
            return "Trust/Will Litigation"

    # If no trust/will keywords found, return "Other"
    return "Other"

def extract_matter_description(transcription):
    """Extract brief matter description: matter type and location only"""
    if not transcription:
        return ""
    
    import re
    text_lower = transcription.lower()
    parts = []
    
    # Extract matter type
    if "trust litigation" in text_lower:
        parts.append("Trust litigation")
    elif "will contest" in text_lower or "contested will" in text_lower:
        parts.append("Will contest")
    elif "estate litigation" in text_lower:
        parts.append("Estate litigation")
    elif "trust" in text_lower:
        parts.append("Trust matter")
    elif "will" in text_lower:
        parts.append("Will matter")
    elif "personal injury" in text_lower or "accident" in text_lower:
        parts.append("Personal injury")
    elif "divorce" in text_lower:
        parts.append("Divorce")
    elif "custody" in text_lower:
        parts.append("Child custody")
    elif "criminal" in text_lower:
        parts.append("Criminal matter")
    
    # Extract state/location
    state_patterns = [
        (r'\bcalifornia\b', 'California'),
        (r'\bCA\b', 'California'),
        (r'\btexas\b', 'Texas'),
        (r'\bTX\b', 'Texas'),
        (r'\bflorida\b', 'Florida'),
        (r'\bFL\b', 'Florida'),
        (r'\bnew york\b', 'New York'),
        (r'\bNY\b', 'New York'),
        (r'\bariz ona\b', 'Arizona'),
        (r'\bAZ\b', 'Arizona'),
        (r'\bnevada\b', 'Nevada'),
        (r'\bNV\b', 'Nevada'),
    ]
    
    for pattern, state_name in state_patterns:
        if re.search(pattern, transcription, re.IGNORECASE):
            parts.append(state_name)
            break
    
    # Join with " - " if we have both, or return what we have
    if len(parts) == 2:
        description = f"{parts[0]} - {parts[1]}"
    elif len(parts) == 1:
        description = parts[0]
    else:
        description = ""
    
    # Ensure within 255 char limit
    if len(description) > 255:
        description = description[:252] + "..."
    
    return description

def parse_transcription_to_case_summary(transcription):
    """
    Parse transcription to extract key case details for Trust/Will litigation cases.
    Creates a concise summary under 255 characters based on the intake questions.

    Key information to extract:
    1. Case type (Trust/Will contest, Trustee Removal, etc.)
    2. Estate value
    3. Beneficiary share value
    4. Decedent name and date of passing
    5. Trustee/Executor name
    6. Court case number if applicable
    """
    if not transcription:
        return ""

    import re

    transcription_lower = transcription.lower()
    summary_parts = []

    # 1. Extract case type
    case_type = None
    if "trust contest" in transcription_lower or "contested trust" in transcription_lower:
        case_type = "Trust Contest"
    elif "will contest" in transcription_lower or "contested will" in transcription_lower:
        case_type = "Will Contest"
    elif "trustee removal" in transcription_lower:
        case_type = "Trustee Removal"
    elif "trust termination" in transcription_lower:
        case_type = "Trust Termination"
    elif "vested rights" in transcription_lower:
        case_type = "Vested Rights"
    elif "probate" in transcription_lower:
        case_type = "Probate"
    elif "trust litigation" in transcription_lower:
        case_type = "Trust Litigation"
    elif "will litigation" in transcription_lower:
        case_type = "Will Litigation"
    elif "trust" in transcription_lower:
        case_type = "Trust Matter"
    elif "will" in transcription_lower:
        case_type = "Will Matter"

    if case_type:
        summary_parts.append(case_type)

    # 2. Extract estate value
    estate_value_patterns = [
        r"estate\s+(?:value|worth|is|of)\s+(?:approximately|about|around)?\s*\$?([\d,]+(?:\.\d+)?)\s*(?:million|mil|m|k|thousand)?",
        r"\$?([\d,]+(?:\.\d+)?)\s*(?:million|mil|m)\s+estate",
        r"estate.*\$?([\d,]+(?:\.\d+)?)\s*(?:million|mil|m|k)"
    ]

    estate_value = None
    for pattern in estate_value_patterns:
        match = re.search(pattern, transcription_lower)
        if match:
            value = match.group(1).replace(',', '')
            # Check if it mentions million
            if 'million' in match.group(0) or ' mil' in match.group(0) or ' m' in match.group(0):
                estate_value = f"${value}M estate"
            elif 'thousand' in match.group(0) or ' k' in match.group(0):
                estate_value = f"${value}K estate"
            else:
                # Try to determine if it's millions based on context
                try:
                    num_value = float(value)
                    if num_value > 1000:  # Likely in thousands
                        estate_value = f"${num_value/1000:.1f}M estate"
                    else:
                        estate_value = f"${value}M estate"
                except:
                    estate_value = f"${value} estate"
            break

    if estate_value:
        summary_parts.append(estate_value)

    # 3. Extract beneficiary share value
    share_patterns = [
        r"share\s+(?:value|worth|is|of)\s+(?:approximately|about|around)?\s*\$?([\d,]+(?:\.\d+)?)\s*(?:million|mil|m|k|thousand)?",
        r"beneficiary.*\$?([\d,]+(?:\.\d+)?)\s*(?:million|mil|m|k)"
    ]

    for pattern in share_patterns:
        match = re.search(pattern, transcription_lower)
        if match:
            value = match.group(1).replace(',', '')
            if 'million' in match.group(0) or ' mil' in match.group(0) or ' m' in match.group(0):
                summary_parts.append(f"${value}M share")
            elif 'thousand' in match.group(0) or ' k' in match.group(0):
                summary_parts.append(f"${value}K share")
            break

    # 4. Extract decedent name and date
    # Look for "decedent" or "deceased" followed by a name
    decedent_patterns = [
        r"decedent['\s]+(?:name\s+is\s+|was\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
        r"(?:my|the)\s+(?:late\s+)?(?:mother|father|parent|grandmother|grandfather|spouse|husband|wife|aunt|uncle|brother|sister)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
        r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s+(?:passed away|died|death)"
    ]

    decedent_name = None
    for pattern in decedent_patterns:
        match = re.search(pattern, transcription)  # Use original case for names
        if match:
            decedent_name = match.group(1)
            break

    if decedent_name:
        summary_parts.append(f"Re: {decedent_name}")

    # 5. Extract trustee/executor name
    trustee_patterns = [
        r"trustee['\s]+(?:name\s+is\s+|is\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)",
        r"executor['\s]+(?:name\s+is\s+|is\s+)?([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)"
    ]

    for pattern in trustee_patterns:
        match = re.search(pattern, transcription)
        if match:
            trustee_name = match.group(1)
            summary_parts.append(f"Trustee: {trustee_name}")
            break

    # 6. Extract court case number
    case_number_patterns = [
        r"case\s+(?:number|no|#)\s*[:.]?\s*([A-Z0-9-]+)",
        r"court\s+case\s+([A-Z0-9-]+)"
    ]

    for pattern in case_number_patterns:
        match = re.search(pattern, transcription)
        if match:
            case_num = match.group(1)
            summary_parts.append(f"Case: {case_num}")
            break

    # 7. Check if disinherited
    if "disinherited" in transcription_lower:
        summary_parts.append("Disinherited")

    # Join all parts with " | " separator
    if summary_parts:
        summary = " | ".join(summary_parts)
        # Ensure it's under 255 characters
        if len(summary) > 255:
            # Truncate to 252 chars and add "..."
            summary = summary[:252] + "..."
        return summary
    else:
        # Fallback: return first 250 characters of transcription
        fallback = transcription[:250] + "..." if len(transcription) > 250 else transcription
        return fallback

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
                # Also populate session
                session['clio_token'] = result[0]
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Error checking database for token: {e}")

    return f"""
    <html>
        <head>
            <title>GoHighLevel-Clio Integration</title>
            <style>
                body {{ font-family: Arial, sans-serif; max-width: 800px; margin: 50px auto; padding: 20px; }}
                .status {{ padding: 20px; border-radius: 5px; margin: 20px 0; }}
                .connected {{ background-color: #d4edda; color: #155724; }}
                .disconnected {{ background-color: #f8d7da; color: #721c24; }}
                a {{ color: #007bff; text-decoration: none; }}
                a:hover {{ text-decoration: underline; }}
                .button {{ 
                    display: inline-block; 
                    padding: 10px 20px; 
                    background-color: #007bff; 
                    color: white; 
                    border-radius: 5px; 
                    margin: 10px 0;
                }}
                .button:hover {{ background-color: #0056b3; text-decoration: none; }}
            </style>
        </head>
        <body>
            <h1>GoHighLevel → Clio Integration</h1>

            <div class="status {'connected' if clio_token else 'disconnected'}">
                <h2>Status: {'✅ Connected to Clio' if clio_token else '❌ Not Connected to Clio'}</h2>
                {f'<p>Token preview: {clio_token[:20]}...</p>' if clio_token else '<p>No token available</p>'}
            </div>

            <h2>Actions</h2>
            <a href="/authorize" class="button">{'Re-authenticate with Clio' if clio_token else 'Connect to Clio'}</a>

            <h2>Test Endpoints</h2>
            <ul>
                <li><a href="/api/test-clio">Test Clio Connection</a></li>
                <li><a href="/api/test-contact">Test Contact Creation</a></li>
            </ul>

            <h2>Webhook Endpoint</h2>
            <p>Configure this URL in GoHighLevel:</p>
            <code>https://ghl-clio-bridge-a-and-d-LawLeaders.replit.app/webhook/gohighlevel</code>
        </body>
    </html>
    """

@app.route('/authorize')
def authorize():
    """Redirect to Clio OAuth authorization"""
    auth_params = {
        'response_type': 'code',
        'client_id': CLIO_CLIENT_ID,
        'redirect_uri': CLIO_REDIRECT_URI
    }
    auth_url = f"{CLIO_AUTH_URL}?response_type={auth_params['response_type']}&client_id={auth_params['client_id']}&redirect_uri={auth_params['redirect_uri']}"
    return redirect(auth_url)

@app.route('/api/clio-callback')
def clio_callback():
    """Handle OAuth callback from Clio"""
    code = request.args.get('code')
    if not code:
        return "Error: No authorization code received", 400

    # Exchange code for token
    token_data = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': CLIO_REDIRECT_URI,
        'client_id': CLIO_CLIENT_ID,
        'client_secret': CLIO_CLIENT_SECRET
    }

    try:
        response = requests.post(CLIO_TOKEN_URL, data=token_data)
        if response.status_code == 200:
            token_info = response.json()
            access_token = token_info.get('access_token')
            refresh_token = token_info.get('refresh_token')

            # Store in session
            session['clio_token'] = access_token
            session['clio_refresh_token'] = refresh_token

            # Also store in database
            try:
                db_url = os.environ.get("DATABASE_URL")
                conn = psycopg2.connect(db_url)
                cursor = conn.cursor()

                # Check if record exists
                cursor.execute("SELECT id FROM api_configs WHERE service = 'clio'")
                exists = cursor.fetchone()

                if exists:
                    cursor.execute(
                        "UPDATE api_configs SET oauth_token = %s, refresh_token = %s, updated_at = NOW() WHERE service = 'clio'",
                        (access_token, refresh_token)
                    )
                else:
                    cursor.execute(
                        "INSERT INTO api_configs (service, oauth_token, refresh_token) VALUES ('clio', %s, %s)",
                        (access_token, refresh_token)
                    )

                conn.commit()
                cursor.close()
                conn.close()
                print("✅ Token successfully saved to database")
            except Exception as e:
                print(f"❌ Error saving token to database: {e}")

            return redirect('/')
        else:
            return f"Error exchanging code for token: {response.text}", 400
    except Exception as e:
        return f"Exception during OAuth: {str(e)}", 500

@app.route('/api/test-clio')
def test_clio():
    """Test Clio API connection"""
    token = session.get('clio_token') or get_token_from_db()
    if not token:
        return jsonify({"error": "No Clio token available. Please authorize first."}), 401

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(f"{CLIO_API_BASE}/users/who_am_i", headers=headers, timeout=10)

        if response.status_code == 401:
            # Try to refresh token
            new_token = refresh_clio_token()
            if new_token:
                headers["Authorization"] = f"Bearer {new_token}"
                response = requests.get(f"{CLIO_API_BASE}/users/who_am_i", headers=headers, timeout=10)
            else:
                return jsonify({"error": "Token expired and refresh failed"}), 401

        return jsonify({
            "status": response.status_code,
            "response": response.json() if response.status_code == 200 else response.text
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

def get_token_from_db():
    """Helper function to get token from database"""
    try:
        db_url = os.environ.get("DATABASE_URL")
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        cursor.execute("SELECT oauth_token FROM api_configs WHERE service = 'clio' AND oauth_token IS NOT NULL LIMIT 1")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return result[0] if result else None
    except Exception as e:
        print(f"Error getting token from database: {e}")
        return None

@app.route('/api/ghl-webhook-live', methods=['POST'])
def ghl_webhook_live():
    """Live webhook endpoint for GoHighLevel - same as /webhook/gohighlevel"""
    try:
        # Get JSON data from GoHighLevel
        data = request.get_json()

        print("=" * 50)
        print("📥 Received webhook from GoHighLevel (LIVE)")
        print(f"Full payload: {json.dumps(data, indent=2)}")
        print("=" * 50)

        # Extract contact information
        name = data.get('name', data.get('contact', {}).get('name', ''))
        email = data.get('email', data.get('contact', {}).get('email', ''))
        phone = data.get('phone', data.get('contact', {}).get('phone', ''))
        state = data.get('state', data.get('contact', {}).get('state', ''))

        # Extract transcription for case description
        transcription = data.get('transcription', '')
        if not transcription and 'customData' in data:
            transcription = data.get('customData', {}).get('transcription', '')

        # Extract brief description (matter type + location) for Clio description field
        brief_description = extract_matter_description(transcription)
        
        # FORCE truncation to be safe - Clio has 255 char limit
        if brief_description and len(brief_description) > 255:
            brief_description = brief_description[:252] + "..."
        
        # If extraction failed, use a safe default
        if not brief_description:
            brief_description = "New matter from Law Leaders/Legal Navigator"
        
        # Keep full transcription for Clio notes (65K char limit)
        full_transcription = transcription

        # Extract practice area based on transcription
        practice_area = extract_practice_area(transcription)

        print(f"📋 Extracted Info:")
        print(f"  Name: {name}")
        print(f"  Email: {email}")
        print(f"  Phone: {phone}")
        print(f"  State: {state}")
        print(f"  Practice Area: {practice_area}")
        print(f"  Brief Description ({len(brief_description)} chars): {brief_description}")
        print(f"  Full Transcription Length: {len(full_transcription)} chars")

        # Validate required fields
        if not name:
            return jsonify({"error": "Name is required"}), 400

        # Get Clio token
        token = session.get('clio_token') or get_token_from_db()
        if not token:
            return jsonify({"error": "Not authenticated with Clio"}), 401

        # Step 1: Create contact in Clio
        print("\n🔄 Creating contact in Clio...")
        contact_result = create_clio_contact(name, email, phone, state, token)

        if "error" in contact_result:
            print(f"❌ Contact creation failed: {contact_result}")
            return jsonify({
                "status": "error",
                "message": "Data forwarded to Clio",
                "clio_contact": contact_result,
                "clio_matter": {"error": "Contact creation failed"}
            }), 400

        print(f"✅ Contact created: {json.dumps(contact_result, indent=2)}")

        # Step 2: Create matter in Clio with brief description and full transcription note
        print("\n🔄 Creating matter in Clio...")
        matter_result = create_clio_matter(
            contact_result, 
            practice_area, 
            brief_description,  # Brief description (matter type + location)
            full_transcription,  # Full transcription goes to notes
            token
        )

        if "error" in matter_result:
            print(f"❌ Matter creation failed: {matter_result}")
            return jsonify({
                "status": "success",
                "message": "Data forwarded to Clio",
                "clio_contact": contact_result,
                "clio_matter": matter_result
            }), 200

        print(f"✅ Matter created: {json.dumps(matter_result, indent=2)}")

        # Return success response in the format GHL expects
        return jsonify({
            "status": "success",
            "message": "Data forwarded to Clio",
            "clio_contact": contact_result,
            "clio_matter": matter_result
        }), 200

    except Exception as e:
        print(f"❌ Exception in webhook: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Exception: {str(e)}"}), 500

@app.route('/webhook/gohighlevel', methods=['POST'])
def gohighlevel_webhook():
    """Main webhook endpoint for GoHighLevel"""
    try:
        # Get JSON data from GoHighLevel
        data = request.get_json()

        print("=" * 50)
        print("📥 Received webhook from GoHighLevel")
        print(f"Full payload: {json.dumps(data, indent=2)}")
        print("=" * 50)

        # Extract contact information
        name = data.get('name', data.get('contact', {}).get('name', ''))
        email = data.get('email', data.get('contact', {}).get('email', ''))
        phone = data.get('phone', data.get('contact', {}).get('phone', ''))
        state = data.get('state', data.get('contact', {}).get('state', ''))

        # Extract transcription for case description
        transcription = data.get('transcription', '')
        if not transcription and 'customData' in data:
            transcription = data.get('customData', {}).get('transcription', '')

        # Extract brief description (matter type + location) for Clio description field
        brief_description = extract_matter_description(transcription)
        
        # FORCE truncation to be safe - Clio has 255 char limit
        if brief_description and len(brief_description) > 255:
            brief_description = brief_description[:252] + "..."
        
        # If extraction failed, use a safe default
        if not brief_description:
            brief_description = "New matter from Law Leaders/Legal Navigator"
        
        # Keep full transcription for Clio notes (65K char limit)
        full_transcription = transcription

        # Extract practice area based on transcription
        practice_area = extract_practice_area(transcription)

        print(f"📋 Extracted Info:")
        print(f"  Name: {name}")
        print(f"  Email: {email}")
        print(f"  Phone: {phone}")
        print(f"  State: {state}")
        print(f"  Practice Area: {practice_area}")
        print(f"  Brief Description ({len(brief_description)} chars): {brief_description}")
        print(f"  Full Transcription Length: {len(full_transcription)} chars")

        # Validate required fields
        if not name:
            return jsonify({"error": "Name is required"}), 400

        # Get Clio token
        token = session.get('clio_token') or get_token_from_db()
        if not token:
            return jsonify({"error": "Not authenticated with Clio"}), 401

        # Step 1: Create contact in Clio
        print("\n🔄 Creating contact in Clio...")
        contact_result = create_clio_contact(name, email, phone, state, token)

        if "error" in contact_result:
            print(f"❌ Contact creation failed: {contact_result}")
            return jsonify(contact_result), 400

        print(f"✅ Contact created: {json.dumps(contact_result, indent=2)}")

        # Step 2: Create matter in Clio with brief description and full transcription note
        print("\n🔄 Creating matter in Clio...")
        matter_result = create_clio_matter(
            contact_result, 
            practice_area, 
            brief_description,  # Brief description (matter type + location)
            full_transcription,  # Full transcription goes to notes
            token
        )

        if "error" in matter_result:
            print(f"❌ Matter creation failed: {matter_result}")
            return jsonify({
                "contact": contact_result,
                "matter_error": matter_result
            }), 400

        print(f"✅ Matter created: {json.dumps(matter_result, indent=2)}")

        # Return success response
        return jsonify({
            "status": "success",
            "message": "Contact and matter created successfully in Clio",
            "contact": contact_result,
            "matter": matter_result,
            "practice_area": practice_area,
            "brief_description": brief_description,
            "transcription_length": len(full_transcription)
        }), 200

    except Exception as e:
        print(f"❌ Exception in webhook: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"Exception: {str(e)}"}), 500

def create_clio_contact(name, email=None, phone=None, state=None, token=None):
    """Create a contact in Clio"""
    import requests
    import json
    from flask import session

    # Get authentication token
    auth_token = token or session.get('clio_token', '')
    if not auth_token:
        return {"error": "No Clio authentication token available"}

    # Set up the request
    contacts_url = f"{CLIO_API_BASE}/contacts"
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # Build contact data
    contact_data = {
        "data": {
            "type": "Person",
            "first_name": name.split()[0] if name else "",
            "last_name": " ".join(name.split()[1:]) if len(name.split()) > 1 else ""
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
        elif response.status_code == 401:
            # Token expired - try to refresh automatically
            print("🔄 Token expired (401), attempting auto-refresh...")
            new_token = refresh_clio_token()

            if new_token:
                # Retry with new token
                print("🔄 Retrying contact creation with refreshed token...")
                headers["Authorization"] = f"Bearer {new_token}"
                retry_response = requests.post(
                    contacts_url,
                    headers=headers,
                    json=contact_data,
                    timeout=20
                )

                if retry_response.status_code in [200, 201]:
                    print("✅ Successfully created contact after token refresh")
                    return retry_response.json()
                else:
                    print(f"❌ Failed even after token refresh. Status: {retry_response.status_code}")
                    return {
                        "error": f"Failed to create contact even after token refresh. Status: {retry_response.status_code}",
                        "response_body": retry_response.text,
                        "request_data": contact_data
                    }
            else:
                print("❌ Could not refresh token")
                return {
                    "error": "Token expired and could not be refreshed automatically",
                    "response_body": response.text,
                    "request_data": contact_data
                }
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

def create_clio_matter(contact_data, practice_area, description, full_transcription="", token=None):
    """Create a matter in Clio and add full transcription as a note"""
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

    # Ensure description is under 255 characters (Clio's limit)
    if description and len(description) > 255:
        description = description[:252] + "..."

    # Use the correct Clio API format - based on their documentation
    matter_data = {
        "data": {
            "type": "Matter",
            "client": {
                "id": str(contact_id)
            },
            "display_number": f"GHL-{contact_id}",
            "description": description if description else "",
            "status": "Pending",
            "practice_area": practice_area or "General"
        }
    }

    try:
        print(f"📤 Creating matter with data: {json.dumps(matter_data, indent=2)}")
        print(f"📏 Description length: {len(description)} characters")

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
            matter_result = response.json()
            matter_id = matter_result.get("data", {}).get("id")
            
            # Create a note with the full transcription if available
            if full_transcription and matter_id:
                print(f"📝 Adding full transcription as note ({len(full_transcription)} chars)...")
                note_data = {
                    "data": {
                        "type": "Matter",
                        "subject": "Call Transcription",
                        "detail": full_transcription,
                        "matter": {
                            "id": matter_id
                        }
                    }
                }
                
                note_response = requests.post(
                    f"{CLIO_API_BASE}/notes",
                    headers=headers,
                    json=note_data,
                    timeout=20
                )
                
                if note_response.status_code in [200, 201]:
                    print("✅ Successfully added transcription note to matter")
                else:
                    print(f"⚠️ Failed to add note: {note_response.status_code} - {note_response.text}")
            
            return matter_result
        elif response.status_code == 401:
            # Token expired - try to refresh automatically
            print("🔄 Token expired (401), attempting auto-refresh...")
            new_token = refresh_clio_token()

            if new_token:
                # Retry with new token
                print("🔄 Retrying matter creation with refreshed token...")
                headers["Authorization"] = f"Bearer {new_token}"
                retry_response = requests.post(
                    f"{CLIO_API_BASE}/matters",
                    headers=headers,
                    json=matter_data,
                    timeout=20
                )

                if retry_response.status_code in [200, 201]:
                    print("✅ Successfully created matter after token refresh")
                    return retry_response.json()
                else:
                    print(f"❌ Failed even after token refresh. Status: {retry_response.status_code}")
                    return {
                        "error": f"Failed to create matter even after token refresh. Status: {retry_response.status_code}",
                        "response_body": retry_response.text,
                        "contact_id": contact_id
                    }
            else:
                print("❌ Could not refresh token")
                return {
                    "error": "Token expired and could not be refreshed automatically",
                    "response_body": response.text,
                    "contact_id": contact_id
                }
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
                        "description": description if description else "",
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

