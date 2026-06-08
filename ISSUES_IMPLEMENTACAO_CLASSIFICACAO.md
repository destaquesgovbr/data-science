# Issues: Implementação de Classificação com LLM em Produção

**Base:** Resultados da Issue #3 - Avaliação LLMs para Classificação  
**Status:** Backlog para implementação pós-pesquisa  
**Data:** Maio 2026

---

## Issue #8: Pipeline de Classificação Hierárquica de Notícias

**Tipo:** Implementação / Engenharia de Produção  
**Status:** Planejado  
**Prioridade:** Alta  
**Complexidade:** 4-6 semanas  
**Dependências:** Issue #3 (concluída)

### Contexto e Motivação

Com a conclusão da Issue #3, temos **decisão técnica clara**:

#### Resultado da Pesquisa (Issue #3)
- **Modelo selecionado:** Claude Haiku (via AWS Bedrock)
- **Accuracy:** 80.5% L3 (taxonomia hierárquica de 500 categorias)
- **Custo:** $97/mês (@1k classificações/dia)
- **Latência:** ~2-3s P95
- **Modelos locais testados:** 8 modelos (Llama, Qwen, Gemma, Phi-4, etc.)
  - Melhor: Llama 8B com 16% accuracy (5x pior que Claude)
  - Custo local: $434/mês + overhead de manutenção
  - **Conclusão:** Gap intransponível, não vale a pena

#### Aprendizados Chave
1. **Abordagem hierárquica** (L1 → L2 → L3) é essencial vs direta (0% accuracy)
2. **APIs comerciais** têm vantagem intransponível para tarefas complexas
3. **TCO local** é 2.5x maior que API (infra + manutenção + setup)
4. **Break-even** seria apenas >900k classificações/mês (~30k/dia)
5. Cliente não aceita 16% quando API entrega 80.5%

Agora precisamos **implementar sistema de classificação em produção**:
- Pipeline hierárquico (3 níveis: Tema → Subtema → Categoria)
- API REST para classificação sob demanda
- Monitoramento de qualidade e custo
- Cache para otimizar custo (notícias repetidas)

### Objetivo Geral

Implementar pipeline completo de classificação hierárquica ou direta:
- Classificar notícias em taxonomia de 500 categorias (3 níveis)
- API REST com Claude Haiku via AWS Bedrock
- Abordagem hierárquica (L1 → L2 → L3)
- Cache Redis para otimizar custos
- Monitoramento de accuracy e custo

### Abordagem Técnica

#### 1. Arquitetura do Sistema

```
┌─────────────────────────────────────┐
│  Notícia Nova                       │
│  - Título, conteúdo                 │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Cache Redis (opcional)             │
│  - Key: hash(texto)                 │
│  - Value: classificação L3          │
│  - TTL: 30 dias                     │
└──────────────┬──────────────────────┘
               │ (cache miss)
               ▼
┌─────────────────────────────────────┐
│  Pre-processamento                  │
│  - Limpeza de texto                 │
│  - Truncamento (100k tokens limite) │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Classificação Hierárquica          │
│  (Claude Haiku via Bedrock)         │
│                                     │
│  ETAPA 1: Nível L1 (Tema)           │
│  ├─ Prompt com 10 temas principais  │
│  └─ Output: tema selecionado        │
│                                     │
│  ETAPA 2: Nível L2 (Subtema)        │
│  ├─ Prompt com subtemas do L1       │
│  └─ Output: subtema selecionado     │
│                                     │
│  ETAPA 3: Nível L3 (Categoria)      │
│  ├─ Prompt com categorias do L2     │
│  └─ Output: categoria final         │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Validação e Logging                │
│  - Validar categoria existe         │
│  - Calcular confidence              │
│  - Log para auditoria               │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  Storage + Monitoring               │
│  - Salvar classificação             │
│  - Métricas: latência, custo, cache │
│  - Alertas: erro, accuracy drop     │
└─────────────────────────────────────┘
```

#### 2. Stack Tecnológica

**LLM:**
```python
import boto3

# Claude Haiku via AWS Bedrock
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')

MODEL_ID = 'anthropic.claude-haiku-20240307-v1:0'
```

**Cache:**
```python
import redis
import hashlib

# Redis para cache de classificações
redis_client = redis.Redis(host='localhost', port=6379, db=0)

def get_cache_key(text: str) -> str:
    """Hash do texto para cache."""
    return hashlib.sha256(text.encode()).hexdigest()
```

