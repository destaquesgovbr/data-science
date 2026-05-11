#!/usr/bin/env python3
"""
Gera referências para uma amostra (50 notícias) para teste rápido
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pandas as pd
import boto3
import json
import time
from tqdm import tqdm

BEDROCK_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
BEDROCK_REGION = "us-east-1"
SAMPLE_SIZE = 50

def call_claude(text: str) -> str:
    bedrock = boto3.client('bedrock-runtime', region_name=BEDROCK_REGION)

    prompt = f"""Resuma esta notícia governamental brasileira em 2-3 frases concisas (100-150 palavras).

Notícia:
{text}

Resumo:"""

    response = bedrock.invoke_model(
        modelId=BEDROCK_MODEL_ID,
        body=json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 300,
            "temperature": 0.3,
            "messages": [{"role": "user", "content": prompt}]
        })
    )

    response_body = json.loads(response['body'].read())
    return response_body['content'][0]['text'].strip()

def main():
    print("=" * 80)
    print(f"GERAÇÃO DE REFERÊNCIAS - AMOSTRA ({SAMPLE_SIZE} notícias)")
    print("=" * 80)

    # Carregar dataset
    script_dir = Path(__file__).parent
    data_file = script_dir.parent / "data" / "news_sample.csv"

    print(f"\n1. Carregando dataset...")
    df = pd.read_csv(data_file)

    # Sample aleatória
    df_sample = df.sample(n=SAMPLE_SIZE, random_state=42)
    print(f"   Selecionadas {len(df_sample)} notícias")

    # Gerar referências
    print(f"\n2. Gerando referências com Claude 3 Haiku...")
    results = []

    for idx, row in tqdm(df_sample.iterrows(), total=len(df_sample), desc="Processando"):
        try:
            start_time = time.time()
            summary = call_claude(row['content'])
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

            time.sleep(0.3)  # Rate limiting

        except Exception as e:
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

    # Salvar
    print(f"\n3. Salvando...")
    results_df = pd.DataFrame(results)
    output_file = script_dir.parent / "data" / "reference_summaries_sample.csv"
    results_df.to_csv(output_file, index=False)

    # Estatísticas
    successful = results_df[results_df['success'] == True]
    print(f"\n4. Resultados:")
    print(f"   Sucesso: {len(successful)}/{len(results_df)}")

    if len(successful) > 0:
        print(f"   Tamanho médio: {successful['reference_length'].mean():.0f} chars")
        print(f"   Latência média: {successful['latency'].mean():.2f}s")
        print(f"   Tempo total: {successful['latency'].sum()/60:.1f} min")

    print(f"\n✅ Arquivo salvo: {output_file}")
    print("=" * 80)

if __name__ == "__main__":
    main()
