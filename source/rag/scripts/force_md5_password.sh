#!/bin/bash
#
# Force MD5 password hash
#

set -e

echo "Forcing MD5 password hash for rag_user..."
echo

# Change password encryption to md5 temporarily
sudo -u postgres psql << 'EOF'
-- Set password encryption to md5
SET password_encryption = 'md5';

-- Update password (will use md5 now)
ALTER USER rag_user WITH PASSWORD 'rag_password_2024';

-- Check the hash
SELECT rolname, substring(rolpassword, 1, 5) as hash_method
FROM pg_authid
WHERE rolname = 'rag_user';
EOF

echo
echo "Restarting PostgreSQL..."
sudo systemctl restart postgresql
sleep 3

echo
echo "Testing connection..."
cd /l/disk0/lpmoraes/environments/data-science
source .venv/bin/activate

python3 << 'PYEOF'
import psycopg

try:
    conn = psycopg.connect(
        host='localhost',
        port=5432,
        dbname='news_db',
        user='rag_user',
        password='rag_password_2024'
    )
    print("✅ SUCCESS!")

    cur = conn.cursor()
    cur.execute('SELECT current_user;')
    print(f"   Connected as: {cur.fetchone()[0]}")

    conn.close()

except Exception as e:
    print(f"❌ Failed: {e}")

    # Try with trust method as last resort
    print("\n🔧 Let's try switching to 'trust' method temporarily...")
    exit(1)
PYEOF
