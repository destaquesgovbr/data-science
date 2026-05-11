#!/usr/bin/env python3
"""
Gera referências (ground truth) para as 200 notícias usando Claude Haiku

As referências serão usadas para calcular ROUGE e avaliar todas as técnicas
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import boto3
import json
import time
from tqdm import tqdm

# Configuração
# Usar Haiku 4.5 (ACTIVE)
BEDROCK_MODEL_ID = "anthropic.claude-haiku-4-5-20251001-v1:0"
BEDROCK_REGION = "us-east-1"

def call_bedrock_claude(text: str, max_retries: int = 3) -> str:
    """
    Chama Claude Haiku via Bedrock para gerar resumo

    Args:
        text: Texto completo da notícia
        max_retries: Número máximo de tentativas

    Returns:
        Resumo gerado
    """
    bedrock = boto3.client('bedrock-runtime', region_name=BEDROCK_REGION)

    prompt = f"""Você é um especialista em sumarização de notícias governamentais brasileiras.

Sua tarefa é criar um resumo conciso e informativo da notícia abaixo.

**Diretrizes:**
- O resumo deve ter 2-3 frases (aproximadamente 100-150 palavras)
- Inclua apenas os fatos mais importantes e relevantes
- Mantenha a fidelidade ao texto original (sem inventar informações)
- Use linguagem clara e objetiva
- Preserve números, datas e nomes importantes

**Notícia:**
{text}

**Resumo:**"""

    request_body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 300,
        "temperature": 0.3,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }

    for attempt in range(max_retries):
        try:
            response = bedrock.invoke_model(
                modelId=BEDROCK_MODEL_ID,
                body=json.dumps(request_body)
            )

            response_body = json.loads(response['body'].read())
            summary = response_body['content'][0]['text'].strip()

            return summary

        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
                continue
            else:
                raise e

def main():
    print("=" * 80)
    print("GERAÇÃO DE REFERÊNCIAS (GROUND TRUTH) COM CLAUDE HAIKU")
    print("=" * 80)

    # Carregar dataset
    script_dir = Path(__file__).parent
    data_file = script_dir.parent / "data" / "news_sample.csv"

    print(f"\n1. Carregando dataset: {data_file}")
    df = pd.read_csv(data_file)
    print(f"   Total: {len(df)} notícias")

    # Verificar se já existem referências
    output_file = script_dir.parent / "data" / "reference_summaries.csv"
    if output_file.exists():
        print(f"\n⚠️  Arquivo de referências já existe: {output_file}")
        print("   Continuando mesmo assim...")

    # Gerar referências
    print(f"\n2. Gerando referências com Claude Haiku...")
    print(f"   Modelo: {BEDROCK_MODEL_ID}")
    print(f"   Região: {BEDROCK_REGION}")
    print()

    results = []
    failed = []

    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Processando"):
        try:
            # Gerar resumo
            start_time = time.time()
            summary = call_bedrock_claude(row['content'])
            latency = time.time() - start_time

            results.append({
                'id': row['id'],
                'title': row['title'],
                'category': row['level_1_label'],
                'original_length': row['length'],
                'reference_summary': summary,
                'reference_length': len(summary),
                'latency': latency,
                'success': True,
                'error': None
            })

        except Exception as e:
            failed.append((idx, row['id'], str(e)))
            results.append({
                'id': row['id'],
                'title': row['title'],
                'category': row['level_1_label'],
                'original_length': row['length'],
                'reference_summary': '',
                'reference_length': 0,
                'latency': 0,
                'success': False,
                'error': str(e)
            })

        # Rate limiting (evitar throttling)
        time.sleep(0.5)

    # Salvar resultados
    print(f"\n3. Salvando referências...")
    results_df = pd.DataFrame(results)
    results_df.to_csv(output_file, index=False)
    print(f"   Arquivo: {output_file}")

    # Estatísticas
    print("\n4. Estatísticas:")
    successful = results_df[results_df['success'] == True]
    print(f"   Total processado: {len(results_df)}")
    print(f"   Sucesso: {len(successful)} ({len(successful)/len(results_df)*100:.1f}%)")
    print(f"   Falhas: {len(failed)}")

    if len(successful) > 0:
        print(f"\n   Referências geradas:")
        print(f"   - Tamanho médio: {successful['reference_length'].mean():.0f} caracteres")
        print(f"   - Tamanho mediano: {successful['reference_length'].median():.0f} caracteres")
        print(f"   - Min-Max: {successful['reference_length'].min()}-{successful['reference_length'].max()}")
        print(f"   - Latência média: {successful['latency'].mean():.2f}s")
        print(f"   - Taxa de compressão média: {(successful['reference_length']/successful['original_length']).mean():.1%}")

    if failed:
        print(f"\n⚠️  Notícias com falha:")
        for idx, news_id, error in failed[:5]:
            print(f"   - [{idx}] {news_id}: {error[:100]}")
        if len(failed) > 5:
            print(f"   ... e mais {len(failed)-5}")

    # Estimativa de custo
    total_tokens_in = successful['original_length'].sum() / 4  # ~4 chars per token
    total_tokens_out = successful['reference_length'].sum() / 4

    # Claude Haiku pricing: $0.25/MTok input, $1.25/MTok output
    cost_input = (total_tokens_in / 1_000_000) * 0.25
    cost_output = (total_tokens_out / 1_000_000) * 1.25
    total_cost = cost_input + cost_output

    print(f"\n5. Estimativa de custo:")
    print(f"   Tokens input: ~{total_tokens_in:,.0f}")
    print(f"   Tokens output: ~{total_tokens_out:,.0f}")
    print(f"   Custo total: ~${total_cost:.4f}")

    print("\n" + "=" * 80)
    print("✅ REFERÊNCIAS GERADAS COM SUCESSO!")
    print("=" * 80)
    print(f"\nPróximo passo: Avaliar TextRank e LexRank com ROUGE usando estas referências")

if __name__ == "__main__":
    main()
