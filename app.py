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
    """Extract caller name, phone, email from transcript text - handles ALL formats"""
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

    # Split into lines for easier processing
    lines = transcription.split('\n')

    # Look for name patterns - more specific now
    name_patterns = [
        r"[Mm]y name is ([A-Za-z\s]+)",               # "My name is David Glick"
        r"[Ii]t'?s ([A-Za-z\s]+)",                    # "It's David Glick" 
        r"[Tt]his is ([A-Za-z\s]+)",                  # "This is David Glick"
        r"[Ii]'m ([A-Za-z\s]+)",                      # "I'm David Glick"
        r"[Cc]all me ([A-Za-z\s]+)"                   # "Call me David"
    ]

    # Look for the name in ANY human/caller line - handle ALL formats we've seen
    for line in lines:
        line = line.strip()

        # Check if this is a human/caller line (handle multiple formats)
        is_human_line = (
            line.lower().startswith('human:') or 
            line.lower().startswith('caller:') or
            line.lower().startswith('**caller:') or
            '**caller:**' in line.lower() or
            'caller:**' in line.lower()
        )

        if is_human_line:
            # Clean the line - remove ALL prefixes we've seen
            clean_line = line
            clean_line = re.sub(r'^\*+\s*caller:\s*', '', clean_line, flags=re.IGNORECASE)
            clean_line = re.sub(r'^caller:\s*', '', clean_line, flags=re.IGNORECASE)  
            clean_line = re.sub(r'^human:\s*', '', clean_line, flags=re.IGNORECASE)
            clean_line = re.sub(r'^\*+', '', clean_line).strip()

            print(f"🔍 Checking human/caller line: '{clean_line}'")

            for pattern in name_patterns:
                match = re.search(pattern, clean_line, re.IGNORECASE)
                if match:
                    potential_name = match.group(1).strip()

                    # Filter out common false positives
                    false_positives = [
                        'not sure', 'not sure what', 'good', 'fine', 'okay', 'ok',
                        'yes', 'no', 'yeah', 'yep', 'sure', 'right', 'correct',
                        'that', 'this', 'here', 'there', 'help', 'calling',
                        'having trouble', 'trouble with', 'need help', 'looking for'
                    ]

                    # Check if it's a false positive
                    is_false_positive = False
                    for fp in false_positives:
                        if fp in potential_name.lower():
                            is_false_positive = True
                            break

                    if not is_false_positive and len(potential_name) > 1:
                        # Additional validation: should be a proper name
                        words = potential_name.split()
                        if len(words) >= 1:  # Accept single names too
                            # Remove trailing commas and clean up
                            clean_name = re.sub(r',.*$', '', potential_name).strip()
                            caller_info["name"] = clean_name.title()
                            print(f"✓ Successfully extracted name: {caller_info['name']}")
                            break

            # If we found a name, break out of the outer loop too
            if caller_info["name"]:
                break

    # If still no name found, try alternative approach - look for bot/AI asking for name
    if not caller_info["name"]:
        print("🔍 Trying alternative name extraction methods...")

        # Look for patterns where bot/AI agent asks for name and human responds
        for i, line in enumerate(lines):
            line = line.strip()

            # Check if bot/AI is asking for name
            is_bot_asking = (
                ('bot:' in line.lower() or 'ai agent:' in line.lower()) and 
                ('name' in line.lower() or 'could i have' in line.lower())
            )

            if is_bot_asking:
                print(f"🔍 Found bot/AI asking for name: '{line}'")

                # Look at the next human response
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    print(f"🔍 Next line: '{next_line}'")

                    # Check if next line is human response
                    is_human_response = (
                        next_line.lower().startswith('human:') or 
                        next_line.lower().startswith('caller:') or
                        '**caller:**' in next_line.lower()
                    )

                    if is_human_response:
                        # Clean the response
                        clean_response = next_line
                        clean_response = re.sub(r'^\*+\s*caller:\s*', '', clean_response, flags=re.IGNORECASE)
                        clean_response = re.sub(r'^caller:\s*', '', clean_response, flags=re.IGNORECASE)
                        clean_response = re.sub(r'^human:\s*', '', clean_response, flags=re.IGNORECASE)
                        clean_response = re.sub(r'^\*+', '', clean_response).strip()

                        print(f"🔍 Clean human response: '{clean_response}'")

                        # Try to extract name from this response
                        for pattern in name_patterns:
                            match = re.search(pattern, clean_response, re.IGNORECASE)
                            if match:
                                potential_name = match.group(1).strip()

                                # Check if it's a false positive
                                is_false_positive = False
                                false_positives = [
                                    'not sure', 'not sure what', 'having trouble', 'trouble with',
                                    'need help', 'looking for', 'yes', 'no', 'yeah'
                                ]
                                for fp in false_positives:
                                    if fp in potential_name.lower():
                                        is_false_positive = True
                                        break

                                if not is_false_positive and len(potential_name) > 1:
                                    clean_name = re.sub(r',.*$', '', potential_name).strip()
                                    caller_info["name"] = clean_name.title()
                                    print(f"✓ Found name in response to bot/AI question: {caller_info['name']}")
                                    break

                        if caller_info["name"]:
                            break

    # Final fallback: look for direct name patterns anywhere in transcript
    if not caller_info["name"]:
        print("🔍 Final fallback: looking for direct name patterns...")

        # Look for "My name is" anywhere in the transcript
        for pattern in name_patterns:
            match = re.search(pattern, transcription, re.IGNORECASE)
            if match:
                potential_name = match.group(1).strip()

                # Same validation as before
                false_positives = [
                    'not sure', 'not sure what', 'having trouble', 'trouble with',
                    'need help', 'looking for', 'yes', 'no', 'yeah'
                ]

                is_false_positive = False
                for fp in false_positives:
                    if fp in potential_name.lower():
                        is_false_positive = True
                        break

                if not is_false_positive and len(potential_name) > 1:
                    clean_name = re.sub(r',.*$', '', potential_name).strip()
                    caller_info["name"] = clean_name.title()
                    print(f"✓ Found name with fallback method: {caller_info['name']}")
                    break

    if not caller_info["name"]:
        print("⚠ Could not extract a name from the transcript")

    # Look for phone patterns (keep this the same)
    phone_patterns = [
        r"(\+?1?\s*\(?\d{3}\)?\s*[-.\s]?\d{3}\s*[-.\s]?\d{4})",
        r"(\d{3}\s+\d{3}\s+\d{4})",
        r"(\d{10})"
    ]

    for pattern in phone_patterns:
        match = re.search(pattern, transcription)
        if match:
            phone = match.group(1)
            phone = re.sub(r'[^\d+]', '', phone)
            if phone.startswith('1') and len(phone) == 11:
                phone = phone[1:]
            if len(phone) == 10:
                caller_info["phone"] = f"({phone[:3]}) {phone[3:6]}-{phone[6:]}"
                print(f"✓ Extracted phone: {caller_info['phone']}")
                break

    # Look for email patterns  
    email_pattern = r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})"
    email_match = re.search(email_pattern, transcription.lower())
    if email_match:
        caller_info["email"] = email_match.group(1)
        print(f"✓ Extracted email: {caller_info['email']}")

    print(f"📋 Final extraction results: {caller_info}")
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