**API:**
```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI(title="News Classification API")
```

#### 3. Classificação Hierárquica (3 Etapas)

**Validado na Issue #3:** Abordagem hierárquica é ESSENCIAL (direta = 0% accuracy)

```python
class HierarchicalClassifier:
    """
    Classificação hierárquica em 3 etapas.
    Baseado nos resultados da Issue #3.
    """
    
    def __init__(self):
        self.bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
        self.model_id = 'anthropic.claude-haiku-20240307-v1:0'
        self.taxonomy = load_taxonomy()  # 500 categorias hierárquicas
    
    def classify(self, title: str, content: str) -> dict:
        """
        Classifica notícia em 3 etapas hierárquicas.
        
        Returns:
            {
                'L1': 'Governo e Políticas Públicas',
                'L2': 'Saúde Pública',
                'L3': 'Vacinação e Campanhas de Imunização',
                'confidence': 0.95,
                'latency': 2.3,
                'cost': 0.00009
            }
        """
        
        start = time.time()
        
        # ETAPA 1: Classificar L1 (Tema principal)
        l1_category = self._classify_l1(title, content)
        
        # ETAPA 2: Classificar L2 (Subtema dentro do L1)
        l2_category = self._classify_l2(title, content, l1_category)
        
        # ETAPA 3: Classificar L3 (Categoria específica dentro do L2)
        l3_category = self._classify_l3(title, content, l1_category, l2_category)
        
        latency = time.time() - start
        cost = self._calculate_cost(title, content)
        
        return {
            'L1': l1_category,
            'L2': l2_category,
            'L3': l3_category,
            'confidence': 'high',  # Claude geralmente confiante
            'latency': latency,
            'cost': cost
        }
    
    def _classify_l1(self, title: str, content: str) -> str:
        """
        ETAPA 1: Classificar tema principal (L1).
        ~10 categorias nível 1.
        """
        
        # Buscar categorias L1 da taxonomia
        l1_categories = self.taxonomy.get_l1_categories()
        
        prompt = f"""
Classifique esta notícia governamental brasileira em UM dos seguintes temas principais:

{self._format_categories(l1_categories)}

Notícia:
Título: {title}
Conteúdo: {content[:2000]}

Responda APENAS com o nome exato do tema, sem explicação adicional.

Tema:"""
        
        response = self._call_bedrock(prompt)
        l1_category = self._parse_response(response, l1_categories)
        
        return l1_category
    
    def _classify_l2(self, title: str, content: str, l1: str) -> str:
        """
        ETAPA 2: Classificar subtema (L2) dentro do tema L1.
        ~50 categorias nível 2.
        """
        
        # Buscar apenas subtemas do L1 selecionado
        l2_categories = self.taxonomy.get_l2_categories(l1)
        
        prompt = f"""
Esta notícia foi classificada como "{l1}".

Agora classifique em UM dos seguintes subtemas dentro de "{l1}":

{self._format_categories(l2_categories)}

Notícia:
Título: {title}
Conteúdo: {content[:2000]}

Responda APENAS com o nome exato do subtema, sem explicação adicional.

Subtema:"""
        
        response = self._call_bedrock(prompt)
        l2_category = self._parse_response(response, l2_categories)
        
        return l2_category
    
    def _classify_l3(self, title: str, content: str, l1: str, l2: str) -> str:
        """
        ETAPA 3: Classificar categoria específica (L3) dentro do subtema L2.
        ~500 categorias nível 3 (mas apenas ~10-20 por L2).
        """
        
        # Buscar apenas categorias do L2 selecionado
        l3_categories = self.taxonomy.get_l3_categories(l1, l2)
        
        prompt = f"""
Esta notícia foi classificada como:
- Tema: "{l1}"
- Subtema: "{l2}"

Agora classifique na categoria específica final dentro de "{l2}":

{self._format_categories(l3_categories)}

Notícia:
Título: {title}
Conteúdo: {content[:2000]}

Responda APENAS com o nome exato da categoria, sem explicação adicional.

Categoria:"""
        
        response = self._call_bedrock(prompt)
        l3_category = self._parse_response(response, l3_categories)
        
        return l3_category
    
    def _call_bedrock(self, prompt: str) -> str:
        """Chama Claude Haiku via Bedrock."""
        
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 100,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "temperature": 0,  # Determinístico
        }
        
        response = self.bedrock.invoke_model(
            modelId=self.model_id,
            body=json.dumps(body)
        )
        
        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text']
    
    def _parse_response(self, response: str, valid_categories: list) -> str:
        """
        Extrai categoria da resposta.
        Robustificação: Claude às vezes adiciona texto extra.
        """
        
        response = response.strip()
        
        # Checar match exato
        if response in valid_categories:
            return response
        
        # Fuzzy matching (case insensitive)
        for cat in valid_categories:
            if cat.lower() in response.lower():
                return cat
        
        # Fallback: primeira categoria válida (não deveria acontecer)
        logging.warning(f"Parse falhou: '{response}' não está em {valid_categories[:3]}...")
        return valid_categories[0]
    
    def _format_categories(self, categories: list) -> str:
        """Formata lista de categorias para prompt."""
        return '\n'.join([f"- {cat}" for cat in categories])
    
    def _calculate_cost(self, title: str, content: str) -> float:
        """
        Calcula custo aproximado da classificação.
        
        Claude Haiku pricing (Bedrock):
        - Input: $0.25 / 1M tokens
        - Output: $1.25 / 1M tokens
        """
        
        # Estimativa conservadora
        input_tokens = (len(title) + len(content[:2000])) / 4  # ~4 chars/token
        input_tokens *= 3  # 3 chamadas (L1, L2, L3)
        
        output_tokens = 30 * 3  # ~30 tokens por resposta × 3 chamadas
        
        cost_input = (input_tokens / 1_000_000) * 0.25
        cost_output = (output_tokens / 1_000_000) * 1.25
        
        return cost_input + cost_output
```

