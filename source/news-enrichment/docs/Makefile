# Makefile para renderizar documentações Quarto

.PHONY: all html pdf clean preview help

# Variáveis
DOCS := CLASSIFIER_README.qmd DOCUMENTACAO_PROMPTS.qmd
HTML_FILES := $(DOCS:.qmd=.html)
PDF_FILES := $(DOCS:.qmd=.pdf)

# Target padrão
all: html

# Renderizar todos para HTML
html: $(HTML_FILES)
	@echo "✓ Todos os HTMLs gerados com sucesso!"

# Renderizar todos para PDF
pdf: $(PDF_FILES)
	@echo "✓ Todos os PDFs gerados com sucesso!"

# Regra genérica para HTML
%.html: %.qmd
	@echo "Renderizando $< → $@"
	@export $$(cat .env 2>/dev/null | grep -v '^#' | xargs) && quarto render $< --to html
	@echo "✓ $@ gerado"

# Regra genérica para PDF
%.pdf: %.qmd
	@echo "Renderizando $< → $@"
	@export $$(cat .env 2>/dev/null | grep -v '^#' | xargs) && quarto render $< --to pdf
	@echo "✓ $@ gerado"

# Preview interativo (abre servidor local)
preview:
	@echo "Iniciando preview..."
	@export $$(cat .env 2>/dev/null | grep -v '^#' | xargs) && quarto preview CLASSIFIER_README.qmd

# Limpar arquivos gerados
clean:
	@echo "Limpando arquivos gerados..."
	@rm -f $(HTML_FILES) $(PDF_FILES)
	@rm -rf *_files/
	@echo "✓ Arquivos limpos"

# Renderizar documento específico
classifier-html:
	@export $$(cat .env 2>/dev/null | grep -v '^#' | xargs) && quarto render CLASSIFIER_README.qmd --to html

classifier-pdf:
	@export $$(cat .env 2>/dev/null | grep -v '^#' | xargs) && quarto render CLASSIFIER_README.qmd --to pdf

prompts-html:
	@export $$(cat .env 2>/dev/null | grep -v '^#' | xargs) && quarto render DOCUMENTACAO_PROMPTS.qmd --to html

prompts-pdf:
	@export $$(cat .env 2>/dev/null | grep -v '^#' | xargs) && quarto render DOCUMENTACAO_PROMPTS.qmd --to pdf

# Ajuda
help:
	@echo "Makefile para renderizar documentações Quarto"
	@echo ""
	@echo "Targets disponíveis:"
	@echo "  make all              - Renderiza tudo para HTML (padrão)"
	@echo "  make html             - Renderiza todas as documentações para HTML"
	@echo "  make pdf              - Renderiza todas as documentações para PDF"
	@echo "  make preview          - Inicia preview interativo"
	@echo "  make clean            - Remove arquivos gerados"
	@echo ""
	@echo "Targets específicos:"
	@echo "  make classifier-html  - Renderiza apenas CLASSIFIER_README.html"
	@echo "  make classifier-pdf   - Renderiza apenas CLASSIFIER_README.pdf"
	@echo "  make prompts-html     - Renderiza apenas DOCUMENTACAO_PROMPTS.html"
	@echo "  make prompts-pdf      - Renderiza apenas DOCUMENTACAO_PROMPTS.pdf"
	@echo ""
	@echo "Exemplos:"
	@echo "  make                  # Renderiza tudo para HTML"
	@echo "  make pdf              # Renderiza tudo para PDF"
	@echo "  make classifier-html  # Apenas uma documentação"
