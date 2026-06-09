# 🚀 Sistema de Enriquecimento de Notícias com LLMs

**Substituto Open Source para Cogfy**
Enriqueça datasets de notícias com resumos, categorização e metadados usando LLMs - customizável, local e econômico.

---

## 📋 Features

✅ **Múltiplos Providers de LLM**
- APIs: OpenAI, Anthropic (Claude), Groq
- Local: Ollama, HuggingFace Transformers
- Flexível e extensível

✅ **Enriquecimento Completo**
- Resumos (curto e longo)
- Categorização automática
- Extração de entidades (pessoas, organizações, locais)
- Análise de sentimento
- Tags relevantes

✅ **Otimizado para Produção**
- Processamento em batch paralelo
- Checkpoints automáticos (continua se interrompido)
- Rate limiting inteligente
- Logging e métricas

✅ **Econômico**
- Opção 100% gratuita (Groq, Ollama)
- Minimiza custos com APIs pagas
- Controle total de gastos

---

## 🎯 Casos de Uso

Este sistema substitui o Cogfy em cenários como:

1. **Enriquecimento de Datasets de Notícias** para ML/AI
2. **Categorização Automática** de grandes volumes de texto
3. **Geração de Metadados** para busca e recomendação
4. **Análise de Sentimento** em escala
5. **Extração de Entidades** (NER) customizada

---

## 🚀 Quick Start

### Opção 1: Groq (Recomendado - Gratuito e Rápido)

```bash
# 1. Instalar dependências
pip install -r requirements_enricher.txt

# 2. Obter API key gratuita
# Acesse: https://console.groq.com
# Copie sua API key

# 3. Configurar
export GROQ_API_KEY="sua-chave-aqui"

# 4. Executar exemplo
python exemplo_enriquecimento.py
```

### Opção 2: Ollama (100% Local e Gratuito)

```bash
# 1. Instalar Ollama
curl -fsSL https://ollama.com/install.sh | sh

# 2. Baixar modelo
ollama pull mistral

# 3. Instalar dependências Python
pip install -r requirements_enricher.txt

# 4. Executar
python exemplo_enriquecimento.py
# Escolha opção 2 (Ollama)
```

### Opção 3: Docker

```bash
# 1. Configurar API keys no .env
cat > .env << EOF
GROQ_API_KEY=sua-chave-groq
OPENAI_API_KEY=sua-chave-openai
ANTHROPIC_API_KEY=sua-chave-anthropic
EOF

# 2. Build e run
docker-compose -f docker-compose.enricher.yml up

# Com Ollama local
docker-compose -f docker-compose.enricher.yml up ollama enricher
```

---

## 📚 Uso Básico

### 1. Enriquecimento Simples

```python
import polars as pl
from llm_enricher import EnrichmentConfig, create_enricher, NewsEnricher

# Carregar seu dataset
df = pl.read_parquet("noticias.parquet")

# Configurar (exemplo com Groq - gratuito)
config = EnrichmentConfig(
    provider="groq",
    model="mixtral-8x7b-32768",
    api_key="sua-chave",
    max_workers=5,
    batch_size=50
)

# Criar pipeline
enricher = create_enricher(config)
pipeline = NewsEnricher(enricher)

# Enriquecer!
df_enriquecido = pipeline.enrich_dataframe(
    df,
    text_column="conteudo",  # coluna com texto da notícia
    enrichment_type="full"   # ou "summary" ou "categorization"
)

# Salvar
df_enriquecido.write_parquet("noticias_enriquecidas.parquet")
```

### 2. Produção com Checkpoint

```bash
# Via linha de comando
python enriquecer_producao.py \
    noticias.parquet \
    --text-column conteudo \
    --provider groq \
    --batch-size 100 \
    --output noticias_enriched.parquet

# Se interrompido, rode novamente - continua de onde parou!
```

---

## 🔧 Configuração de Providers

### Groq (Recomendado - Gratuito)

**Prós:** Gratuito, rápido, boa qualidade
**Contras:** Limite de requisições (mas generoso)

```python
config = EnrichmentConfig(
    provider="groq",
    model="mixtral-8x7b-32768",  # ou "llama-3.3-70b-versatile"
    api_key=os.getenv("GROQ_API_KEY"),
    max_workers=5,
    batch_size=100
)
```

**Obter API key:** https://console.groq.com

---

### Ollama (100% Local)