def debug_webhook_data(data):
    """Helper function to debug incoming webhook data"""
    print("🔍 DEBUGGING WEBHOOK DATA:")
    print(f"Raw data keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")

    if isinstance(data, dict):
        for key, value in data.items():
            if isinstance(value, (str, int, float, bool)):
                print(f"  {key}: {value}")
            elif isinstance(value, dict):
                print(f"  {key}: (dict with {len(value)} keys)")
                for subkey in value.keys():
                    print(f"    - {subkey}")
            elif isinstance(value, list):
                print(f"  {key}: (list with {len(value)} items)")
            else:
                print(f"  {key}: {type(value)}")

    print("🔍 END DEBUG")
    return data
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
        debug_webhook_data(data)
        # Extract transcription first
        transcription = data.get("transcription", "")

        # Also check if transcription is in customData
        if not transcription and "customData" in data and isinstance(data["customData"], dict):
            transcription = data["customData"].get("transcription", "")
        print("=" * 80)
        print("🔍 TRANSCRIPT DEBUG:")
        print(f"Raw transcription length: {len(transcription) if transcription else 0}")
        if transcription:
            print("Raw transcription content:")
            print(repr(transcription))  # This shows exact content including \n, spaces, etc.
            print("\nFirst 500 characters:")
            print(transcription[:500])
            print("\nSplit by lines:")
            lines = transcription.split('\n')
            for i, line in enumerate(lines[:10]):  # Show first 10 lines
                print(f"Line {i}: {repr(line)}")
        else:
            print("❌ NO TRANSCRIPTION FOUND!")
            print("Available data keys:", list(data.keys()))
            if "customData" in data:
                print("CustomData keys:", list(data["customData"].keys()) if isinstance(data["customData"], dict) else "Not a dict")
        print("=" * 80)
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
                # Prepare address data for the new function
                address_data = {
                    "state": state,
                    "country": "US"
                }

                # Create contact in Clio
                contact_data = create_clio_contact(full_name, phone, email, address_data)

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
def create_clio_contact(caller_name, phone, email="", address_data=None):
        """Create a contact in Clio - FIXED VERSION"""

        # Split the name properly to satisfy Clio's requirements
        first_name = ""
        last_name = ""

        if caller_name and caller_name.strip():
            name_parts = caller_name.strip().split()
            if len(name_parts) == 1:
                first_name = name_parts[0]
                last_name = "."  # Clio requires at least one name, use placeholder
            elif len(name_parts) >= 2:
                first_name = name_parts[0]
                last_name = " ".join(name_parts[1:])
        else:
            # If no name extracted, use placeholder names
            first_name = "Unknown"
            last_name = "Caller"

        print(f"📋 Creating contact: {first_name} {last_name}")

        # Prepare contact data
        contact_data = {
            "data": {
                "type": "Person",
                "first_name": first_name,
                "last_name": last_name
            }
        }

        # Add phone if provided
        if phone:
            contact_data["data"]["phone_numbers"] = [{
                "number": phone,
                "type": "work"
            }]

            # Add email if provided
            if email:
                contact_data["data"]["email_addresses"] = [{
                    "address": email,
                    "type": "work"
                }]

            # Add address if provided
            if address_data:
                addresses = []
                address = {"type": "home"}

                if address_data.get("state"):
                    address["state"] = address_data["state"]
                if address_data.get("country"):
                    address["country"] = address_data["country"]
                if address_data.get("city"):
                    address["city"] = address_data["city"]
                if address_data.get("postal_code"):
                    address["postal_code"] = address_data["postal_code"]

                if len(address) > 1:  # More than just "type"
                    addresses.append(address)
                    contact_data["data"]["addresses"] = addresses

            # Get auth token
            token = get_clio_token()
            if not token:
                print("❌ No Clio token available")
                return None

            print("Sending contact creation request to Clio API...")
            print(f"Request data: {json.dumps(contact_data, indent=2)}")

            try:
                response = requests.post(
                    "https://app.clio.com/api/v4/contacts",
                    headers={
                        "Authorization": f"Bearer {token}",
                        "Content-Type": "application/json"
                    },
                    json=contact_data,
                    timeout=30
                )

                print(f"Response status: {response.status_code}")

                if response.status_code == 201:
                    # Success!
                    contact_info = response.json()
                    print(f"✅ Contact created successfully!")
                    return contact_info
                else:
                    print(f"Response body: {response.text[:500]}...")
                    print(f"❌ Failed to create contact in Clio API - Status: {response.status_code}")

                    # Check if it's a validation error we can fix
                    if response.status_code == 422:
                        try:
                            error_data = response.json()
                            print(f"Validation errors: {error_data}")

                            # If name is still the issue, try with different approach
                            if "name" in str(error_data).lower() or "first" in str(error_data).lower():
                                print("🔄 Retrying with minimal contact data...")

                                # Try with just phone number and minimal name
                                minimal_data = {
                                    "data": {
                                        "type": "Person",
                                        "first_name": first_name if first_name else "Unknown",
                                        "last_name": last_name if last_name else "Caller"
                                    }
                                }

                                if phone:
                                    minimal_data["data"]["phone_numbers"] = [{
                                        "number": phone,
                                        "type": "work"
                                    }]

                                print(f"Minimal request: {json.dumps(minimal_data, indent=2)}")

                                retry_response = requests.post(
                                    "https://app.clio.com/api/v4/contacts",
                                    headers={
                                        "Authorization": f"Bearer {token}",
                                        "Content-Type": "application/json"
                                    },
                                    json=minimal_data,
                                    timeout=30
                                )

                                if retry_response.status_code == 201:
                                    print("✅ Contact created with minimal data!")
                                    return retry_response.json()
                                else:
                                    print(f"❌ Retry also failed: {retry_response.status_code}")
                                    print(f"Retry response: {retry_response.text[:200]}...")

                        except Exception as e:
                            print(f"Error parsing validation response: {e}")

                    return None

            except Exception as e:
                print(f"❌ Exception during contact creation: {e}")
                return None

