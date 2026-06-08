#!/bin/bash
# Export indexed database for transfer to EC2

echo "📦 Exporting database..."

# Dump database
PGPASSWORD=rag_pass pg_dump -h localhost -p 5433 -U rag_user news_db > /tmp/news_db_indexed.sql

# Compress
gzip -9 /tmp/news_db_indexed.sql

# Stats
SIZE=$(du -h /tmp/news_db_indexed.sql.gz | cut -f1)
echo "✅ Database exported: /tmp/news_db_indexed.sql.gz ($SIZE)"
echo ""
echo "Transfer to EC2:"
echo "  scp /tmp/news_db_indexed.sql.gz lpmoraes@aws-insp-7-01:/tmp/"
echo ""
echo "Import on EC2:"
echo "  gunzip /tmp/news_db_indexed.sql.gz"
echo "  PGPASSWORD=rag_pass psql -h localhost -p 5432 -U rag_user -d news_db < /tmp/news_db_indexed.sql"