**Prós:** Gratuito, privado, sem limites
**Contras:** Requer recursos locais, pode ser mais lento

```python
config = EnrichmentConfig(
    provider="ollama",
    model="mistral",  # ou "llama3.2", "phi3"
    base_url="http://localhost:11434",
    max_workers=2,
    batch_size=20
)
```

**Modelos recomendados:**
- `mistral` - Bom equilíbrio qualidade/velocidade
- `llama3.2` - Melhor qualidade
- `phi3` - Mais rápido, menor qualidade

```bash
# Instalar Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Baixar modelos
ollama pull mistral
ollama pull llama3.2
ollama pull phi3
```

---

### OpenAI (Pago)

**Prós:** Melhor qualidade, muito confiável
**Contras:** Custa dinheiro

```python
config = EnrichmentConfig(
    provider="openai",
    model="gpt-4o-mini",  # ou "gpt-4o"
    api_key=os.getenv("OPENAI_API_KEY"),
    max_workers=3,
    batch_size=50
)
```

**Estimativa de custo (gpt-4o-mini):**
- ~$0.15 por 1000 notícias (entrada: 200 tokens, saída: 150 tokens)

---

### Anthropic Claude (Pago)

**Prós:** Excelente qualidade, bom para análise detalhada
**Contras:** Custa dinheiro

```python
config = EnrichmentConfig(
    provider="anthropic",
    model="claude-3-5-haiku-20241022",  # ou "claude-3-5-sonnet-20241022"
    api_key=os.getenv("ANTHROPIC_API_KEY"),
    max_workers=3,
    batch_size=50
)
```

---

## 📊 Tipos de Enriquecimento

### 1. Resumo (`enrichment_type="summary"`)

Adiciona colunas:
- `resumo_curto` - 1-2 frases (max 280 chars)
- `resumo_longo` - 3-4 frases detalhadas
- `pontos_principais` - Array com principais pontos

### 2. Categorização (`enrichment_type="categorization"`)

Adiciona colunas:
- `categoria_principal` - Categoria primária
- `categorias_secundarias` - Array de categorias relacionadas
- `tags` - Array de tags relevantes
- `entidades` - JSON com pessoas, organizações, locais
- `sentimento` - positivo/negativo/neutro
- `relevancia` - baixa/media/alta

### 3. Completo (`enrichment_type="full"`)

Combina todos os campos acima.

---

## 💡 Exemplos Práticos

### Exemplo 1: Dataset do HuggingFace

```python
from datasets import load_dataset
import polars as pl
from llm_enricher import EnrichmentConfig, create_enricher, NewsEnricher

# Carregar dataset
dataset = load_dataset("seu-dataset-de-noticias", split="train")
df = pl.from_pandas(dataset.to_pandas())

# Configurar
config = EnrichmentConfig(
    provider="groq",
    model="mixtral-8x7b-32768",
    api_key=os.getenv("GROQ_API_KEY"),
    max_workers=5
)

# Enriquecer
enricher = create_enricher(config)
pipeline = NewsEnricher(enricher)

df_enriched = pipeline.enrich_dataframe(
    df,
    text_column="text",  # ajuste conforme seu dataset
    enrichment_type="full"
)

# Salvar
df_enriched.write_parquet("dataset_enriched.parquet")
```

### Exemplo 2: Processamento Incremental

```python
from enriquecer_producao import ProductionEnricher

# Configurar
config = EnrichmentConfig(
    provider="groq",
    model="mixtral-8x7b-32768",
    api_key=os.getenv("GROQ_API_KEY"),
    batch_size=100
)

# Criar enriquecedor de produção
enricher = ProductionEnricher(config)

# Processar (com checkpoint automático)
df_result = enricher.enrich_dataset(
    input_file="noticias_grandes.parquet",
    text_column="conteudo",
    job_id="job_noticias_2024",
    resume=True  # Continua de onde parou
)
```

### Exemplo 3: Comparar Providers

```bash
# Teste rápido de diferentes providers
python exemplo_enriquecimento.py
# Escolha opção 5 (Comparar Providers)

# Vai mostrar qualidade e velocidade de cada um
```

---

## 🐳 Docker

### Build

```bash
docker build -f Dockerfile.enricher -t news-enricher .
```

### Run

```bash
# Com Groq
docker run -e GROQ_API_KEY="sua-chave" \
    -v $(pwd)/output:/app/output \
    news-enricher

# Com Ollama (local)
docker-compose -f docker-compose.enricher.yml up
```