#### 4. Cache para Otimização de Custos

**Problema:** Notícias podem ser processadas múltiplas vezes (republicações, edições)

**Solução:** Cache Redis com TTL de 30 dias

```python
import redis
import hashlib
import json

redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

def classify_with_cache(title: str, content: str) -> dict:
    """
    Classifica com cache para economizar custos.
    """
    
    # 1. Gerar cache key
    cache_key = hashlib.sha256(f"{title}{content}".encode()).hexdigest()
    
    # 2. Verificar cache
    cached = redis_client.get(cache_key)
    
    if cached:
        result = json.loads(cached)
        result['cache_hit'] = True
        result['cost'] = 0  # Cache = custo zero
        return result
    
    # 3. Cache miss: classificar
    classifier = HierarchicalClassifier()
    result = classifier.classify(title, content)
    
    # 4. Salvar no cache (TTL 30 dias)
    redis_client.setex(
        cache_key,
        30 * 24 * 3600,  # 30 dias
        json.dumps(result)
    )
    
    result['cache_hit'] = False
    return result
```

**Economia esperada:**
- ~20-30% notícias são republicadas/editadas
- Cache hit = $0 (vs $0.00009/classificação)
- Economia: ~$20-30/mês em @1k/dia

#### 5. API REST

```python
from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
import time

app = FastAPI(title="News Classification API")

class ClassificationRequest(BaseModel):
    title: str
    content: str
    use_cache: bool = True

class ClassificationResponse(BaseModel):
    L1: str
    L2: str
    L3: str
    confidence: str
    latency: float
    cost: float
    cache_hit: bool
    timestamp: str

@app.post("/api/v1/classify", response_model=ClassificationResponse)
async def classify_news(
    request: ClassificationRequest,
    api_key: str = Header(..., alias="X-API-Key")
):
    """
    Classifica notícia em taxonomia hierárquica de 500 categorias.
    
    Exemplo:
    ```bash
    curl -X POST http://localhost:8000/api/v1/classify \
      -H "X-API-Key: xxx" \
      -H "Content-Type: application/json" \
      -d '{
        "title": "Ministério da Saúde anuncia campanha de vacinação",
        "content": "O Ministério da Saúde anunciou hoje...",
        "use_cache": true
      }'
    ```
    
    Response:
    ```json
    {
      "L1": "Governo e Políticas Públicas",
      "L2": "Saúde Pública",
      "L3": "Vacinação e Campanhas de Imunização",
      "confidence": "high",
      "latency": 2.3,
      "cost": 0.00009,
      "cache_hit": false,
      "timestamp": "2026-05-21T10:30:00Z"
    }
    ```
    """
    
    # Validar API key
    if not validate_api_key(api_key):
        raise HTTPException(status_code=401, detail="Invalid API key")
    
    # Validar input
    if len(request.title) < 10:
        raise HTTPException(status_code=400, detail="Title too short")
    
    if len(request.content) < 50:
        raise HTTPException(status_code=400, detail="Content too short")
    
    # Classificar (com ou sem cache)
    if request.use_cache:
        result = classify_with_cache(request.title, request.content)
    else:
        classifier = HierarchicalClassifier()
        result = classifier.classify(request.title, request.content)
        result['cache_hit'] = False
    
    return ClassificationResponse(
        L1=result['L1'],
        L2=result['L2'],
        L3=result['L3'],
        confidence=result['confidence'],
        latency=result['latency'],
        cost=result['cost'],
        cache_hit=result['cache_hit'],
        timestamp=datetime.now().isoformat(),
    )

@app.get("/health")
async def health_check():
    """Health check endpoint."""
    
    # Testar Bedrock connection
    try:
        bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')
        # Simple ping
        return {"status": "healthy", "bedrock": "connected"}
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return classification_metrics.export_prometheus()

@app.get("/stats")
async def stats():
    """Estatísticas de uso."""
    
    stats = {
        'total_classifications': get_total_classifications(),
        'cache_hit_rate': get_cache_hit_rate(),
        'avg_latency': get_avg_latency(),
        'cost_today': get_cost_today(),
        'cost_month': get_cost_month(),
        'accuracy_l1': get_accuracy_l1(),  # Se houver validação
        'accuracy_l2': get_accuracy_l2(),
        'accuracy_l3': get_accuracy_l3(),
    }
    
    return stats
```

