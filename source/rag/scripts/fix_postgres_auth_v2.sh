#!/bin/bash
#
# Fix PostgreSQL Authentication V2
# Properly configure pg_hba.conf to allow password auth for rag_user
#

set -e

echo "Fixing PostgreSQL authentication (V2)..."
echo

# Backup original config
sudo cp /etc/postgresql/16/main/pg_hba.conf /etc/postgresql/16/main/pg_hba.conf.backup2

# Remove previous RAG entries if they exist
sudo sed -i '/# RAG System - Issue #5/d' /etc/postgresql/16/main/pg_hba.conf
sudo sed -i '/news_db.*rag_user/d' /etc/postgresql/16/main/pg_hba.conf

# Add our rules at the TOP of the file (before other rules)
# This ensures they are matched first
sudo sed -i '1i\# RAG System - Issue #5 (Added by setup script)' /etc/postgresql/16/main/pg_hba.conf
sudo sed -i '2i\local   news_db         rag_user                                scram-sha-256' /etc/postgresql/16/main/pg_hba.conf
sudo sed -i '3i\host    news_db         rag_user        127.0.0.1/32            scram-sha-256' /etc/postgresql/16/main/pg_hba.conf
sudo sed -i '4i\host    news_db         rag_user        ::1/128                 scram-sha-256' /etc/postgresql/16/main/pg_hba.conf
sudo sed -i '5i\ ' /etc/postgresql/16/main/pg_hba.conf

echo "New pg_hba.conf (first 15 lines):"
sudo head -15 /etc/postgresql/16/main/pg_hba.conf
echo

# Reload PostgreSQL
echo "Reloading PostgreSQL..."
sudo systemctl reload postgresql
sleep 2

echo
echo "✅ Authentication fixed!"
echo
echo "Testing connection..."
PGPASSWORD=rag_password_2024 psql -h localhost -U rag_user -d news_db -c 'SELECT current_user, current_database();'
