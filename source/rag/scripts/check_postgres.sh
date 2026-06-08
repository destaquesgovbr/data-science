#!/bin/bash
#
# Check PostgreSQL Setup
#

echo "=========================================="
echo "PostgreSQL Diagnostic"
echo "=========================================="
echo

echo "1. Checking if rag_user exists..."
sudo -u postgres psql -c "\du rag_user"
echo

echo "2. Checking if news_db exists..."
sudo -u postgres psql -c "\l news_db"
echo

echo "3. Checking pgvector extension..."
sudo -u postgres psql -d news_db -c "SELECT extname, extversion FROM pg_extension WHERE extname = 'vector';"
echo

echo "4. Resetting rag_user password..."
sudo -u postgres psql -c "ALTER USER rag_user WITH PASSWORD 'rag_password_2024';"
echo

echo "5. Testing connection..."
PGPASSWORD=rag_password_2024 psql -h localhost -U rag_user -d news_db -c 'SELECT current_user, current_database();'
echo

echo "Done!"
