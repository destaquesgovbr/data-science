#!/bin/bash
# Transfer complete working RAG system to EC2

set -e

echo "📦 Preparing RAG system for transfer..."

cd /l/disk0/lpmoraes/environments/data-science

# Create clean package
tar -czf /tmp/rag-complete.tar.gz \
    source/rag/ \
    --exclude="source/rag/.venv" \
    --exclude="source/rag/__pycache__" \
    --exclude="source/rag/**/__pycache__" \
    --exclude="source/rag/**/*.pyc" \
    --exclude="source/rag/**/*.log" \
    --exclude="source/rag/deploy/batch_indexing.py" \
    --exclude="source/rag/deploy/batch_indexing_*.py"

SIZE=$(du -h /tmp/rag-complete.tar.gz | cut -f1)
echo "✅ Package created: /tmp/rag-complete.tar.gz ($SIZE)"

echo ""
echo "📤 Transferring to EC2..."
scp /tmp/rag-complete.tar.gz lpmoraes@aws-insp-7-01:/tmp/

echo ""
echo "✅ Transfer complete!"
echo ""
echo "Next steps on EC2:"
echo "  ssh lpmoraes@aws-insp-7-01"
echo "  cd /home/lpmoraes"
echo "  tar -xzf /tmp/rag-complete.tar.gz"
echo "  cd source/rag"
echo "  source .venv/bin/activate"
echo "  cat data/corpus_consolidated.json | jq '.documents' > data/corpus_flat.json"
echo "  python scripts/index_corpus.py --input data/corpus_flat.json --format json"
echo ""
