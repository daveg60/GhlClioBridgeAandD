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
    """Extract practice area from description text - EXPANDED for all legal matters"""
    if not description:
        return "Other"

    description_lower = description.lower()

    # Personal Injury Law
    personal_injury_keywords = [
        "personal injury", "accident", "injury", "hurt", "slip and fall", 
        "car accident", "auto accident", "motor vehicle", "medical malpractice", 
        "wrongful death", "premises liability", "product liability", "dog bite",
        "bicycle accident", "motorcycle accident", "pedestrian accident",
        "nursing home abuse", "construction accident", "workplace injury"
    ]
    for keyword in personal_injury_keywords:
        if keyword in description_lower:
            return "Personal Injury"

    # Family Law
    family_law_keywords = [
        "divorce", "custody", "child support", "alimony", "spousal support",
        "marriage", "separation", "adoption", "family", "spouse", "prenup",
        "prenuptial", "domestic violence", "restraining order", "paternity",
        "visitation", "guardianship", "child custody", "domestic relations"
    ]
    for keyword in family_law_keywords:
        if keyword in description_lower:
            return "Family Law"

    # Criminal Law
    criminal_law_keywords = [
        "criminal", "arrest", "arrested", "charge", "charged", "offense", 
        "crime", "dui", "dwi", "owi", "theft", "assault", "battery",
        "probation", "jail", "prison", "felony", "misdemeanor", "warrant",
        "drug", "trafficking", "possession", "domestic violence", "fraud",
        "embezzlement", "burglary", "robbery", "homicide", "manslaughter"
    ]
    for keyword in criminal_law_keywords:
        if keyword in description_lower:
            return "Criminal Law"

    # Estate Planning & Probate
    estate_planning_keywords = [
        "estate", "will", "trust", "inheritance", "probate", "executor",
        "beneficiary", "death", "asset", "living will", "power of attorney",
        "estate planning", "succession", "heir", "testamentary", "guardian",
        "conservatorship", "elder law", "medicaid planning"
    ]
    for keyword in estate_planning_keywords:
        if keyword in description_lower:
            return "Estate Planning"

    # Real Estate Law
    real_estate_keywords = [
        "real estate", "property", "house", "home", "closing", "deed",
        "title", "mortgage", "foreclosure", "landlord", "tenant", "lease",
        "eviction", "zoning", "easement", "boundary", "construction",
        "homeowners association", "hoa", "purchase agreement"
    ]
    for keyword in real_estate_keywords:
        if keyword in description_lower:
            return "Real Estate"

    # Business Law
    business_law_keywords = [
        "business", "contract", "llc", "corporation", "partnership",
        "employment", "fired", "wrongful termination", "discrimination",
        "harassment", "wage", "overtime", "breach of contract", "lawsuit",
        "commercial", "intellectual property", "trademark", "copyright",
        "non-compete", "partnership dispute", "shareholder"
    ]
    for keyword in business_law_keywords:
        if keyword in description_lower:
            return "Business Law"

    # Immigration Law
    immigration_keywords = [
        "immigration", "visa", "green card", "citizenship", "deportation",
        "asylum", "refugee", "work permit", "naturalization", "ice",
        "immigration court", "removal proceedings", "family petition"
    ]
    for keyword in immigration_keywords:
        if keyword in description_lower:
            return "Immigration"

    # Bankruptcy Law
    bankruptcy_keywords = [
        "bankruptcy", "chapter 7", "chapter 13", "debt", "foreclosure",
        "creditor", "discharge", "filing bankruptcy", "debt relief"
    ]
    for keyword in bankruptcy_keywords:
        if keyword in description_lower:
            return "Bankruptcy"

    # Social Security Disability
    disability_keywords = [
        "disability", "social security", "ssdi", "ssi", "disabled",
        "disability benefits", "social security disability"
    ]
    for keyword in disability_keywords:
        if keyword in description_lower:
            return "Social Security Disability"

    # Workers' Compensation
    workers_comp_keywords = [
        "workers compensation", "workers comp", "work injury", 
        "on the job injury", "workplace accident", "injured at work"
    ]
    for keyword in workers_comp_keywords:
        if keyword in description_lower:
            return "Workers' Compensation"

    # Civil Rights
    civil_rights_keywords = [
        "civil rights", "discrimination", "police brutality", "excessive force",
        "constitutional rights", "section 1983", "civil lawsuit"
    ]
    for keyword in civil_rights_keywords:
        if keyword in description_lower:
            return "Civil Rights"

    # Tax Law
    tax_keywords = [
        "tax", "irs", "tax debt", "tax lien", "tax levy", "audit",
        "tax resolution", "offer in compromise", "innocent spouse"
    ]
    for keyword in tax_keywords:
        if keyword in description_lower:
            return "Tax Law"

    # If no match is found, return "General"
    return "General"