#### 6. Monitoramento

```python
from prometheus_client import Counter, Histogram, Gauge

class ClassificationMetrics:
    """
    Coleta métricas de classificação.
    """
    
    def __init__(self):
        # Contadores
        self.total = Counter(
            'classifications_total',
            'Total de classificações',
            ['level']  # L1, L2, L3
        )
        
        self.cache_hits = Counter(
            'cache_hits_total',
            'Total de cache hits'
        )
        
        # Histogramas
        self.latency = Histogram(
            'classification_latency_seconds',
            'Latência de classificação',
            ['level']
        )
        
        # Custo
        self.cost = Counter(
            'classification_cost_usd',
            'Custo acumulado (USD)'
        )
        
        # Gauges
        self.cache_hit_rate = Gauge(
            'cache_hit_rate',
            'Taxa de cache hit'
        )
    
    def log_classification(self, result: dict):
        """Log classificação bem-sucedida."""
        
        self.total.labels(level='L3').inc()
        self.latency.labels(level='L3').observe(result['latency'])
        self.cost.inc(result['cost'])
        
        if result['cache_hit']:
            self.cache_hits.inc()
        
        # Atualizar cache hit rate
        total = sum([m.samples[0].value for m in self.total.collect()])
        hits = sum([m.samples[0].value for m in self.cache_hits.collect()])
        self.cache_hit_rate.set(hits / total if total > 0 else 0)

# Alertas
def setup_alerts():
    """
    Alertas baseados em métricas.
    """
    
    # Alerta 1: Custo diário > $5 (anomalia)
    # Alerta 2: Latência P95 > 5s
    # Alerta 3: Cache hit rate < 10% (esperado ~20-30%)
    # Alerta 4: Accuracy L3 < 75% (se houver validação humana)
    
    pass  # Integrar com CloudWatch/Slack
```

### Entregas Planejadas (Deliverables)

#### Core (obrigatório para produção):

1. **`hierarchical_classifier.py`** - Classe de classificação 3 etapas
2. **`taxonomy.py`** - Gerenciamento da taxonomia hierárquica (500 categorias)
3. **`cache_manager.py`** - Cache Redis com TTL
4. **`api/main.py`** - API REST com FastAPI
5. **`monitoring/metrics.py`** - Métricas Prometheus
6. **`tests/test_classifier.py`** - Testes de qualidade
7. **`tests/test_hierarchy.py`** - Validar abordagem hierárquica
8. **`docs/API.md`** - Documentação da API
9. **`docs/TAXONOMY.md`** - Documentação da taxonomia
10. **Docker setup** - Container para API

#### Otimizações (pós-MVP):

11. **Validação humana** - Sample mensal para medir accuracy real
12. **Confidence scoring** - Detectar classificações duvidosas
13. **A/B test** - Validar se hierárquica continua melhor que direta

### Métricas de Sucesso

