#!/bin/bash
#
# Test with a completely new user
#

set -e

echo "Creating test user: test_user123"
sudo -u postgres psql << EOF
-- Create new user
CREATE USER test_user123 WITH PASSWORD 'test123';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE news_db TO test_user123;

-- Connect and grant schema privileges
\c news_db
GRANT ALL ON SCHEMA public TO test_user123;

\du test_user123
EOF

echo
echo "Testing connection with new user..."
cd /l/disk0/lpmoraes/environments/data-science
source .venv/bin/activate

python3 << 'PYEOF'
import psycopg

try:
    conn = psycopg.connect(
        host='localhost',
        port=5432,
        dbname='news_db',
        user='test_user123',
        password='test123'
    )
    print("✅ NEW USER WORKS!")

    cur = conn.cursor()
    cur.execute('SELECT current_user, current_database();')
    user, db = cur.fetchone()
    print(f"   User: {user}")
    print(f"   DB: {db}")

    conn.close()

except Exception as e:
    print(f"❌ NEW USER ALSO FAILS: {e}")
PYEOF

echo
echo "Cleaning up test user..."
sudo -u postgres psql -c "DROP USER IF EXISTS test_user123;"
echo "Done!"
