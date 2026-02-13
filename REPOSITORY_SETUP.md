# Guia de Configuração do Repositório

Este guia explica como finalizar a estrutura do repositório e fazer o primeiro commit.

## Estrutura Criada

```
news-enrichment-system/
├── .github/workflows/     # CI/CD (futuro)
├── news_enrichment/       # Código principal
├── examples/             # Exemplos copiados
├── benchmarks/           # Scripts de benchmark copiados
├── docs/                 # Documentação copiada
│   └── rendered/        # HTMLs/PDFs gerados
├── data/                # Dados e taxonomia
├── tests/               # Testes (estrutura criada)
├── .gitignore           ✅ Criado
├── .env.example         ✅ Criado
├── LICENSE              ✅ Criado (MIT)
├── README.md            ✅ Criado
├── pyproject.toml       ✅ Criado
└── requirements.txt     (verificar se existe)
```

## Próximos Passos

### 1. Limpar Arquivos Duplicados (Opcional)

Os arquivos originais ainda existem na raiz. Você pode:

**Opção A: Manter ambos** (raiz + nova estrutura) - útil durante transição
**Opção B: Remover da raiz** após verificar que tudo está ok:

```bash
# Liste arquivos antigos
ls -1 exemplo_*.py benchmark_*.py *.qmd *.md | grep -v README.md

# Remova apenas se tiver certeza
# rm exemplo_*.py benchmark_*.py CLASSIFIER_README.qmd DOCUMENTACAO_PROMPTS.qmd
```

### 2. Verificar requirements.txt

```bash
# Se não existir, criar:
cat > requirements.txt << 'REQS'
anthropic>=0.25.0
openai>=1.0.0
groq>=0.4.0
polars>=0.20.0
pandas>=2.0.0
pyyaml>=6.0
python-dotenv>=1.0.0
psycopg2-binary>=2.9.0
tqdm>=4.66.0
REQS
```

### 3. Inicializar Git e Fazer Primeiro Commit

```bash
# Se ainda não é um repo git
git init

# Adicionar arquivos
git add .

# Primeiro commit
git commit -m "Initial commit: News Enrichment System

- Add core news_enrichment module
- Add examples and benchmarks
- Add comprehensive documentation
- Configure project structure with pyproject.toml
- Add MIT license"
```

### 4. Criar Repositório no GitHub

```bash
# Via GitHub CLI (se instalado)
gh repo create news-enrichment-system --public --source=. --remote=origin --push

# OU manualmente:
# 1. Crie repo em https://github.com/new
# 2. Conecte e push:
git remote add origin https://github.com/seu-usuario/news-enrichment-system.git
git branch -M main
git push -u origin main
```

### 5. Atualizar README.md com seu GitHub

Edite [README.md](README.md) e substitua:
- `seu-usuario` pelo seu username do GitHub
- `seu-email@exemplo.com` pelo seu email

### 6. Adicionar Badges (Opcional)

Após primeiro push, você pode adicionar badges reais ao README:

```markdown
[![Tests](https://github.com/seu-usuario/news-enrichment-system/workflows/tests/badge.svg)](https://github.com/seu-usuario/news-enrichment-system/actions)
[![codecov](https://codecov.io/gh/seu-usuario/news-enrichment-system/branch/main/graph/badge.svg)](https://codecov.io/gh/seu-usuario/news-enrichment-system)
```

## Estrutura de Branches (Sugestão)

```
main                  # Código estável
├── develop          # Desenvolvimento
├── feature/xyz      # Features
└── docs/updates     # Atualizações de docs
```

## CI/CD (Futuro)

Para adicionar testes automáticos, crie `.github/workflows/tests.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      - run: pip install -r requirements.txt
      - run: pytest tests/
```

## Dúvidas?

Consulte a documentação completa em `docs/`
