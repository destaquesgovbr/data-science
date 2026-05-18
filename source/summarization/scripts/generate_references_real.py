#!/usr/bin/env python3
"""
Gera referências para notícias REAIS do gov.br
Usa Claude 3 Haiku (mesmo método das sintéticas)
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
    print(f"GERAÇÃO DE REFERÊNCIAS - NOTÍCIAS REAIS DO GOV.BR")
    print("=" * 80)

    # Carregar amostra de notícias reais
    script_dir = Path(__file__).parent
    news_file = script_dir.parent / "data" / "news_real_sample.csv"

    if not news_file.exists():
        print(f"\n❌ ERRO: Arquivo {news_file} não encontrado!")
        print(f"   Execute primeiro: python scripts/prepare_real_news.py")
        return

    print(f"\n1. Carregando notícias reais...")
    df_news = pd.read_csv(news_file)
    print(f"   Total de notícias: {len(df_news)}")
    print(f"   Categorias: {df_news['category'].nunique()}")
    print(f"   Tamanho médio: {df_news['length'].mean():.0f} chars")

    # Gerar referências
    print(f"\n2. Gerando {len(df_news)} referências com Claude 3 Haiku...")
    print(f"   Custo estimado: ~${len(df_news) * 0.0006:.3f}")

    results = []
    errors = 0
    start_time = time.time()

    for idx, row in tqdm(df_news.iterrows(), total=len(df_news), desc="Processando"):
        try:
            call_start = time.time()
            summary = call_claude(row['content'])
            latency = time.time() - call_start

            results.append({
                'id': row['id'],
                'title': row['title'],
                'category': row['category'],
                'subcategory': row['subcategory'],
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
                'category': row['category'],
                'subcategory': row['subcategory'],
                'original_length': row['length'],
                'reference_summary': '',
                'reference_length': 0,
                'latency': 0,
                'success': False,
                'error': str(e)
            })
            print(f"\n   ⚠️  Erro na notícia {row['id']}: {str(e)[:100]}")

    total_time = time.time() - start_time

    # Salvar
    df_results = pd.DataFrame(results)
    output_file = script_dir.parent / "data" / "reference_summaries_real.csv"
    df_results.to_csv(output_file, index=False)

    # Estatísticas
    print(f"\n3. Estatísticas finais:")
    successful = df_results[df_results['success'] == True]
    print(f"   Total de referências: {len(df_results)}")
    print(f"   Sucesso: {len(successful)}/{len(df_results)} ({len(successful)/len(df_results)*100:.1f}%)")
    print(f"   Erros: {errors}")
    print(f"   Tempo total: {total_time/60:.1f} min")

    if len(successful) > 0:
        print(f"\n   Tamanho médio dos resumos: {successful['reference_length'].mean():.0f} chars")
        print(f"   Latência média: {successful['latency'].mean():.2f}s")
        print(f"   Taxa de compressão média: {(successful['original_length'] / successful['reference_length']).mean():.1f}x")

        print(f"\n   Distribuição por categoria (top 10):")
        cat_stats = successful.groupby('category').agg({
            'reference_length': 'mean',
            'id': 'count'
        }).rename(columns={'id': 'count'}).sort_values('count', descending=True)

        for cat, row in cat_stats.head(10).iterrows():
            print(f"      {cat[:35]:<35} n={int(row['count']):>3}  len={row['reference_length']:.0f}")

    print(f"\n✅ Arquivo salvo: {output_file}")
    print("=" * 80)
    print(f"\nPróximo passo:")
    print(f"   python scripts/test_real_dataset.py")

if __name__ == "__main__":
    main()
