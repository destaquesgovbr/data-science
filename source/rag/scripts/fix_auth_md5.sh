#!/bin/bash
#
# Switch to MD5 authentication (simpler, more compatible)
#

set -e

echo "Switching to MD5 authentication..."
echo

# Backup
sudo cp /etc/postgresql/16/main/pg_hba.conf /etc/postgresql/16/main/pg_hba.conf.backup3

# Replace scram-sha-256 with md5 for news_db
sudo sed -i 's/news_db.*scram-sha-256/news_db         rag_user                                md5/' /etc/postgresql/16/main/pg_hba.conf
sudo sed -i 's/news_db.*rag_user.*127.0.0.1.*scram-sha-256/news_db         rag_user        127.0.0.1\/32            md5/' /etc/postgresql/16/main/pg_hba.conf
sudo sed -i 's/news_db.*rag_user.*::1.*scram-sha-256/news_db         rag_user        ::1\/128                 md5/' /etc/postgresql/16/main/pg_hba.conf

echo "New pg_hba.conf (first 10 lines):"
sudo head -10 /etc/postgresql/16/main/pg_hba.conf
echo

# Restart PostgreSQL (reload may not be enough)
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
    print("✅ SUCCESS! Connection works with MD5 auth")

    cur = conn.cursor()
    cur.execute('SELECT current_user, current_database(), version();')
    user, db, version = cur.fetchone()
    print(f"   User: {user}")
    print(f"   DB: {db}")
    print(f"   Version: {version[:60]}...")

    conn.close()

except Exception as e:
    print(f"❌ Still failed: {e}")
    exit(1)
PYEOF
