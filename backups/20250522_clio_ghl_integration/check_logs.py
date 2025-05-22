import os
import psycopg2
import json
from datetime import datetime, timedelta

def show_recent_transactions(hours=24):
    """Show transactions from the last X hours"""
    db_url = os.environ.get("DATABASE_URL")
    
    if not db_url:
        print("DATABASE_URL environment variable not set")
        return
    
    try:
        # Connect to the database
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Calculate the time threshold
        time_threshold = datetime.now() - timedelta(hours=hours)
        
        # Get recent transactions
        cursor.execute(
            """SELECT id, source, destination, request_method, request_url, 
                     response_status, success, created_at 
              FROM transactions 
              WHERE created_at > %s
              ORDER BY created_at DESC""",
            (time_threshold,)
        )
        
        transactions = cursor.fetchall()
        
        if not transactions:
            print(f"No transactions found in the last {hours} hours")
            return
        
        print(f"Found {len(transactions)} transactions in the last {hours} hours:")
        print("=" * 80)
        
        for t in transactions:
            t_id, source, dest, method, url, status, success, created = t
            print(f"ID: {t_id} | {created} | {source} → {dest} | {method} {url} | Status: {status} | Success: {success}")
        
        print("=" * 80)
        
        # Get error count
        cursor.execute(
            """SELECT COUNT(*) FROM error_logs WHERE created_at > %s""",
            (time_threshold,)
        )
        
        error_count = cursor.fetchone()[0]
        print(f"Errors in the last {hours} hours: {error_count}")
        
        if error_count > 0:
            # Get recent errors
            cursor.execute(
                """SELECT id, transaction_id, error_type, error_message, created_at 
                  FROM error_logs 
                  WHERE created_at > %s
                  ORDER BY created_at DESC
                  LIMIT 5""",
                (time_threshold,)
            )
            
            errors = cursor.fetchall()
            print("\nMost recent errors:")
            print("-" * 80)
            
            for e in errors:
                e_id, t_id, e_type, message, created = e
                print(f"Error ID: {e_id} | Transaction: {t_id} | {created}")
                print(f"Type: {e_type}")
                print(f"Message: {message[:150]}..." if len(message) > 150 else f"Message: {message}")
                print("-" * 80)
        
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error connecting to database: {str(e)}")

def add_test_transaction():
    """Add a test transaction to the database"""
    db_url = os.environ.get("DATABASE_URL")
    
    if not db_url:
        print("DATABASE_URL environment variable not set")
        return
    
    try:
        # Connect to the database
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Insert a test transaction
        cursor.execute(
            """INSERT INTO transactions
               (source, destination, request_method, request_url, request_headers,
                request_body, response_status, response_body, duration_ms, success, created_at)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
               RETURNING id""",
            ('ghl', 'clio', 'POST', '/api/contacts', 
             json.dumps({"Content-Type": "application/json"}),
             json.dumps({"name": "Test User", "email": "test@example.com"}),
             200, json.dumps({"id": "test-123", "status": "created"}),
             150, True, datetime.now())
        )
        
        transaction_id = cursor.fetchone()[0]
        
        print(f"Added test transaction with ID: {transaction_id}")
        
        conn.commit()
        cursor.close()
        conn.close()
        
    except Exception as e:
        print(f"Error connecting to database: {str(e)}")

if __name__ == "__main__":
    print("Checking recent transactions...")
    show_recent_transactions(hours=24)