def summarize_transcript(transcription, max_length=200):
    """
    Create a concise summary of the transcript for matter description
    """
    if not transcription or len(transcription) <= max_length:
        return transcription

    import re

    # Clean up the transcript and separate human vs bot lines
    lines = transcription.split('\n')
    human_lines = []
    bot_lines = []

    for line in lines:
        if 'human:' in line.lower():
            # Remove "human:" prefix and clean
            clean_line = re.sub(r'^human:\s*', '', line, flags=re.IGNORECASE).strip()
            if clean_line:
                human_lines.append(clean_line)
        elif 'bot:' in line.lower():
            clean_line = re.sub(r'^bot:\s*', '', line, flags=re.IGNORECASE).strip()
            if clean_line:
                bot_lines.append(clean_line)

    # Focus on human lines first - this is where the legal issue will be
    human_text = " ".join(human_lines)

    # Look for the main legal issue from human speech
    legal_issue_patterns = [
        r"(I need help with .+?)[\.\!\?]",
        r"(I want to .+?)[\.\!\?]",
        r"(I was .+?)[\.\!\?]", 
        r"(I have been .+?)[\.\!\?]",
        r"(My .+ and I .+?)[\.\!\?]",  # "My husband and I are getting divorced"
        r"(My .+?)[\.\!\?]",
        r"(There was .+?)[\.\!\?]",
        r"(Someone .+?)[\.\!\?]",
        r"(I got .+?)[\.\!\?]",
        r"(I am .+?)[\.\!\?]"
    ]

    main_issue = ""
    for pattern in legal_issue_patterns:
        match = re.search(pattern, human_text, re.IGNORECASE)
        if match:
            potential_issue = match.group(1).strip()
            # Filter out administrative/contact info statements
            if not any(admin_word in potential_issue.lower() for admin_word in 
                      ['name is', 'phone number', 'email', 'address', 'calling about', 'contact']):
                main_issue = potential_issue
                break

    # If no clear issue found, look for legal keywords in human text
    if not main_issue:
        # Look for specific legal situations
        legal_keywords = {
            'divorce': 'seeking divorce assistance',
            'custody': 'need help with child custody',
            'accident': 'involved in an accident',
            'injured': 'sustained injuries',
            'arrested': 'facing criminal charges',
            'fired': 'employment issue',
            'will': 'estate planning matter',
            'sued': 'involved in litigation',
            'bankruptcy': 'bankruptcy consultation',
            'disability': 'disability benefits matter',
            'immigration': 'immigration issue',
            'tax': 'tax matter',
            'contract': 'contract dispute',
            'real estate': 'real estate matter'
        }

        for keyword, description in legal_keywords.items():
            if keyword in human_text.lower():
                main_issue = description
                break

    # Look for additional context details
    details = []

    # Timeframes
    time_patterns = [
        r"(last week|yesterday|today|last month|this week|recently|[A-Za-z]+ \d+)",
        r"(\d+ (days|weeks|months|years) ago)"
    ]

    for pattern in time_patterns:
        match = re.search(pattern, human_text, re.IGNORECASE)
        if match:
            details.append(match.group(1))
            break

    # Specific legal context from human speech
    context_keywords = [
        "accident", "injury", "divorce", "custody", "arrested", "fired", 
        "sued", "died", "will", "estate", "contract", "property", "bankruptcy",
        "disability", "immigration", "tax"
    ]
    for keyword in context_keywords:
        if keyword.lower() in human_text.lower():
            if f"involving {keyword}" not in details:  # Avoid duplicates
                details.append(f"involving {keyword}")
            break

    # Build the final summary
    summary_parts = []

    if main_issue:
        summary_parts.append(main_issue)
    elif human_text:
        # Fallback: use first substantial human statement
        first_substantial = ""
        for line in human_lines:
            if len(line) > 10 and not any(admin in line.lower() for admin in 
                                        ['name is', 'phone', 'email', 'address']):
                first_substantial = line
                break
        if first_substantial:
            summary_parts.append(first_substantial[:100])

    if details:
        summary_parts.append(f"({', '.join(details)})")

    summary = " ".join(summary_parts)

    # If still too long, truncate intelligently
    if len(summary) > max_length:
        if '(' in summary:
            # Keep main issue, truncate details
            main_part = summary.split('(')[0].strip()
            if len(main_part) <= max_length - 3:
                summary = main_part
            else:
                summary = main_part[:max_length-3] + "..."
        else:
            # Truncate at sentence boundary
            sentences = summary.split('.')
            summary = sentences[0]
            if len(summary) > max_length:
                summary = summary[:max_length-3] + "..."

    # Final fallback
    if not summary or len(summary) < 10:
        summary = "Legal consultation request from GoHighLevel"

    return summary


