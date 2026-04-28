#!/bin/bash
# Script completo para executar avaliação de todos os modelos
# Tempo estimado: 1-2 horas (11 modelos × 200 notícias)

set -e  # Exit on error

echo "================================================================================"
echo "🚀 AVALIAÇÃO COMPLETA DE MODELOS LLM - ISSUE #3"
echo "================================================================================"
echo ""
echo "Este script irá:"
echo "  1. Avaliar 11 modelos LLM em 200 notícias"
echo "  2. Gerar relatórios comparativos"
echo "  3. Criar visualizações"
echo ""
echo "Tempo estimado: 1-2 horas"
echo "Custo estimado: ~\$1-2 USD (depende dos modelos)"
echo ""
read -p "Deseja continuar? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]
then
    echo "❌ Avaliação cancelada"
    exit 1
fi

echo ""
echo "================================================================================"
echo "📊 ETAPA 1: AVALIAÇÃO DOS MODELOS"
echo "================================================================================"
echo ""

python scripts/evaluate_llm_apis_json.py

if [ $? -ne 0 ]; then
    echo ""
    echo "❌ Erro na avaliação. Verifique os logs acima."
    exit 1
fi

echo ""
echo "================================================================================"
echo "📊 ETAPA 2: GERAÇÃO DE VISUALIZAÇÕES"
echo "================================================================================"
echo ""

python scripts/visualize_results.py

if [ $? -ne 0 ]; then
    echo ""
    echo "⚠️  Erro ao gerar visualizações, mas resultados foram salvos."
fi

echo ""
echo "================================================================================"
echo "✅ AVALIAÇÃO CONCLUÍDA!"
echo "================================================================================"
echo ""
echo "📁 Resultados disponíveis em:"
echo "   - results/comparison_summary_json.csv"
echo "   - results/detailed_predictions_json.csv"
echo "   - results/classification_report_json.txt"
echo "   - results/figures/*.png"
echo ""
echo "🎯 Próximos passos:"
echo "   1. Revisar results/comparison_summary_json.csv"
echo "   2. Analisar visualizações em results/figures/"
echo "   3. Escolher modelo(s) para produção"
echo "   4. Atualizar docs/TECHNICAL_REPORT_ISSUE3.md"
echo ""
