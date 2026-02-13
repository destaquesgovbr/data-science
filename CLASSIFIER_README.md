# NewsClassifier - Classificação de Notícias sem Dataset

## Visão Geral

`NewsClassifier` é uma versão simplificada e standalone do sistema de enriquecimento, ideal para:

- **APIs REST** (FastAPI, Flask, Django)
- **Microserviços**
- **Integrações com sistemas externos**
- **Processamento em tempo real**

**Diferenças do sistema completo:**
- Não acessa base de dados (sem `NewsDatasetManager`)
- Recebe notícias via parâmetro (dict ou lista)
- Retorna apenas classificação JSON (sem salvar)
- Mais leve e portável

---

## Instalação

### Dependências

```bash
pip install boto3 pyyaml
```

### Módulo

```python
from news_enrichment import NewsClassifier
```

---

## Uso Básico

### 1. Inicialização

```python
from news_enrichment import NewsClassifier

# Com taxonomia predefinida (recomendado)
classifier = NewsClassifier(
    model_id="anthropic.claude-3-haiku-20240307-v1:0",
    region="us-east-1",
    taxonomy=taxonomy_dict,  # Carregado de arvore.yaml
    batch_size=4,
    sleep_between_batches=0.5,
    verbose=False
)

# Ou sem taxonomia (classificação orgânica)
classifier = NewsClassifier(
    model_id="anthropic.claude-3-haiku-20240307-v1:0",
    region="us-east-1",
    taxonomy=None
)
```

### 2. Classificar uma notícia

```python
noticia = {
    'title': 'Governo anuncia reforma tributária',
    'content': 'O governo federal lançou proposta...'
}

# Retorna dict
resultado = classifier.classify_single(noticia, return_format="dict")

# Ou retorna JSON string
resultado_json = classifier.classify_single(noticia, return_format="json")
```

**Saída:**
```json
{
  "theme_1_level_1": "Economia e Finanças",
  "theme_1_level_1_code": "01",
  "theme_1_level_1_label": "Economia e Finanças",
  "theme_1_level_2_code": "01.02",
  "theme_1_level_2_label": "Fiscalização e Tributação",
  "theme_1_level_3_code": "01.02.03",
  "theme_1_level_3_label": "Reforma Tributária",
  "most_specific_theme_code": "01.02.03",
  "most_specific_theme_label": "Reforma Tributária",
  "summary": "Governo federal anuncia proposta de reforma tributária..."
}
```

### 3. Classificar múltiplas notícias

```python
noticias = [
    {
        'title': 'Notícia 1',
        'content': 'Conteúdo 1...'
    },
    {
        'title': 'Notícia 2',
        'content': 'Conteúdo 2...'
    }
]

# Retorna lista de dicts
resultados = classifier.classify_batch(noticias, return_format="list")

# Ou retorna JSON string
resultados_json = classifier.classify_batch(noticias, return_format="json")
```

---

## Campos de Entrada

### Obrigatórios
- `title` (string) - Título da notícia
- `content` (string) - Conteúdo da notícia

### Opcionais
- `subtitle` (string) - Subtítulo
- `editorial_lead` (string) - Lead editorial
- `unique_id` (string) - ID único (mantido na saída para rastreabilidade)

---

## Campos de Saída

| Campo | Tipo | Descrição |
|-------|------|-----------|
| `theme_1_level_1` | string | Tema nível 1 |
| `theme_1_level_1_code` | string | Código nível 1 (ex: "01") |
| `theme_1_level_1_label` | string | Label nível 1 |
| `theme_1_level_2_code` | string | Código nível 2 (ex: "01.02") |
| `theme_1_level_2_label` | string | Label nível 2 |
| `theme_1_level_3_code` | string | Código nível 3 (ex: "01.02.03") |
| `theme_1_level_3_label` | string | Label nível 3 |
| `most_specific_theme_code` | string | Código do tema mais específico |
| `most_specific_theme_label` | string | Label do tema mais específico |
| `summary` | string | Resumo da notícia (2-3 frases) |
| `unique_id` | string | ID único (se fornecido na entrada) |

---

## Uso com FastAPI

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from news_enrichment import NewsClassifier
import yaml

# Setup
app = FastAPI()

# Carregar taxonomia
with open("arvore.yaml", "r", encoding="utf-8") as f:
    taxonomy_raw = yaml.safe_load(f)
    taxonomy = parse_taxonomy(taxonomy_raw)  # Função auxiliar

# Inicializar classificador (uma vez no startup)
classifier = NewsClassifier(
    model_id="anthropic.claude-3-haiku-20240307-v1:0",
    region="us-east-1",
    taxonomy=taxonomy,
    verbose=False
)

# Modelos Pydantic
class NewsRequest(BaseModel):
    title: str
    content: str
    subtitle: str | None = None
    editorial_lead: str | None = None
    unique_id: str | None = None

class NewsResponse(BaseModel):
    status: str
    message: str
    data: dict | None