def extract_caller_info_from_transcript(transcription):
    """Extract caller name, phone, email from transcript text"""
    import re

    caller_info = {
        "name": "",
        "phone": "", 
        "email": ""
    }
    
    # For debugging
    print(f"Extracting info from transcript: {transcription[:100]}...")

    if not transcription:
        return caller_info

    # First try to directly detect names from dialog format
    # Look for dialog with the person's name mentioned by the bot
    name_from_dialogue = None
    lines = transcription.split('\n')
    for i, line in enumerate(lines):
        if i > 0 and 'bot:' in line.lower() and 'thanks' in line.lower():
            # Look for patterns like "Thanks Jennifer."
            thanks_match = re.search(r'[Tt]hanks\s+([A-Za-z]+)[\.!\s]', line)
            if thanks_match:
                name_from_dialogue = thanks_match.group(1)
                break
    
    # If we found a first name from dialogue, try to find the full name
    full_name = ""
    if name_from_dialogue:
        # Look for the full name in human lines
        for line in lines:
            if 'human:' in line.lower() and 'name is' in line.lower() and name_from_dialogue.lower() in line.lower():
                name_match = re.search(r'[Mm]y name is ([A-Za-z\s]+)', line)
                if name_match:
                    full_name = name_match.group(1).strip()
                    break
    
    # If we found a full name, use it
    if full_name:
        caller_info["name"] = full_name
    elif name_from_dialogue:
        # Just use the first name if that's all we found
        caller_info["name"] = name_from_dialogue
    else:
        # Fall back to standard patterns
        name_patterns = [
            r"[Mm]y name is ([A-Za-z\s]+)[\.|\,]",   # Matches "My name is Jennifer Parker."
            r"[Mm]y name is ([A-Za-z\s]+)",          # Fallback without punctuation
            r"[Tt]his is ([A-Za-z\s]+)",             # Fallback "This is John Smith"
            r"[Ii]'m ([A-Za-z\s]+)",                 # Fallback "I'm John Smith"
            r"[Cc]all me ([A-Za-z\s]+)"              # Fallback "Call me John"
        ]
        
        for pattern in name_patterns:
            for line in lines:
                if 'human:' in line.lower():
                    match = re.search(pattern, line)
                    if match:
                        caller_info["name"] = match.group(1).strip()
                        break
            if caller_info["name"]:
                break
    
    # Process the name to get first and last name properly
    if caller_info["name"]:
        # Title case and clean up extra spaces
        caller_info["name"] = " ".join([word.capitalize() for word in caller_info["name"].split()])
        print(f"✓ Successfully extracted name: {caller_info['name']}")
    else:
        print("⚠ Could not extract a name from the transcript")

    # Look for phone patterns
    phone_pattern = r"(\d{3}[-.]?\d{3}[-.]?\d{4})"
    phone_match = re.search(phone_pattern, transcription)
    if phone_match:
        caller_info["phone"] = phone_match.group(1)

    # Look for email patterns  
    email_pattern = r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"
    email_match = re.search(email_pattern, transcription.lower())
    if email_match:
        caller_info["email"] = email_match.group(1)

    return caller_info