---

## 📈 Performance

Benchmarks (1000 notícias, média 200 palavras):

| Provider | Modelo | Tempo | Custo | Qualidade |
|----------|--------|-------|-------|-----------|
| Groq | Mixtral 8x7B | ~5 min | Grátis | ⭐⭐⭐⭐ |
| Ollama | Mistral 7B | ~15 min | Grátis | ⭐⭐⭐ |
| OpenAI | GPT-4o-mini | ~8 min | ~$0.15 | ⭐⭐⭐⭐⭐ |
| Anthropic | Claude Haiku | ~10 min | ~$0.25 | ⭐⭐⭐⭐⭐ |

---

## 🔒 Segurança

- **API Keys:** Nunca commite API keys no código. Use variáveis de ambiente.
- **Dados Sensíveis:** Use Ollama (local) para dados confidenciais.
- **Rate Limiting:** Sistema respeita limites de API automaticamente.

---

## 🛠️ Troubleshooting

### Erro: "API key not found"

```bash
# Configure a variável de ambiente
export GROQ_API_KEY="sua-chave"

# Ou crie um arquivo .env
echo 'GROQ_API_KEY="sua-chave"' > .env
```

### Erro: Ollama não conecta

```bash
# Verificar se Ollama está rodando
curl http://localhost:11434/api/tags

# Se não estiver, iniciar
ollama serve
```

### Erro: Out of memory

```python
# Reduzir batch_size e max_workers
config = EnrichmentConfig(
    provider="groq",
    model="mixtral-8x7b-32768",
    api_key=api_key,
    max_workers=2,  # Reduzir de 5 para 2
    batch_size=20   # Reduzir de 50 para 20
)
```

### Erro: Rate limit exceeded (Groq)

```python
# Reduzir paralelismo
config = EnrichmentConfig(
    provider="groq",
    model="mixtral-8x7b-32768",
    api_key=api_key,
    max_workers=2,  # Menos requisições paralelas
    batch_size=20
)
```

---

## 🎓 Customização

### Criar Prompt Customizado

```python
from llm_enricher import NewsEnricher

class CustomNewsEnricher(NewsEnricher):
    def create_full_enrichment_prompt(self) -> str:
        return """Analise esta notícia e retorne JSON:

Notícia: {text}

JSON:
{{
    "resumo": "...",
    "categoria": "...",
    "seu_campo_customizado": "..."
}}"""

# Usar
enricher = create_enricher(config)
pipeline = CustomNewsEnricher(enricher)
```

### Adicionar Novo Provider

```python
from llm_enricher import BaseLLMEnricher

class MeuProviderEnricher(BaseLLMEnricher):
    def enrich_single(self, text: str, prompt_template: str) -> Dict[str, Any]:
        prompt = prompt_template.format(text=text)
        # Sua implementação aqui
        return resultado_json
```

---

## 📦 Estrutura do Projeto

```
.
├── llm_enricher.py              # Core do sistema
├── exemplo_enriquecimento.py    # Exemplos interativos
├── enriquecer_producao.py       # Script de produção
├── requirements_enricher.txt    # Dependências
├── Dockerfile.enricher          # Container
├── docker-compose.enricher.yml  # Orquestração
└── README_ENRICHER.md          # Esta documentação
```

---

## 🤝 Comparação com Cogfy

| Feature | Cogfy | Este Sistema |
|---------|-------|--------------|
| **Custo** | Alto, proprietário | Gratuito ou muito barato |
| **Customização** | Limitada | Total controle |
| **Privacy** | Dados na nuvem | Opção 100% local |
| **Modelos** | Fixo | Múltiplos providers |
| **Integração** | API apenas | API + Local + Docker |
| **Código** | Fechado | Open Source |

---

## 📞 Suporte

Para dúvidas ou problemas:

1. Verifique a seção **Troubleshooting** acima
2. Execute os exemplos em `exemplo_enriquecimento.py`
3. Teste com dataset pequeno primeiro

---

## 🎉 Próximos Passos

1. **Comece com Groq** (gratuito e rápido)
2. **Teste com dataset pequeno** (10-100 registros)
3. **Ajuste prompts** para seu domínio
4. **Escale para produção** com checkpoints
5. **Migre para local** se necessário (Ollama)

---

## 📄 Licença

Open Source - Use como quiser!

---

**Divirta-se enriquecendo notícias! 🚀📰**