def create_clio_matter(contact_data, practice_area, description, token=None):
    """Create a matter in Clio using the correct API format with better error handling"""
    import requests
    import json
    import hashlib
    from datetime import datetime
    from flask import session

    # Summarize the transcript if it's too long
    if description and len(description) > 255:
        summarized_description = summarize_transcript(description, max_length=240)
        print(f"📝 Original length: {len(description)}")
        print(f"📝 Summarized: {summarized_description}")
        description = summarized_description

    # Better contact ID extraction with debugging
    print(f"🔍 Contact data received: {json.dumps(contact_data, indent=2)}")

    contact_id = None

    # Try multiple ways to extract contact ID
    if isinstance(contact_data, dict):
        # Method 1: Standard API response format
        if "data" in contact_data and isinstance(contact_data["data"], dict):
            contact_id = contact_data["data"].get("id")
            print(f"📋 Method 1 - Contact ID from data.id: {contact_id}")

        # Method 2: Direct ID field
        if not contact_id:
            contact_id = contact_data.get("id")
            print(f"📋 Method 2 - Contact ID from direct id: {contact_id}")

        # Method 3: Check if it's an error response with mock data
        if not contact_id and "mock_data" in contact_data:
            mock_data = contact_data["mock_data"]
            if "data" in mock_data:
                contact_id = mock_data["data"].get("id")
                print(f"📋 Method 3 - Contact ID from mock_data: {contact_id}")

    if not contact_id:
        error_msg = f"Cannot create matter without valid contact ID. Contact data: {contact_data}"
        print(f"❌ {error_msg}")
        return {"error": error_msg}

    print(f"✅ Using contact ID: {contact_id}")

    # Get authentication token
    auth_token = token or session.get('clio_token', '')
    if not auth_token:
        return {"error": "No Clio authentication token available"}

    # Check if we're in mock mode
    USE_MOCK_DATA = auth_token == "mock-token-for-testing"

    if USE_MOCK_DATA:
        print("🧪 Creating mock matter data")
        mock_matter_id = hashlib.md5(f"matter-{contact_id}-{practice_area}".encode()).hexdigest()[:8]

        mock_matter = {
            "data": {
                "id": f"mock-matter-{mock_matter_id}",
                "type": "matters",
                "attributes": {
                    "display_number": f"GHL-{contact_id}",
                    "description": description or "Lead from GoHighLevel",
                    "status": "Pending",
                    "practice_area": practice_area or "General",
                    "created_at": datetime.now().isoformat(),
                    "client_id": contact_id
                }
            }
        }

        return {
            "mock_data": True,
            "data": mock_matter["data"],
            "message": "Mock matter created successfully"
        }

    # Set up headers for real API call
    headers = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # Try multiple API formats that Clio accepts
    api_attempts = [
        {
            "name": "Standard Matter Creation",
            "url": f"{CLIO_API_BASE}/matters",
            "data": {
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
        },
        {
            "name": "Alternative Format 1",
            "url": f"{CLIO_API_BASE}/matters",
            "data": {
                "data": {
                    "type": "Matter",
                    "client_id": str(contact_id),
                    "display_number": f"GHL-{contact_id}",
                    "description": description or "Lead from GoHighLevel",
                    "status": "Pending",
                    "practice_area": practice_area or "General"
                }
            }
        },
        {
            "name": "Contact-specific endpoint",
            "url": f"{CLIO_API_BASE}/contacts/{contact_id}/matters",
            "data": {
                "data": {
                    "type": "Matter",
                    "display_number": f"GHL-{contact_id}",
                    "description": description or "Lead from GoHighLevel",
                    "status": "Pending",
                    "practice_area": practice_area or "General"
                }
            }
        }
    ]

    # Try each API format
    for attempt in api_attempts:
        try:
            print(f"🔄 Trying {attempt['name']}")
            print(f"📤 URL: {attempt['url']}")
            print(f"📤 Data: {json.dumps(attempt['data'], indent=2)}")

            response = requests.post(
                attempt['url'],
                headers=headers,
                json=attempt['data'],
                timeout=30
            )

            print(f"📥 Response status: {response.status_code}")
            print(f"📥 Response headers: {dict(response.headers)}")
            print(f"📥 Response body: {response.text}")

            if response.status_code in [200, 201]:
                print(f"✅ Successfully created matter using {attempt['name']}")
                result = response.json()
                return result
            elif response.status_code == 401:
                print("🔐 Authentication failed - token may be expired")
                return {
                    "error": "Authentication failed - please re-authenticate with Clio",
                    "status_code": 401
                }
            elif response.status_code == 422:
                print("📝 Validation error - checking response for details")
                try:
                    error_details = response.json()
                    print(f"Validation errors: {error_details}")
                except:
                    pass

        except requests.exceptions.Timeout:
            print(f"⏰ Timeout for {attempt['name']}")
            continue
        except Exception as e:
            print(f"❌ Exception for {attempt['name']}: {str(e)}")
            continue

    # If all attempts failed, return detailed error info
    return {
        "error": "Failed to create matter with all attempted formats",
        "contact_id": contact_id,
        "practice_area": practice_area,
        "description_length": len(description) if description else 0,
        "message": "Check Clio authentication and API permissions"
    }

# Main entry point
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)