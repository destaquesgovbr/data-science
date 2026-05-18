#!/usr/bin/env python3
"""
Gera referências para TODO o dataset (200 notícias)
Reutiliza as 50 existentes e gera mais 150
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
    print(f"GERAÇÃO DE REFERÊNCIAS - DATASET COMPLETO (200 notícias)")
    print("=" * 80)

    # Carregar dataset
    script_dir = Path(__file__).parent
    data_file = script_dir.parent / "data" / "news_sample.csv"
    existing_refs_file = script_dir.parent / "data" / "reference_summaries_sample.csv"

    print(f"\n1. Carregando datasets...")
    df_news = pd.read_csv(data_file)
    print(f"   Total de notícias: {len(df_news)}")

    # Carregar referências existentes
    try:
        df_existing = pd.read_csv(existing_refs_file)
        existing_ids = set(df_existing['id'].tolist())
        print(f"   Referências existentes: {len(existing_ids)}")
    except FileNotFoundError:
        df_existing = pd.DataFrame()
        existing_ids = set()
        print(f"   Nenhuma referência existente encontrada")

    # Identificar notícias sem referência
    df_missing = df_news[~df_news['id'].isin(existing_ids)]
    print(f"   Notícias sem referência: {len(df_missing)}")

    if len(df_missing) == 0:
        print("\n✅ Todas as notícias já possuem referências!")
        return

    # Gerar referências faltantes
    print(f"\n2. Gerando {len(df_missing)} novas referências com Claude 3 Haiku...")
    print(f"   Custo estimado: ~${len(df_missing) * 0.0006:.3f}")

    results = []
    errors = 0

    for idx, row in tqdm(df_missing.iterrows(), total=len(df_missing), desc="Processando"):
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
            errors += 1
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
            print(f"\n   ⚠️  Erro na notícia {row['id']}: {str(e)[:100]}")

    # Combinar com existentes
    print(f"\n3. Combinando com referências existentes...")
    new_refs_df = pd.DataFrame(results)

    if len(df_existing) > 0:
        all_refs_df = pd.concat([df_existing, new_refs_df], ignore_index=True)
    else:
        all_refs_df = new_refs_df

    # Salvar
    output_file = script_dir.parent / "data" / "reference_summaries_full.csv"
    all_refs_df.to_csv(output_file, index=False)

    # Estatísticas
    print(f"\n4. Estatísticas finais:")
    successful = all_refs_df[all_refs_df['success'] == True]
    print(f"   Total de referências: {len(all_refs_df)}")
    print(f"   Sucesso: {len(successful)}/{len(all_refs_df)}")
    print(f"   Novas geradas: {len(results)}")
    print(f"   Erros: {errors}")

    if len(successful) > 0:
        print(f"\n   Tamanho médio: {successful['reference_length'].mean():.0f} chars")

        # Latência apenas das novas
        if len(new_refs_df[new_refs_df['success'] == True]) > 0:
            print(f"   Latência média (novas): {new_refs_df[new_refs_df['success'] == True]['latency'].mean():.2f}s")
            print(f"   Tempo total: {new_refs_df[new_refs_df['success'] == True]['latency'].sum()/60:.1f} min")

    print(f"\n✅ Arquivo salvo: {output_file}")
    print("=" * 80)

if __name__ == "__main__":
    main()