def should_create_matter(transcription):
    """
    Check if the AI agent rejected the case based on transcript
    """
    if not transcription:
        return True, "No transcript to analyze"

    rejection_phrases = [
        "i'm sorry, we only handle",
        "i'm sorry, but we"
    ]

    transcript_lower = transcription.lower()

    for phrase in rejection_phrases:
        if phrase in transcript_lower:
            return False, "Case rejected by AI agent"

    return True, "Case accepted"
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

        # Extract transcription first
        transcription = data.get("transcription", "")

        # Also check if transcription is in customData
        if not transcription and "customData" in data and isinstance(data["customData"], dict):
            transcription = data["customData"].get("transcription", "")

        # CHECK FOR REJECTION FIRST - before any processing
        should_create, reason = should_create_matter(transcription)
        if not should_create:
            print(f"🚫 Not creating matter: {reason}")
            return jsonify({
                "status": "success",
                "message": "Call handled - case rejected by AI agent"
            })

        print("✅ Case accepted - proceeding with contact/matter creation")

        # Extract caller info from transcript
        caller_info = extract_caller_info_from_transcript(transcription)

        # Use extracted info or fall back to webhook data (with proper title case)
        full_name = caller_info["name"] or data.get("full_name", "").title()
        email = caller_info["email"] or data.get("email", "")
        phone = caller_info["phone"] or data.get("phone", "")
        case_description = ""
        state = data.get("state", "")

        # Process full name into first and last name for Clio API
        first_name = ""
        last_name = ""
        if full_name:
            name_parts = full_name.split()
            if len(name_parts) > 0:
                first_name = name_parts[0]
                if len(name_parts) > 1:
                    last_name = " ".join(name_parts[1:])
            print(f"✓ Processed name: {first_name} {last_name}")

        # Try to extract case description from customData
        if "customData" in data and isinstance(data["customData"], dict):
            custom_data = data["customData"]
            if not full_name:
                full_name = custom_data.get("full_name", "").title()
            if not email:
                email = custom_data.get("email", "")
            if not phone:
                phone = custom_data.get("phone", "")
            case_description = custom_data.get("case_description", "")

        # Use transcription as case description if no explicit case description provided
        if not case_description and transcription:
            case_description = transcription
            print("📝 Using transcription as case description")

        # Extract practice area from case description or transcription
        practice_area = extract_practice_area(case_description)
        print(f"📋 Detected practice area: {practice_area}")

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
            contact_data = create_clio_contact(full_name, email, phone, state, token=clio_token, first_name=first_name, last_name=last_name)

            # Create matter in Clio
            matter_data = create_clio_matter(contact_data, practice_area, case_description, token=clio_token)

            return jsonify({
                "status": "success",
                "message": "Data forwarded to Clio",
                "clio_contact": contact_data,
                "clio_matter": matter_data,
                "practice_area": practice_area
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
def create_clio_contact(full_name, email, phone, state=None, token=None, first_name=None, last_name=None):
    """Create a contact in Clio using the Clio API documentation format"""
    import requests
    import json
    import hashlib
    from datetime import datetime
    from flask import session
    
    # Use provided first/last name if available, otherwise parse from full_name
    if not first_name and not last_name and full_name:
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
    """Create a matter in Clio using the correct API format"""
    import requests
    import json
    from flask import session

    # Summarize the transcript if it's too long
    if description and len(description) > 255:
        summarized_description = summarize_transcript(description, max_length=240)
        print(f"📝 Original length: {len(description)}")
        print(f"📝 Summarized: {summarized_description}")
        description = summarized_description

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