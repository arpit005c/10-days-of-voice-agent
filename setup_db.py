import sqlite3

def create_database():
    conn = sqlite3.connect('bank_fraud.db')
    c = conn.cursor()
    
    # Create table
    c.execute('''
        CREATE TABLE IF NOT EXISTS fraud_cases (
            username TEXT PRIMARY KEY,
            security_code TEXT,
            card_last4 TEXT,
            merchant TEXT,
            amount TEXT,
            location TEXT,
            timestamp TEXT,
            case_status TEXT
        )
    ''')
    
    # Insert Sample Data
    samples = [
        ('john_doe', '1234', '4242', 'Apple Store', '$999.00', 'New York, NY', 'Today, 2:30 PM', 'pending'),
        ('jane_smith', '9797', '8888', 'Unknown Crypto Site', '$5000.00', 'Lagos, Nigeria', 'Yesterday, 3:00 AM', 'pending')
    ]
    
    c.executemany('INSERT OR REPLACE INTO fraud_cases VALUES (?,?,?,?,?,?,?,?)', samples)
    
    conn.commit()
    conn.close()
    print("✅ Database 'bank_fraud.db' created with sample cases.")

if __name__ == "__main__":
    create_database()