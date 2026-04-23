#!/bin/bash
#
# Script para executar experimento completo de fine-tuning.
#
# Usage:
#   ./run_finetuning_experiment.sh fewshot   # Experimento few-shot (500 triplas)
#   ./run_finetuning_experiment.sh full      # Experimento full (1668 triplas)

set -e

DATASET_TYPE=${1:-fewshot}
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
OUTPUT_DIR="models/bge-m3-${DATASET_TYPE}-${TIMESTAMP}"
RESULTS_FILE="results/finetuning/${DATASET_TYPE}_${TIMESTAMP}_results.json"

echo "========================================================================"
echo "EXPERIMENTO DE FINE-TUNING - ${DATASET_TYPE}"
echo "========================================================================"
echo ""
echo "Dataset: ${DATASET_TYPE}"
echo "Output: ${OUTPUT_DIR}"
echo "Results: ${RESULTS_FILE}"
echo ""

# Etapa 1: Fine-tuning
echo "========================================================================"
echo "ETAPA 1: FINE-TUNING"
echo "========================================================================"
echo ""

if [ "$DATASET_TYPE" == "fewshot" ]; then
    python source/embeddings/scripts/finetune_model.py \
        --dataset fewshot \
        --epochs 2 \
        --batch-size 16 \
        --learning-rate 2e-5 \
        --warmup-steps 50 \
        --output "$OUTPUT_DIR" \
        --evaluation-steps 25
else
    python source/embeddings/scripts/finetune_model.py \
        --dataset full \
        --epochs 3 \
        --batch-size 16 \
        --learning-rate 2e-5 \
        --warmup-steps 100 \
        --output "$OUTPUT_DIR" \
        --evaluation-steps 50
fi

echo ""
echo "✅ Fine-tuning concluído!"
echo ""

# Etapa 2: Avaliação
echo "========================================================================"
echo "ETAPA 2: AVALIAÇÃO NO TEST SET"
echo "========================================================================"
echo ""

python source/embeddings/scripts/evaluate_finetuned.py \
    --model "$OUTPUT_DIR" \
    --compare-baseline "BAAI/bge-m3" \
    --output "$RESULTS_FILE"

echo ""
echo "✅ Avaliação concluída!"
echo ""

# Resumo
echo "========================================================================"
echo "EXPERIMENTO CONCLUÍDO"
echo "========================================================================"
echo ""
echo "📁 Modelo fine-tuned: ${OUTPUT_DIR}"
echo "📊 Resultados: ${RESULTS_FILE}"
echo ""
echo "Próximos passos:"
echo "  1. Revisar resultados em ${RESULTS_FILE}"
echo "  2. Se ganhos > 2%, considerar full fine-tuning"
echo "  3. Análise qualitativa de casos de sucesso/falha"
echo ""
