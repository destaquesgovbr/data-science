#!/bin/bash
#
# Test with a new simple password
#

set -e

NEW_PASSWORD="testpass123"

echo "Setting new password: $NEW_PASSWORD"
sudo -u postgres psql -c "ALTER USER rag_user WITH PASSWORD '$NEW_PASSWORD';"

echo
echo "Testing connection immediately..."
cd /l/disk0/lpmoraes/environments/data-science
source .venv/bin/activate

python3 << EOF
import psycopg

try:
    conn = psycopg.connect(
        host='localhost',
        port=5432,
        dbname='news_db',
        user='rag_user',
        password='$NEW_PASSWORD'
    )
    print("✅ SUCCESS! Connection works with password: $NEW_PASSWORD")

    cur = conn.cursor()
    cur.execute('SELECT current_user, current_database();')
    user, db = cur.fetchone()
    print(f"   Connected as: {user}")
    print(f"   Database: {db}")

    conn.close()
    exit(0)

except Exception as e:
    print(f"❌ FAILED: {e}")
    exit(1)
EOF

if [ $? -eq 0 ]; then
    echo
    echo "Password '$NEW_PASSWORD' works!"
    echo "Changing back to 'rag_password_2024'..."
    sudo -u postgres psql -c "ALTER USER rag_user WITH PASSWORD 'rag_password_2024';"
    echo "Done!"
fi