# Endpoints
@app.post("/classify", response_model=NewsResponse)
def classify_news(news: NewsRequest):
    """Classifica uma única notícia."""
    try:
        result = classifier.classify_single(
            news.dict(exclude_none=True),
            return_format="dict"
        )
        return {
            "status": "success",
            "message": "Notícia classificada com sucesso",
            "data": result
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/classify/batch", response_model=NewsResponse)
def classify_batch(news_list: list[NewsRequest]):
    """Classifica múltiplas notícias."""
    try:
        results = classifier.classify_batch(
            [n.dict(exclude_none=True) for n in news_list],
            return_format="list"
        )
        return {
            "status": "success",
            "message": f"{len(results)} notícias classificadas",
            "data": results
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Health check
@app.get("/health")
def health():
    return {"status": "ok"}
```

---

## Uso com Flask

```python
from flask import Flask, request, jsonify
from news_enrichment import NewsClassifier
import yaml

app = Flask(__name__)

# Setup (carregar taxonomia e inicializar classificador)
# ... (mesmo código do FastAPI)

@app.route("/classify", methods=["POST"])
def classify_news():
    """Classifica uma única notícia."""
    try:
        news_data = request.json
        result = classifier.classify_single(news_data, return_format="dict")
        return jsonify({
            "status": "success",
            "message": "Notícia classificada com sucesso",
            "data": result
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "data": None
        }), 500

@app.route("/classify/batch", methods=["POST"])
def classify_batch():
    """Classifica múltiplas notícias."""
    try:
        news_list = request.json
        results = classifier.classify_batch(news_list, return_format="list")
        return jsonify({
            "status": "success",
            "message": f"{len(results)} notícias classificadas",
            "data": results
        })
    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e),
            "data": None
        }), 500

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
```

---

## Configuração AWS

O `NewsClassifier` usa a mesma configuração de credenciais AWS do sistema completo.

### Desenvolvimento Local

```bash
# Usar ~/.aws/credentials
aws configure
```

### Produção (Variáveis de Ambiente)

```bash
export AWS_ACCESS_KEY_ID="sua-key"
export AWS_SECRET_ACCESS_KEY="sua-secret"
export AWS_DEFAULT_REGION="us-east-1"
```

### Deploy em AWS (IAM Role)

```python
# Credenciais automáticas via IAM role (mais seguro)
classifier = NewsClassifier(
    model_id="anthropic.claude-3-haiku-20240307-v1:0",
    region="us-east-1"
)
# boto3 detecta IAM role automaticamente
```

---

## Taxomomia

### Carregar de YAML

```python
import yaml

with open("arvore.yaml", "r", encoding="utf-8") as f:
    taxonomy_raw = yaml.safe_load(f)

# Converter para formato esperado
taxonomy = parse_taxonomy(taxonomy_raw)

classifier = NewsClassifier(
    model_id="anthropic.claude-3-haiku-20240307-v1:0",
    region="us-east-1",
    taxonomy=taxonomy
)
```

### Ver Resumo da Taxonomia

```python
summary = classifier.get_taxonomy_summary()
print(summary)

# Output:
# {
#   'mode': 'predefined',
#   'level_1_categories': 25,
#   'level_2_categories': 98,
#   'level_3_categories': 287,
#   'total_categories': 410
# }
```

---

## Performance

### Configuração Recomendada

```python
classifier = NewsClassifier(
    model_id="anthropic.claude-3-haiku-20240307-v1:0",  # Haiku (rápido e barato)
    region="us-east-1",
    taxonomy=taxonomy,
    batch_size=4,              # Otimizado
    sleep_between_batches=0.5  # Evita throttling
)
```

### Métricas

- **Modelo**: Claude Haiku
- **Tempo médio**: ~2.9s por notícia
- **Custo**: ~$0.001 por notícia
- **Taxa de sucesso**: 100%
- **Batch processing**: 4 notícias em paralelo

---

## Exemplos

### Exemplo 1: Script standalone

Ver: [exemplo_classificacao.py](exemplo_classificacao.py)

### Exemplo 2: Simulação de API

Ver: [exemplo_api_classificacao.py](exemplo_api_classificacao.py)

---

## Comparação com Sistema Completo

| Aspecto | NewsEnricher (completo) | NewsClassifier (standalone) |
|---------|-------------------------|----------------------------|
| **Input** | Dataset Hugging Face | Parâmetros (dict/list) |
| **Output** | Parquet/CSV/Postgres | JSON/Dict |
| **Uso** | Processamento em batch | API/microserviço |
| **Dataset** | Requer NewsDatasetManager | Não requer |
| **Complexidade** | Mais complexo | Mais simples |
| **Portabilidade** | Média | Alta |

---

## Arquivos Necessários

Para usar o `NewsClassifier` em produção, você precisa apenas:

```
projeto/
├── news_enrichment/
│   ├── __init__.py
│   ├── llm_client.py      # Cliente Bedrock
│   └── classifier.py      # NewsClassifier
├── arvore.yaml            # Taxonomia (opcional)
└── seu_app.py             # Sua API/aplicação
```

**Não precisa:**
- `dataset_manager.py`
- `enricher.py`
- `postgres_exporter.py`
-  Dataset Hugging Face

---

## Próximos Passos

1. **Cache**: Adicionar Redis para classificações frequentes
2. **Rate Limiting**: Limitar requests por IP/token
3. **Autenticação**: Adicionar API keys
4. **Monitoramento**: Integrar com Prometheus/Grafana
5. **Async**: Versão async para FastAPI (usando `asyncio`)

---

## Suporte

- **Documentação completa**: [DOCUMENTACAO_PROMPTS.md](DOCUMENTACAO_PROMPTS.md)
- **Benchmarks**: [benchmark_prompts.py](benchmark_prompts.py)
- **Sistema completo**: [exemplo_enriquecimento.py](exemplo_enriquecimento.py)

---

**Status**: ✅ Pronto para produção
