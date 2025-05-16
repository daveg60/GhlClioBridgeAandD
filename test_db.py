import os
import psycopg2

def test_db_connection():
    try:
        # Connect to the database
        db_url = os.environ.get("DATABASE_URL")
        print(f"Attempting to connect to database...")
        
        conn = psycopg2.connect(db_url)
        cursor = conn.cursor()
        
        # Test a simple query
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        
        print(f"Database connection successful! Result: {result}")
        
        # Close connection
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"Database connection error: {str(e)}")
        return False

if __name__ == "__main__":
    test_db_connection()