**Qualidade (baseline Issue #3):**
- ✅ Accuracy L3 > 75% (baseline: 80.5%)
- ✅ Accuracy L1 > 95%
- ✅ Accuracy L2 > 85%

**Performance:**
- ✅ Latência P95 < 5s (baseline: 2-3s)
- ✅ Disponibilidade > 99.5%
- ✅ Cache hit rate > 20%

**Custo:**
- ✅ Custo/mês < $150 (@1k/dia)
- ✅ Economia via cache: $20-30/mês

### Cronograma Estimado

**Sprint 1 (Setup e Core):** 2 semanas
- Configurar AWS Bedrock
- Implementar HierarchicalClassifier
- Carregar taxonomia de 500 categorias

**Sprint 2 (API e Cache):** 1 semana
- API REST com FastAPI
- Cache Redis
- Testes básicos

**Sprint 3 (Monitoramento):** 1 semana
- Métricas Prometheus
- Dashboard
- Alertas

**Sprint 4 (Deploy e Validação):** 1 semana
- Deploy em staging
- Validação com sample
- Deploy produção

**Total:** 5 semanas

### Riscos e Mitigações

| Risco | Probabilidade | Impacto | Mitigação |
|-------|---------------|---------|-----------|
| **Throttling Bedrock** | Baixa | Médio | Retry exponencial + monitoramento |
| **Custo inesperado** | Baixa | Alto | Alertas de custo + cache agressivo |
| **Taxonomy desatualizada** | Média | Médio | Processo de atualização documentado |
| **Accuracy degradar** | Baixa | Alto | Validação humana mensal (sample) |

### Decisões Técnicas Chave

#### 1. Por que Claude Haiku (não local)?

**Baseado na Issue #3:**
- Claude: 80.5% accuracy L3
- Melhor local (Llama 8B): 16% accuracy (5x pior)
- Claude: $97/mês vs Local $434/mês (@1k/dia)
- TCO local: 2.5x maior (infra + manutenção)

**Decisão:** Não há cenário onde local compensa

#### 2. Por que abordagem hierárquica?

**Baseado na Issue #3:**
- Hierárquica: 80.5% L3
- Direta (500 categorias simultâneas): 0% L3
- Prompt de 500 categorias sobrecarrega modelo

**Decisão:** Hierárquica é ESSENCIAL

#### 3. Cache: Redis vs DynamoDB?

| Aspecto | Redis | DynamoDB |
|---------|-------|----------|
| **Latência** | ~1ms | ~10ms |
| **Custo** | $15/mês (t4g.small) | $5-10/mês |
| **Simplicidade** | +++ | ++ |

**Decisão:** Redis (latência crítica)

### Referências

- **Documento de pesquisa:** Issue #3 - Relatório Executivo Final
- **Modelo:** Claude Haiku (anthropic.claude-haiku-20240307-v1:0)
- **AWS Bedrock Docs:** https://docs.aws.amazon.com/bedrock/

### Aprovações Necessárias

- [ ] Acesso AWS Bedrock (credenciais de produção)
- [ ] Budget: $150/mês para Claude Haiku (@1k/dia)
- [ ] Redis: t4g.small ($15/mês) ou ElastiCache
- [ ] Taxonomia de 500 categorias (arquivo YAML/JSON)

---

## Sub-Issues Detalhadas

### Issue #8.1: HierarchicalClassifier
**Estimativa:** 1 semana  
**Entrega:** Classe de classificação 3 etapas funcionando

### Issue #8.2: Taxonomia
**Estimativa:** 3 dias  
**Entrega:** Carregar e gerenciar 500 categorias hierárquicas

### Issue #8.3: Cache Redis
**Estimativa:** 2 dias  
**Entrega:** Cache com TTL funcionando

### Issue #8.4: API REST
**Estimativa:** 1 semana  
**Entrega:** Endpoint `/classify` documentado

### Issue #8.5: Monitoramento
**Estimativa:** 3 dias  
**Entrega:** Métricas + dashboard + alertas

### Issue #8.6: Deploy
**Estimativa:** 1 semana  
**Entrega:** Produção estável com validação

---

## Priorização

### P0 - Crítico (MVP)
#8.1, #8.2, #8.3, #8.4, #8.6

### P1 - Alta
#8.5

---

**Estimativa Total:** ~5 semanas (1 dev full-time)

**Baseline validado:** 80.5% accuracy L3, $97/mês, ~2-3s latência (Issue #3)
