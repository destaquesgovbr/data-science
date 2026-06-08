#!/bin/bash
#
# Debug PostgreSQL authentication
#

echo "=========================================="
echo "PostgreSQL Authentication Debug"
echo "=========================================="
echo

echo "1. Checking password encryption method..."
sudo -u postgres psql -c "SHOW password_encryption;"
echo

echo "2. Checking rag_user password hash..."
sudo -u postgres psql -c "SELECT rolname, rolpassword FROM pg_authid WHERE rolname = 'rag_user';"
echo

echo "3. Checking pg_hba.conf entries for news_db..."
sudo grep -n "news_db" /etc/postgresql/16/main/pg_hba.conf
echo

echo "4. Setting password with explicit encryption..."
sudo -u postgres psql << EOF
-- Set password with scram-sha-256
ALTER USER rag_user WITH PASSWORD 'rag_password_2024';
EOF
echo

echo "5. Reloading PostgreSQL..."
sudo systemctl reload postgresql
sleep 2
echo

echo "6. Testing connection via psql (as postgres user)..."
sudo -u postgres psql -c "SET ROLE rag_user; SELECT current_user;"
echo

echo "Done!"
