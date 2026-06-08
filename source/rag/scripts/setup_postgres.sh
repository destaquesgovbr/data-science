#!/bin/bash
#
# PostgreSQL Setup Script for RAG System
# Run this script with: bash scripts/setup_postgres.sh
#

set -e  # Exit on error

echo "=========================================="
echo "PostgreSQL Setup for RAG System"
echo "=========================================="
echo

# Create user and database
echo "1. Creating database user 'rag_user'..."
sudo -u postgres psql -c "CREATE USER rag_user WITH PASSWORD 'rag_password_2024';" 2>/dev/null || echo "   User already exists, skipping..."

echo "2. Creating database 'news_db'..."
sudo -u postgres psql -c "CREATE DATABASE news_db OWNER rag_user;" 2>/dev/null || echo "   Database already exists, skipping..."

echo "3. Granting privileges..."
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE news_db TO rag_user;"

# Enable pgvector extension
echo "4. Enabling pgvector extension..."
sudo -u postgres psql -d news_db -c "CREATE EXTENSION IF NOT EXISTS vector;"

echo "5. Granting schema privileges..."
sudo -u postgres psql -d news_db -c "GRANT ALL ON SCHEMA public TO rag_user;"
sudo -u postgres psql -d news_db -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO rag_user;"
sudo -u postgres psql -d news_db -c "ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO rag_user;"

echo
echo "✅ PostgreSQL setup complete!"
echo
echo "Database details:"
echo "  Host: localhost"
echo "  Port: 5432"
echo "  Database: news_db"
echo "  User: rag_user"
echo "  Password: rag_password_2024"
echo
echo "To verify, run:"
echo "  psql -h localhost -U rag_user -d news_db -c '\\dx'"
echo
