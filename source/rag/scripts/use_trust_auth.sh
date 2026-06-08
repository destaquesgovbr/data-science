#!/bin/bash
#
# Use trust authentication (NO PASSWORD) temporarily
# THIS IS INSECURE - only for local development
#

set -e

echo "Switching to TRUST authentication (no password)..."
echo "⚠️  This is INSECURE - only use for local development!"
echo

# Backup
sudo cp /etc/postgresql/16/main/pg_hba.conf /etc/postgresql/16/main/pg_hba.conf.before_trust

# Add trust rules at the top
sudo sed -i '1i\# TEMPORARY - Trust authentication for development' /etc/postgresql/16/main/pg_hba.conf
sudo sed -i '2i\local   news_db         rag_user                                trust' /etc/postgresql/16/main/pg_hba.conf
sudo sed -i '3i\host    news_db         rag_user        127.0.0.1/32            trust' /etc/postgresql/16/main/pg_hba.conf
sudo sed -i '4i\ ' /etc/postgresql/16/main/pg_hba.conf

echo "New pg_hba.conf (first 10 lines):"
sudo head -10 /etc/postgresql/16/main/pg_hba.conf
echo

# Reload
echo "Reloading PostgreSQL..."
sudo pg_ctlcluster 16 main reload
sleep 2

echo
echo "Testing connection (no password needed)..."
cd /l/disk0/lpmoraes/environments/data-science
source .venv/bin/activate

python3 << 'PYEOF'
import psycopg

try:
    # No password with trust!
    conn = psycopg.connect(
        host='localhost',
        port=5433,
        dbname='news_db',
        user='rag_user'
    )
    print("✅ SUCCESS! Connected with trust auth")

    cur = conn.cursor()
    cur.execute('SELECT current_user, current_database();')
    user, db = cur.fetchone()
    print(f"   User: {user}")
    print(f"   DB: {db}")

    conn.close()

except Exception as e:
    print(f"❌ Failed: {e}")
PYEOF
