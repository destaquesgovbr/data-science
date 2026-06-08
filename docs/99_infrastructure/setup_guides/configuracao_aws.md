# Configuração AWS - Guia de Portabilidade

O sistema de enriquecimento de notícias foi projetado para funcionar em **qualquer ambiente** sem alterações no código.

## Modos de Autenticação

### 1. Desenvolvimento Local (Padrão)
Usa credenciais locais automaticamente.

```python
from news_enrichment import BedrockLLMClient

# Usa ~/.aws/credentials ou variáveis de ambiente locais
client = BedrockLLMClient(
    model_id="anthropic.claude-3-haiku-20240307-v1:0",
    region="us-east-1"
)
```

**Configuração necessária:**
```bash
# Via AWS CLI
aws configure

# Ou manualmente em ~/.aws/credentials:
[default]
aws_access_key_id = YOUR_ACCESS_KEY
aws_secret_access_key = YOUR_SECRET_KEY
```

---

### 2. Produção com Variáveis de Ambiente
Ideal para containers, CI/CD, e ambientes cloud.

```bash
# Configurar no ambiente de deploy
export AWS_ACCESS_KEY_ID="sua-access-key"
export AWS_SECRET_ACCESS_KEY="sua-secret-key"
export AWS_DEFAULT_REGION="us-east-1"
```

```python
from news_enrichment import BedrockLLMClient

# Código usa automaticamente as variáveis de ambiente
client = BedrockLLMClient(
    model_id="anthropic.claude-3-haiku-20240307-v1:0",
    region="us-east-1"
)
```

**Onde configurar:**
- Docker: No `docker-compose.yml` ou `Dockerfile`
- Kubernetes: Em Secrets ou ConfigMaps
- CI/CD: Nas variáveis de ambiente do pipeline
- Cloud Run/ECS: Nas configurações de ambiente do serviço

---

### 3. Produção com Credenciais Explícitas
Útil quando credenciais vêm de secrets managers ou arquivos customizados.

```python
import os
from news_enrichment import BedrockLLMClient

# Ler credenciais de variáveis de ambiente
client = BedrockLLMClient(
    model_id="anthropic.claude-3-haiku-20240307-v1:0",
    region="us-east-1",
    aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
    aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY")
)
```

Ou com AWS Secrets Manager:
```python
import boto3
import json
from news_enrichment import BedrockLLMClient

# Buscar credenciais do Secrets Manager
secrets_client = boto3.client('secretsmanager', region_name='us-east-1')
response = secrets_client.get_secret_value(SecretId='bedrock-credentials')
credentials = json.loads(response['SecretString'])

# Usar credenciais
client = BedrockLLMClient(
    model_id="anthropic.claude-3-haiku-20240307-v1:0",
    region="us-east-1",
    aws_access_key_id=credentials['access_key_id'],
    aws_secret_access_key=credentials['secret_access_key']
)
```

---

### 4. Deploy em AWS (EC2/ECS/Lambda) - **RECOMENDADO**
**Mais seguro** - usa IAM roles sem credenciais explícitas.

```python
from news_enrichment import BedrockLLMClient

# Usa IAM role automaticamente - SEM credenciais hardcoded!
client = BedrockLLMClient(
    model_id="anthropic.claude-3-haiku-20240307-v1:0",
    region="us-east-1"
)
# boto3 detecta automaticamente IAM role da instância/container
```

**Configuração necessária:**
1. Criar IAM role com política Bedrock:
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream"
      ],
      "Resource": "arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-3-haiku-20240307-v1:0"
    }
  ]
}
```

2. Anexar role à instância EC2, task definition (ECS) ou função Lambda

**Vantagens:**
- ✅ Sem credenciais no código ou variáveis de ambiente
- ✅ Rotação automática de credenciais
- ✅ Mais seguro (princípio de privilégio mínimo)

---

## Ordem de Precedência

O boto3 busca credenciais nesta ordem:

1. **Parâmetros explícitos** (`aws_access_key_id`, `aws_secret_access_key`)
2. **Variáveis de ambiente** (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`)
3. **Arquivo local** (`~/.aws/credentials`)
4. **IAM role** (se rodando em EC2/ECS/Lambda)

Isso garante flexibilidade máxima sem alteração de código.

---

## Testando Configuração

### Verificar credenciais ativas:
```bash
aws sts get-caller-identity
```

### Testar acesso ao Bedrock:
```python
from news_enrichment import BedrockLLMClient

try:
    client = BedrockLLMClient()
    print("✅ Cliente Bedrock inicializado com sucesso")
    print(f"Região: {client.region}")
    print(f"Modelo: {client.model_id}")
except Exception as e:
    print(f"❌ Erro: {e}")
```

---

## Troubleshooting

### Erro: "Unable to locate credentials"
**Causa:** Nenhuma credencial configurada

**Solução:**
1. Verificar variáveis de ambiente: `echo $AWS_ACCESS_KEY_ID`
2. Verificar arquivo: `cat ~/.aws/credentials`
3. Configurar: `aws configure`

### Erro: "AccessDeniedException"
**Causa:** Credenciais sem permissão para Bedrock

**Solução:** Adicionar política `AmazonBedrockFullAccess` ou criar política customizada

### Erro: "ValidationException: The provided model identifier is invalid"
**Causa:** Modelo não disponível na região

**Solução:** Verificar se Claude 3 Haiku está disponível em `us-east-1`:
```bash
aws bedrock list-foundation-models --region us-east-1 | grep claude
```

---

## Recomendações de Segurança

1. **Nunca commitar credenciais** no código ou git
2. **Usar IAM roles** sempre que possível (em AWS)
3. **Rotacionar credenciais** periodicamente
4. **Usar princípio de privilégio mínimo** (só permissões necessárias)
5. **Monitorar uso** com CloudTrail e CloudWatch

---

## Exemplo Completo

```python
#!/usr/bin/env python3
"""
Exemplo de uso portável do sistema de enriquecimento
Funciona em qualquer ambiente sem alteração
"""

from news_enrichment import NewsDatasetManager, BedrockLLMClient, NewsEnricher

def main():
    # Setup - funciona em qualquer ambiente
    dataset_manager = NewsDatasetManager(cache_dir="./data")

    # Cliente LLM - detecta automaticamente credenciais
    llm_client = BedrockLLMClient(
        model_id="anthropic.claude-3-haiku-20240307-v1:0",
        region="us-east-1",
        batch_size=8,
        sleep_between_batches=0.2
        # Não precisa passar credenciais - detecta automaticamente!
    )

    # Enriquecedor
    enricher = NewsEnricher(
        dataset_manager=dataset_manager,
        llm_client=llm_client,
        verbose=True
    )

    # Processar amostra
    sample = enricher.enrich_sample(n=10, seed=42)
    print(f"✅ Processadas {len(sample)} notícias com sucesso")

if __name__ == "__main__":
    main()
```

**Este mesmo código funciona em:**
- ✅ Laptop de desenvolvimento (macOS/Linux/Windows)
- ✅ Containers Docker
- ✅ CI/CD (GitHub Actions, GitLab CI, etc.)
- ✅ Cloud Run, AWS ECS, Azure Container Instances
- ✅ AWS Lambda, EC2, Fargate
- ✅ Servidores on-premise

---

**Última atualização:** 06/02/2026
