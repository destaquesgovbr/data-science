#!/bin/bash
#
# Fix PostgreSQL Authentication
# Allows password authentication for rag_user
#

set -e

echo "Fixing PostgreSQL authentication for rag_user..."
echo

# Backup original config
sudo cp /etc/postgresql/16/main/pg_hba.conf /etc/postgresql/16/main/pg_hba.conf.backup

# Add md5 authentication for rag_user
echo "# RAG System - Issue #5" | sudo tee -a /etc/postgresql/16/main/pg_hba.conf
echo "local   news_db         rag_user                                md5" | sudo tee -a /etc/postgresql/16/main/pg_hba.conf
echo "host    news_db         rag_user        127.0.0.1/32            md5" | sudo tee -a /etc/postgresql/16/main/pg_hba.conf
echo "host    news_db         rag_user        ::1/128                 md5" | sudo tee -a /etc/postgresql/16/main/pg_hba.conf

# Reload PostgreSQL
sudo systemctl reload postgresql

echo
echo "✅ Authentication fixed!"
echo
echo "Test connection:"
echo "  PGPASSWORD=rag_password_2024 psql -h localhost -U rag_user -d news_db -c 'SELECT version();'"
