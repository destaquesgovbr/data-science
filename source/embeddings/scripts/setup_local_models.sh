#!/bin/bash
# Script para baixar modelos open source no Ollama
# Baixa os 8 modelos configurados para avaliação

set -e  # Exit on error

echo "================================================================================"
echo "🚀 SETUP DE MODELOS LOCAIS - OLLAMA"
echo "================================================================================"
echo ""

# Verificar se Ollama está instalado
if ! command -v ollama &> /dev/null; then
    echo "❌ Ollama não está instalado!"
    echo ""
    echo "Para instalar:"
    echo "  curl -fsSL https://ollama.com/install.sh | sh"
    echo ""
    exit 1
fi

echo "✅ Ollama encontrado: $(ollama --version)"
echo ""

# Verificar se Ollama está rodando
if ! curl -s http://localhost:11434/api/tags &> /dev/null; then
    echo "❌ Ollama não está rodando!"
    echo ""
    echo "Para iniciar em outro terminal:"
    echo "  ollama serve"
    echo ""
    exit 1
fi

echo "✅ Ollama está rodando"
echo ""

# Lista de modelos para baixar
declare -a TIER_B=(
    "llama3.1:8b-instruct-q4_K_M"
    "mistral:7b-instruct-v0.3-q4_K_M"
    "qwen2.5:14b-instruct-q4_K_M"
    "gemma2:9b-instruct-q4_K_M"
    "phi3:14b-instruct-q4_K_M"
)

declare -a TIER_C=(
    "llama3.2:3b-instruct-q4_K_M"
    "phi3.5:3.8b-instruct-q4_K_M"
    "gemma2:2b-instruct-q4_K_M"
)

echo "================================================================================"
echo "📦 MODELOS A SEREM BAIXADOS"
echo "================================================================================"
echo ""
echo "Tier B - Médios (7-15B parâmetros):"
for model in "${TIER_B[@]}"; do
    echo "  - $model"
done
echo ""
echo "Tier C - Pequenos (2-4B parâmetros):"
for model in "${TIER_C[@]}"; do
    echo "  - $model"
done
echo ""

# Perguntar confirmação
read -p "Deseja continuar? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "❌ Download cancelado"
    exit 0
fi

echo ""
echo "================================================================================"
echo "⬇️  BAIXANDO MODELOS TIER B (médios)"
echo "================================================================================"
echo ""

for model in "${TIER_B[@]}"; do
    echo "----------------------------------------"
    echo "📦 Baixando: $model"
    echo "----------------------------------------"

    # Verificar se já existe
    if ollama list | grep -q "$model"; then
        echo "✅ Modelo já existe, pulando..."
    else
        ollama pull "$model"
        if [ $? -eq 0 ]; then
            echo "✅ $model baixado com sucesso!"
        else
            echo "❌ Erro ao baixar $model"
        fi
    fi
    echo ""
done

echo ""
echo "================================================================================"
echo "⬇️  BAIXANDO MODELOS TIER C (pequenos)"
echo "================================================================================"
echo ""

for model in "${TIER_C[@]}"; do
    echo "----------------------------------------"
    echo "📦 Baixando: $model"
    echo "----------------------------------------"

    # Verificar se já existe
    if ollama list | grep -q "$model"; then
        echo "✅ Modelo já existe, pulando..."
    else
        ollama pull "$model"
        if [ $? -eq 0 ]; then
            echo "✅ $model baixado com sucesso!"
        else
            echo "❌ Erro ao baixar $model"
        fi
    fi
    echo ""
done

echo ""
echo "================================================================================"
echo "✅ SETUP COMPLETO!"
echo "================================================================================"
echo ""
echo "Modelos instalados:"
ollama list
echo ""
echo "Para verificar espaço em disco usado:"
echo "  du -sh ~/.ollama/models"
echo ""
echo "Próximos passos:"
echo "  1. Teste rápido: python scripts/test_local_quick.py"
echo "  2. Avaliação completa: python scripts/evaluate_local_models.py"
echo ""
