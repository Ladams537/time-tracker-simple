import os
import psycopg2
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


def initialize_database():
    """Connects to the database and creates the"""
    """ necessary table if it doesn't exist."""
    print("Connecting to the database...")
    conn = None
    try:
        conn = psycopg2.connect(
            dbname=os.getenv("DB_DATABASE"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
            host=os.getenv("DB_HOST", "127.0.0.1"),
            port=os.getenv("DB_PORT", "5432")
        )
        cur = conn.cursor()
        print("Connection successful."
              + "Creating table 'time_log' if it doesn't exist...")

        # Create the table with a UNIQUE constraint on date and time_slot
        cur.execute("""
            CREATE TABLE IF NOT EXISTS time_log (
                id SERIAL PRIMARY KEY,
                entry_date DATE NOT NULL,
                time_slot TIME NOT NULL,
                activity TEXT,
                category TEXT,
                priority TEXT,
                notes TEXT,
                UNIQUE (entry_date, time_slot)
            );
        """)
        conn.commit()
        cur.close()
        print("Table 'time_log' is ready.")
    except psycopg2.OperationalError as e:
        print("ERROR: Could not connect to the database."
              + "Please check your configuration.")
        print(f"Details: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
    finally:
        if conn is not None:
            conn.close()
            print("Database connection closed.")


if __name__ == '__main__':
    initialize_database()
