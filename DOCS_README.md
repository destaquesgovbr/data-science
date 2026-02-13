# Documentação do Sistema de Enriquecimento

Este diretório contém toda a documentação do sistema em formato Quarto (.qmd), que pode ser renderizada para HTML, PDF, ou outros formatos.

## Documentações Disponíveis

### 1. CLASSIFIER_README.qmd
**Tema**: NewsClassifier - Classificação sem Dataset

Documentação do módulo standalone para APIs e microserviços. Inclui:
- Guia de uso básico
- Exemplos FastAPI e Flask
- Configuração AWS
- Esquemas de dados
- Performance e custos

### 2. DOCUMENTACAO_PROMPTS.qmd
**Tema**: Benchmark Cogfy vs Bedrock

Análise comparativa detalhada dos dois estilos de prompts. Inclui:
- Descrição completa dos prompts
- Resultados empíricos de benchmark
- Comparação de performance e custos
- Recomendações para produção

## Como Renderizar

### Opção 1: Makefile (Recomendado)

```bash
# Renderizar tudo para HTML
make

# Renderizar tudo para PDF
make pdf

# Renderizar documento específico
make classifier-html
make prompts-html

# Preview interativo (live reload)
make preview

# Limpar arquivos gerados
make clean

# Ver ajuda
make help
```

### Opção 2: Script Bash

```bash
# Renderizar tudo para HTML
./render_docs.sh

# Renderizar para PDF
./render_docs.sh pdf
```

### Opção 3: Comando Direto

```bash
# Renderizar para HTML
quarto render CLASSIFIER_README.qmd --to html

# Renderizar para PDF
quarto render CLASSIFIER_README.qmd --to pdf

# Preview com live reload
quarto preview CLASSIFIER_README.qmd
```

## Formatos de Saída Suportados

### HTML (Padrão)
- Standalone (todos recursos embutidos)
- Responsivo e mobile-friendly
- TOC interativo
- Syntax highlighting
- Callouts e tabs

```bash
make html
# ou
quarto render documento.qmd --to html
```

### PDF
- Requer LaTeX instalado
- Numeração de seções
- Links coloridos
- TOC automático

```bash
make pdf
# ou
quarto render documento.qmd --to pdf
```

### Outros Formatos

```bash
# Word
quarto render documento.qmd --to docx

# Apresentação (Reveal.js)
quarto render documento.qmd --to revealjs

# Markdown (GitHub-flavored)
quarto render documento.qmd --to gfm
```

## Instalação do Quarto

### Linux

```bash
# Via download direto
wget https://github.com/quarto-dev/quarto-cli/releases/download/v1.4.549/quarto-1.4.549-linux-amd64.deb
sudo dpkg -i quarto-1.4.549-linux-amd64.deb
```

### macOS

```bash
brew install quarto
```

### Windows

Baixe o instalador em: https://quarto.org/docs/get-started/

## Estrutura dos Documentos

Cada documento .qmd contém:

### Metadata YAML
```yaml
---
title: "Título"
subtitle: "Subtítulo"
author: "Autor"
date: today
format:
  html:
    theme: cosmo
    toc: true
    embed-resources: true
  pdf:
    toc: true
    number-sections: true
---
```

### Features Especiais

**Callouts** (caixas destacadas):
```markdown
::: {.callout-tip}
Dica importante
:::

::: {.callout-warning}
Aviso
:::

::: {.callout-note}
Observação
:::
```

**Tabs** (conteúdo alternado):
```markdown
::: {.panel-tabset}
## Opção 1
Conteúdo 1

## Opção 2
Conteúdo 2
:::
```

**Grid Layout** (colunas):
```markdown
::: {.grid}
::: {.g-col-6}
Coluna 1
:::
::: {.g-col-6}
Coluna 2
:::
:::
```

**Diagramas Mermaid**:
```markdown
```{mermaid}
graph LR
    A[Início] --> B[Fim]
```
```

## Exemplos de Uso

### Renderizar tudo de uma vez

```bash
make html
```

**Output:**
```
Renderizando CLASSIFIER_README.qmd → CLASSIFIER_README.html
✓ CLASSIFIER_README.html gerado
Renderizando DOCUMENTACAO_PROMPTS.qmd → DOCUMENTACAO_PROMPTS.html
✓ DOCUMENTACAO_PROMPTS.html gerado
✓ Todos os HTMLs gerados com sucesso!
```

### Preview com live reload

```bash
make preview
```

Abre navegador em `http://localhost:4200` com auto-refresh ao salvar mudanças.

### Gerar PDFs

```bash
make pdf
```

**Requer**: LaTeX instalado (pdflatex, xelatex ou lualatex)

```bash
# Ubuntu/Debian
sudo apt-get install texlive-full

# macOS
brew install basictex
```

## Visualização dos Arquivos Gerados

### HTML

```bash
# Abrir no navegador padrão
xdg-open CLASSIFIER_README.html  # Linux
open CLASSIFIER_README.html      # macOS

# Ou servidor local
python -m http.server 8000
# Acessar: http://localhost:8000/CLASSIFIER_README.html
```

### PDF

```bash
xdg-open CLASSIFIER_README.pdf  # Linux
open CLASSIFIER_README.pdf      # macOS
```

## Troubleshooting

### Erro: "jupyter not found"

**Solução:** Remova `jupyter: python3` do YAML header ou converta blocos `{python}` para `python`:

```bash
sed -i 's/```{python}/```python/g' documento.qmd
```

### Erro: "MissingEnvVarsError"

**Solução:** Crie arquivo `.env` com variáveis dummy:

```bash
cat > .env << EOF
GROQ_API_KEY=not-used
OPENAI_API_KEY=not-used
ANTHROPIC_API_KEY=not-used
OLLAMA_BASE_URL=http://localhost:11434
EOF
```

### PDF não renderiza

**Problema:** LaTeX não instalado

**Solução:**
```bash
# Ubuntu/Debian
sudo apt-get install texlive-xetex texlive-fonts-recommended

# macOS
brew install basictex
eval "$(/usr/libexec/path_helper)"
sudo tlmgr update --self
sudo tlmgr install collection-fontsrecommended
```

## Arquivos Gerados

Após renderização, você terá:

```
exploracoes/
├── CLASSIFIER_README.qmd          # Fonte
├── CLASSIFIER_README.html         # Renderizado (2.0 MB)
├── CLASSIFIER_README.pdf          # Opcional
├── DOCUMENTACAO_PROMPTS.qmd       # Fonte
├── DOCUMENTACAO_PROMPTS.html      # Renderizado
├── DOCUMENTACAO_PROMPTS.pdf       # Opcional
├── Makefile                       # Automação
└── render_docs.sh                 # Script alternativo
```

## Customização

### Mudar tema

Edite o YAML header:

```yaml
format:
  html:
    theme: [cosmo, darkly, flatly, journal, lumen, paper, readable, sandstone, simplex, spacelab, united, yeti]
```

### Adicionar CSS customizado

```yaml
format:
  html:
    css: custom.css
```

### Desabilitar TOC

```yaml
format:
  html:
    toc: false
```

## Mais Informações

- [Documentação Quarto](https://quarto.org/docs/)
- [Guia de Markdown](https://quarto.org/docs/authoring/markdown-basics.html)
- [Temas HTML](https://quarto.org/docs/output-formats/html-themes.html)
- [Customização PDF](https://quarto.org/docs/output-formats/pdf-basics.html)

---

**Status**: ✅ Sistema de documentação pronto
**Última atualização**: 10 de fevereiro de 2026
