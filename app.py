app.clio.com/api/v4/contacts",
            headers={
                "Authorization": f"Bearer {auth_token}",
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
                                "Authorization": f"Bearer {auth_token}",
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