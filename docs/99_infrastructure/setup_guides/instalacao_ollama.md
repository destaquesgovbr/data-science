# Guia de Instalação e Uso - Ollama

## Instalação do Ollama

### Linux / macOS
```bash
curl -fsSL https://ollama.com/install.sh | sh
```

### Windows
Baixe o instalador em: https://ollama.com/download/windows

### Verificar Instalação
```bash
ollama --version
```

---

## Baixar Modelos Recomendados

### Tier 1 - Qualidade/Performance Balanceada (Recomendado)

**Qwen 2.5 7B** (4.7GB) - Melhor para português
```bash
ollama pull qwen2.5:7b
```

**DeepSeek R1 7B** (4.7GB) - Excelente raciocínio
```bash
ollama pull deepseek-r1:7b
```

**Mistral 7B** (4.1GB) - Clássico confiável
```bash
ollama pull mistral:7b
```

### Tier 2 - Mais Leves e Rápidos

**Qwen 2.5 3B** (2.0GB) - Rápido, surpreendentemente bom
```bash
ollama pull qwen2.5:3b
```

**Llama 3.2 3B** (2.0GB) - Muito rápido
```bash
ollama pull llama3.2:3b
```

---

## Uso Básico

### Iniciar Ollama (se não iniciou automaticamente)
```bash
ollama serve
```

### Testar Modelo
```bash
ollama run qwen2.5:7b
```

### Listar Modelos Instalados
```bash
ollama list
```

### Remover Modelo
```bash
ollama rm qwen2.5:7b
```

---

## Uso no Sistema de Enriquecimento

### 1. Verificar Ollama está rodando
```bash
curl http://localhost:11434/api/tags
```

### 2. Executar Script
```bash
python exemplo_enriquecimento_local.py
```

### 3. Escolher modelo no menu interativo
```
1. AWS Bedrock (pago)
2. Qwen 2.5 7B (local, gratuito) ← Recomendado
3. DeepSeek R1 7B (local, gratuito)
4. Mistral 7B (local, gratuito)
5. Qwen 2.5 3B (local, mais rápido)
```

---

## Uso Programático

### Opção 1: LocalLLMClient
```python
from news_enrichment import LocalLLMClient, NewsDatasetManager, NewsEnricher

# Setup
dataset_manager = NewsDatasetManager(cache_dir="./data")

# Cliente com Qwen 2.5 7B
llm_client = LocalLLMClient(
    model="qwen2.5:7b",
    base_url="http://localhost:11434",
    batch_size=4,
    temperature=0.3
)

# Enricher
enricher = NewsEnricher(dataset_manager, llm_client, verbose=True)

# Processar
sample = enricher.enrich_sample(n=10)
```

### Opção 2: Trocar entre Bedrock e Local
```python
from news_enrichment import BedrockLLMClient, LocalLLMClient

# Desenvolvimento local
llm_client = LocalLLMClient(model="qwen2.5:7b")

# Produção (AWS)
llm_client = BedrockLLMClient()

# Código do enricher é o mesmo!
enricher = NewsEnricher(dataset_manager, llm_client)
```

---

## Performance Esperada

### Hardware Recomendado
- **CPU**: 4+ cores
- **RAM**: 8GB+ (16GB recomendado para modelos 7B)
- **GPU** (opcional): NVIDIA com 6GB+ VRAM (acelera 3-5x)

### Tempos Estimados (qwen2.5:7b)

| Hardware | Tempo/notícia | 300k notícias |
|----------|---------------|---------------|
| CPU (8 cores) | ~2-3s | ~6-10 horas |
| GPU (RTX 3060) | ~0.5-1s | ~2-4 horas |
| GPU (RTX 4090) | ~0.2-0.4s | ~1-2 horas |

### Comparação com Bedrock

| Métrica | Bedrock (Claude Haiku) | Local (Qwen 2.5 7B) |
|---------|------------------------|---------------------|
| Custo | ~$150-200 (300k) | GRATUITO |
| Tempo | ~3-4 horas | ~6-10 horas (CPU) |
| Qualidade | Excelente | Muito boa |
| Privacidade | Dados na AWS | 100% local |
| Rate Limits | Sim | Não |

---

## Configuração GPU (Opcional)

### NVIDIA GPU
Ollama detecta automaticamente GPU NVIDIA. Sem configuração adicional.

### Verificar GPU
```bash
ollama run qwen2.5:7b "teste"
# Se GPU ativa, verá "GPU layers: XX"
```

### Forçar CPU (se GPU causar problemas)
```bash
OLLAMA_NUM_GPU=0 ollama serve
```

---

## Troubleshooting

### Ollama não está rodando
```bash
# Verificar status
curl http://localhost:11434/api/tags

# Se erro, iniciar manualmente
ollama serve
```

### Modelo não encontrado
```bash
# Listar modelos instalados
ollama list

# Baixar modelo
ollama pull qwen2.5:7b
```

### Erro de memória
- Use modelo menor: `qwen2.5:3b` ao invés de `7b`
- Reduza `batch_size` no código
- Feche outros programas

### Resposta muito lenta
- Verifique se GPU está sendo usada
- Reduza `batch_size` de 4 para 2
- Use modelo 3B ao invés de 7B

### JSON malformado nas respostas
- Ajuste `temperature` para 0.1 (mais determinístico)
- Aumente `max_retries` para 5

---

## Containerização (Docker)

Veja [Dockerfile.ollama](Dockerfile.ollama) para exemplo de container com Ollama.

```bash
# Build
docker build -f Dockerfile.ollama -t news-enrichment-local .

# Run
docker run -p 11434:11434 -v ./data:/app/data news-enrichment-local
```

---

## Próximos Passos

1. Instale Ollama
2. Baixe modelo: `ollama pull qwen2.5:7b`
3. Execute: `python exemplo_enriquecimento_local.py`
4. Compare qualidade com Bedrock
5. Escolha o melhor para seu caso de uso

**Recomendação:** Teste com amostra de 10 notícias primeiro para validar qualidade!
