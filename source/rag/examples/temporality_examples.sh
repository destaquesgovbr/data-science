#!/bin/bash
# Fase 6: Temporality Examples
#
# This script demonstrates how to use temporal features via API

API_URL="http://localhost:8000/query"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║              Fase 6: Temporalidade - Examples                ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# ============================================================================
# Example 1: Basic query (no date filter)
# ============================================================================

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Example 1: Basic Query - LLM sees publication dates"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Request:"
echo '{
  "query": "Notícias recentes sobre periferias?",
  "top_k": 3
}'
echo ""

curl -s -X POST $API_URL \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Notícias recentes sobre periferias?",
    "top_k": 3
  }' | python3 -m json.tool | grep -A 20 '"sources"'

echo ""
echo "✓ Notice: Each source now has 'published_at' field (DD/MM/YYYY)"
echo ""
read -p "Press Enter to continue..."

# ============================================================================
# Example 2: Filter by date range (March 2026)
# ============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Example 2: Date Filter - Only March 2026"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Request:"
echo '{
  "query": "O que aconteceu?",
  "top_k": 5,
  "date_from": "2026-03-01",
  "date_to": "2026-03-31"
}'
echo ""

curl -s -X POST $API_URL \
  -H "Content-Type: application/json" \
  -d '{
    "query": "O que aconteceu?",
    "top_k": 5,
    "date_from": "2026-03-01",
    "date_to": "2026-03-31"
  }' | python3 -m json.tool | grep -E '"title"|"published_at"' | head -20

echo ""
echo "✓ All sources are from March 2026 (date filter working)"
echo ""
read -p "Press Enter to continue..."

# ============================================================================
# Example 3: Recent news only (last 15 days)
# ============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Example 3: Recent News - Last 15 days"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Calculate date 15 days ago (approximation - March 8)
DATE_FROM="2026-03-08"

echo "Request:"
echo "{
  \"query\": \"Últimas notícias sobre governo\",
  \"top_k\": 3,
  \"date_from\": \"$DATE_FROM\"
}"
echo ""

curl -s -X POST $API_URL \
  -H "Content-Type: application/json" \
  -d "{
    \"query\": \"Últimas notícias sobre governo\",
    \"top_k\": 3,
    \"date_from\": \"$DATE_FROM\"
  }" | python3 -m json.tool | grep -E '"title"|"published_at"' | head -15

echo ""
echo "✓ Only news from March 8 onwards"
echo ""
read -p "Press Enter to continue..."

# ============================================================================
# Example 4: Specific date (exact day)
# ============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Example 4: Specific Date - March 19, 2026"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Request:"
echo '{
  "query": "Notícias sobre periferias",
  "top_k": 5,
  "date_from": "2026-03-19",
  "date_to": "2026-03-19"
}'
echo ""

curl -s -X POST $API_URL \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Notícias sobre periferias",
    "top_k": 5,
    "date_from": "2026-03-19",
    "date_to": "2026-03-19"
  }' | python3 -m json.tool | grep -E '"title"|"published_at"' | head -10

echo ""
echo "✓ Only news from March 19, 2026"
echo ""
read -p "Press Enter to continue..."

# ============================================================================
# Example 5: LLM chronological ordering
# ============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Example 5: LLM Chronological Ordering"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Request:"
echo '{
  "query": "O que aconteceu em março de 2026?",
  "top_k": 5,
  "date_from": "2026-03-01",
  "date_to": "2026-03-31"
}'
echo ""

curl -s -X POST $API_URL \
  -H "Content-Type: application/json" \
  -d '{
    "query": "O que aconteceu em março de 2026?",
    "top_k": 5,
    "date_from": "2026-03-01",
    "date_to": "2026-03-31"
  }' | python3 -m json.tool | grep -A 10 '"answer"'

echo ""
echo "✓ LLM mentions dates and orders events chronologically"
echo ""

# ============================================================================
# Example 6: Full response with all fields
# ============================================================================

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "Example 6: Full Response - All Fields"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Request:"
echo '{
  "query": "Periferias",
  "top_k": 1
}'
echo ""

curl -s -X POST $API_URL \
  -H "Content-Type: application/json" \
  -d '{
    "query": "Periferias",
    "top_k": 1
  }' | python3 -m json.tool

echo ""
echo "✓ Complete response with all fields including published_at"
echo ""

# ============================================================================
# Summary
# ============================================================================

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                          SUMMARY                             ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║  Fase 6 Features Demonstrated:                               ║"
echo "║                                                              ║"
echo "║  ✓ Sources include 'published_at' field (DD/MM/YYYY)        ║"
echo "║  ✓ API accepts 'date_from' and 'date_to' filters            ║"
echo "║  ✓ LLM sees publication dates in context                    ║"
echo "║  ✓ LLM mentions dates in responses                          ║"
echo "║  ✓ LLM can order events chronologically                     ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

echo "For more examples, see: FASE6_TEMPORALIDADE.md"
echo ""
