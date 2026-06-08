#!/bin/bash

API_URL="http://localhost:8000/query"

echo "=== Test 1: Notícias de março de 2026 ==="
curl -s -X POST $API_URL \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Quais notícias foram publicadas em março?",
    "top_k": 5,
    "date_from": "2026-03-01",
    "date_to": "2026-03-31",
    "min_source_score": 0.3
  }' | python -m json.tool | head -50

echo ""
echo "=== Test 2: Apenas notícias recentes (últimos 15 dias) ==="
curl -s -X POST $API_URL \
  -H "Content-Type: application/json" \
  -d '{
    "query": "O que aconteceu recentemente?",
    "top_k": 3,
    "date_from": "2026-03-15"
  }' | python -m json.tool | head -40

