#!/bin/bash
#
# Fix rag_user password
#

set -e

echo "Fixing rag_user password..."
echo

# Change database owner temporarily, drop user, recreate
sudo -u postgres psql << EOF
-- Change owner of news_db to postgres temporarily
ALTER DATABASE news_db OWNER TO postgres;

-- Revoke privileges
REVOKE ALL PRIVILEGES ON DATABASE news_db FROM rag_user;

-- Connect to news_db and revoke schema privileges
\c news_db

REVOKE ALL ON SCHEMA public FROM rag_user;

-- Back to postgres db
\c postgres

-- Drop owned objects first
DROP OWNED BY rag_user;

-- Now drop the user
DROP USER IF EXISTS rag_user;

-- Recreate with correct password
CREATE USER rag_user WITH PASSWORD 'rag_password_2024';

-- Grant privileges
GRANT ALL PRIVILEGES ON DATABASE news_db TO rag_user;

-- Change owner back
ALTER DATABASE news_db OWNER TO rag_user;

-- Connect to news_db and grant schema privileges
\c news_db

GRANT ALL ON SCHEMA public TO rag_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO rag_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO rag_user;

\du rag_user
EOF

echo
echo "✅ User fixed!"
