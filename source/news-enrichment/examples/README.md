# Exemplos de Uso

Esta pasta contém exemplos práticos de como usar o sistema de enriquecimento de notícias.

## Exemplos Disponíveis

### 1. classificacao_simples.py
Demonstra o uso básico do `NewsClassifier` para classificar notícias individuais ou em batch.

```bash
python classificacao_simples.py
```

### 2. classificacao_api.py
Mostra como integrar o classificador em APIs REST (FastAPI/Flask).

```bash
python classificacao_api.py
```

### 3. enriquecimento_basico.py
Exemplo de enriquecimento de dataset completo com persistência.

```bash
python enriquecimento_basico.py
```

### 4. enriquecimento_otimizado.py
Versão otimizada para processar grandes volumes de notícias com paralelismo.

```bash
python enriquecimento_otimizado.py
```

## Configuração

Antes de executar os exemplos, certifique-se de:

1. Ter instalado as dependências: `pip install -r ../requirements.txt`
2. Ter configurado o arquivo `.env` com suas API keys
3. Ter o arquivo de taxonomia em `../data/arvore.yaml`

## Dúvidas

Consulte a documentação completa em `../docs/`
