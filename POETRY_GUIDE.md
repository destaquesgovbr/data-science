# Guia Rápido: Poetry

Este projeto usa **Poetry** para gerenciamento de dependências. Aqui estão os comandos mais úteis.

## Instalação Inicial

```bash
# Instalar Poetry (primeira vez)
curl -sSL https://install.python-poetry.org | python3 -

# Ou via pip
pip install poetry

# Instalar dependências do projeto
poetry install

# Instalar com grupos opcionais
poetry install --with dev --extras ml
```

## Comandos Úteis

### Gerenciar Ambiente Virtual

```bash
# Ativar ambiente virtual do Poetry
poetry shell

# Executar comando no ambiente do Poetry
poetry run python script.py

# Ver informações do ambiente
poetry env info

# Listar ambientes
poetry env list

# Remover ambiente atual
poetry env remove python
```

### Adicionar/Remover Dependências

```bash
# Adicionar nova dependência
poetry add pandas

# Adicionar dependência de dev
poetry add --group dev pytest

# Adicionar dependência opcional
poetry add --optional transformers

# Remover dependência
poetry remove pandas

# Atualizar uma dependência específica
poetry update pandas

# Atualizar todas
poetry update
```

### Verificar Dependências

```bash
# Ver dependências instaladas
poetry show

# Ver árvore de dependências
poetry show --tree

# Ver dependências desatualizadas
poetry show --outdated

# Verificar se há problemas
poetry check
```

### Build e Publicação

```bash
# Gerar requirements.txt (se necessário)
poetry export -f requirements.txt --output requirements.txt --without-hashes

# Build do projeto
poetry build

# Publicar no PyPI
poetry publish
```

## Estrutura do pyproject.toml

```toml
[tool.poetry.dependencies]
python = "^3.9"
polars = "^1.0.0"  # Dependências principais

[tool.poetry.group.dev.dependencies]
pytest = "^7.4.0"  # Dependências de desenvolvimento

[tool.poetry.extras]
ml = ["torch"]  # Dependências opcionais
```

## Instalação por Grupo

```bash
# Apenas produção
poetry install --only main

# Com desenvolvimento
poetry install --with dev

# Com extras (ML)
poetry install --extras ml

# Completo
poetry install --with dev --extras all
```

## Workflows Comuns

### Setup Inicial (Novo Desenvolvedor)

```bash
git clone <repo>
cd <repo>
poetry install --with dev
poetry shell
```

### Adicionar Nova Feature que Precisa de Lib

```bash
poetry add requests
# Desenvolver...
git add pyproject.toml
git commit -m "Add requests dependency"
```

### Rodar Testes

```bash
poetry run pytest
# ou
poetry shell
pytest
```

### Atualizar Projeto

```bash
git pull
poetry install  # Instala novas dependências
```

## Vantagens do Poetry

- ✅ Gerenciamento de dependências determinístico (poetry.lock)
- ✅ Ambiente virtual automático
- ✅ Resolução de conflitos de dependências
- ✅ Build e publicação simplificados
- ✅ Suporte a grupos de dependências (dev, docs, etc.)
- ✅ Dependências opcionais (extras)
- ✅ Compatível com pip (pode gerar requirements.txt)

## Troubleshooting

### Problema: "Poetry not found"

```bash
# Adicionar ao PATH (Linux/Mac)
export PATH="$HOME/.local/bin:$PATH"

# Verificar instalação
poetry --version
```

### Problema: Cache corrompido

```bash
poetry cache clear pypi --all
poetry install
```

### Problema: Ambiente virtual em local errado

```bash
# Configurar para criar venv na pasta do projeto
poetry config virtualenvs.in-project true

# Recriar ambiente
poetry env remove python
poetry install
```

## Migração de requirements.txt

Se você tem um projeto antigo com requirements.txt:

```bash
# 1. Criar pyproject.toml
poetry init

# 2. Adicionar dependências do requirements.txt
cat requirements.txt | xargs poetry add

# 3. Verificar
poetry check
```

## Links Úteis

- [Documentação Oficial](https://python-poetry.org/docs/)
- [Configuração](https://python-poetry.org/docs/configuration/)
- [Commands](https://python-poetry.org/docs/cli/)
