#!/bin/bash

# Script para renderizar todas as documentações Quarto

set -e  # Exit on error

echo "========================================"
echo "Renderizando Documentações Quarto"
echo "========================================"
echo ""

# Cores para output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Carregar variáveis de ambiente (se existir .env)
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

# Função para renderizar um documento
render_doc() {
    local doc=$1
    local format=$2

    echo -e "${BLUE}Renderizando: ${doc} (${format})${NC}"

    if quarto render "$doc" --to "$format"; then
        echo -e "${GREEN}✓ Sucesso: ${doc} → ${format}${NC}"
    else
        echo "❌ Erro ao renderizar: $doc"
        return 1
    fi
    echo ""
}

# Documentações disponíveis
DOCS=(
    "CLASSIFIER_README.qmd"
    "DOCUMENTACAO_PROMPTS.qmd"
)

# Verificar se foi passado argumento
FORMAT="${1:-html}"  # Default: html

echo "Formato de saída: $FORMAT"
echo ""

# Renderizar cada documento
for doc in "${DOCS[@]}"; do
    if [ -f "$doc" ]; then
        render_doc "$doc" "$FORMAT"
    else
        echo "⚠️  Arquivo não encontrado: $doc"
    fi
done

echo "========================================"
echo "Renderização concluída!"
echo "========================================"
echo ""

# Listar arquivos gerados
echo "Arquivos gerados:"
if [ "$FORMAT" == "html" ]; then
    ls -lh *.html 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}'
elif [ "$FORMAT" == "pdf" ]; then
    ls -lh *.pdf 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}'
fi
echo ""
