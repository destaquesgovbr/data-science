#!/bin/bash
#
# Recreate PostgreSQL user with correct password encryption
#

set -e

echo "Recreating rag_user with correct password..."
echo

# Drop and recreate user
sudo -u postgres psql << EOF
-- Drop existing user (cascade to remove privileges)
DROP USER IF EXISTS rag_user;

-- Create user with SCRAM-SHA-256 password
CREATE USER rag_user WITH PASSWORD 'rag_password_2024';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE news_db TO rag_user;

-- Connect to news_db and grant schema privileges
\c news_db

GRANT ALL ON SCHEMA public TO rag_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO rag_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO rag_user;

-- Show user
\du rag_user
EOF

echo
echo "✅ User recreated!"
echo
echo "Testing connection via Python..."
cd /l/disk0/lpmoraes/environments/data-science/source/rag
python3 << 'PYEOF'
import psycopg

conn_string = "host=localhost port=5432 dbname=news_db user=rag_user password=rag_password_2024"

try:
    with psycopg.connect(conn_string) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT current_user, current_database();")
            result = cur.fetchone()
            print(f"✅ Connected as {result[0]} to {result[1]}")
except Exception as e:
    print(f"❌ Failed: {e}")
    exit(1)
PYEOF
