#!/usr/bin/env python3
"""
Teste de Qualidade: Nova 2 Lite em Sample de Notícias Reais

Classifica 50-100 notícias reais com Nova 2 Lite e gera relatório
para análise manual da qualidade das classificações.

Objetivo: validar se Nova pode ser usado para classificação em produção,
documentando evidências para Issue no data-science.
"""

import json
import boto3
import time
import random
from typing import Dict, List, Optional
from pathlib import Path
from collections import Counter
from datetime import datetime

# Configuração
NOVA_MODEL = "us.amazon.nova-2-lite-v1:0"
TAXONOMY_PATH = "/l/disk0/lpmoraes/environments/data-science/data/arvore.yaml"
SAMPLE_SIZE = 50  # Pode ajustar para 100
OUTPUT_DIR = "/tmp/nova_quality_test"

# Cliente Bedrock
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')


def load_taxonomy() -> str:
    """Carrega taxonomia do arquivo YAML."""
    with open(TAXONOMY_PATH, 'r', encoding='utf-8') as f:
        return f.read()


def load_news_sample(sample_size: int) -> List[Dict]:
    """
    Carrega sample de notícias do dataset HuggingFace local.

    Fallback: se não houver dataset local, cria notícias de exemplo.
    """
    # Tentar carregar do HuggingFace dataset
    try:
        from datasets import load_dataset
        print("Carregando dataset HuggingFace govbrnews...")
        dataset = load_dataset("destaquesgovbr/govbrnews", split="train")

        # Sample aleatório
        total = len(dataset)
        indices = random.sample(range(total), min(sample_size, total))

        news = []
        for idx in indices:
            item = dataset[int(idx)]
            news.append({
                'unique_id': item.get('unique_id', f'sample_{idx}'),
                'title': item.get('title', ''),
                'content': item.get('content', '')[:2000],  # Limita tamanho
                'agency': item.get('agency_name', 'unknown'),
                'published_at': item.get('published_at', '')
            })

        print(f"✓ Carregadas {len(news)} notícias do dataset")
        return news

    except Exception as e:
        print(f"Não foi possível carregar dataset HuggingFace: {e}")
        print("Usando notícias de exemplo...")

        # Notícias de exemplo (diversas áreas)
        examples = [
            {
                'unique_id': 'ex_001',
                'title': 'Ministério da Saúde amplia vacinação contra gripe',
                'content': 'O Ministério da Saúde anunciou a ampliação da campanha de vacinação contra a gripe para incluir gestantes e idosos acima de 60 anos. A medida visa proteger grupos vulneráveis durante o período de outono e inverno.',
                'agency': 'ms',
                'published_at': '2024-03-15'
            },
            {
                'unique_id': 'ex_002',
                'title': 'Banco Central reduz taxa Selic para 9,5%',
                'content': 'O Comitê de Política Monetária do Banco Central decidiu reduzir a taxa básica de juros em 0,25 ponto percentual. A decisão reflete a trajetória de desaceleração da inflação observada nos últimos meses.',
                'agency': 'bcb',
                'published_at': '2024-03-16'
            },
            {
                'unique_id': 'ex_003',
                'title': 'MEC lança programa de bolsas para educação básica',
                'content': 'O Ministério da Educação lançou novo programa de bolsas destinado a professores da educação básica que desejam realizar pós-graduação. O investimento total será de R$ 500 milhões.',
                'agency': 'mec',
                'published_at': '2024-03-17'
            },
            {
                'unique_id': 'ex_004',
                'title': 'Polícia Federal desarticula quadrilha de tráfico internacional',
                'content': 'A Polícia Federal deflagrou operação que resultou na prisão de 15 pessoas envolvidas com tráfico internacional de drogas. Foram apreendidos 500kg de cocaína em aeroporto.',
                'agency': 'pf',
                'published_at': '2024-03-18'
            },
            {
                'unique_id': 'ex_005',
                'title': 'Ibama autua empresa por desmatamento ilegal',
                'content': 'O Ibama aplicou multa de R$ 10 milhões a empresa flagrada desmatando área de preservação permanente na Amazônia. A área atingida foi de 200 hectares de floresta nativa.',
                'agency': 'ibama',
                'published_at': '2024-03-19'
            },
            {
                'unique_id': 'ex_006',
                'title': 'BNDES aprova financiamento para infraestrutura rodoviária',
                'content': 'O Banco Nacional de Desenvolvimento Econômico e Social aprovou financiamento de R$ 2 bilhões para obras de duplicação de rodovias federais. As obras devem gerar 5 mil empregos diretos.',
                'agency': 'bndes',
                'published_at': '2024-03-20'
            },
            {
                'unique_id': 'ex_007',
                'title': 'Ministério da Cultura anuncia editais para artistas',
                'content': 'O Ministério da Cultura divulgou três novos editais com investimento total de R$ 30 milhões destinados a projetos culturais nas áreas de música, teatro e cinema.',
                'agency': 'mc',
                'published_at': '2024-03-21'
            },
            {
                'unique_id': 'ex_008',
                'title': 'Ministério do Trabalho fiscaliza condições em frigoríficos',
                'content': 'Operação do Ministério do Trabalho fiscalizou 50 frigoríficos em 10 estados. Foram encontradas irregularidades em condições de trabalho em 30% dos estabelecimentos.',
                'agency': 'mtb',
                'published_at': '2024-03-22'
            }
        ]

        return examples[:sample_size]


def classify_with_nova(title: str, content: str, taxonomy: str) -> Optional[Dict]:
    """Classifica notícia com Nova 2 Lite."""

    prompt = f"""Você é um especialista em classificação temática de notícias governamentais brasileiras.

Analise a notícia abaixo e retorne APENAS um JSON válido (sem markdown, sem explicações).

INSTRUÇÕES:
Escolha as categorias da taxonomia abaixo que melhor se adequam à notícia.
Use EXATAMENTE os códigos e labels fornecidos.

TAXONOMIA DISPONÍVEL:
{taxonomy}

TAREFAS OBRIGATÓRIAS:
1. Classifique a notícia em 3 níveis hierárquicos (theme_1_level_1/2/3).
2. Gere um campo "summary" com um resumo conciso da notícia em 1-2 frases.
3. Analise o sentimento da notícia (positive, neutral ou negative) e atribua um score entre -1.0 e 1.0.

NOTÍCIA:
Título: {title}
Conteúdo: {content}

FORMATO DE SAÍDA (JSON VÁLIDO):
{{
  "theme_1_level_1_code": "01",
  "theme_1_level_1_label": "Economia e Finanças",
  "theme_1_level_2_code": "01.01",
  "theme_1_level_2_label": "Política Econômica",
  "theme_1_level_3_code": "01.01.01",
  "theme_1_level_3_label": "Política Fiscal",
  "summary": "Resumo conciso em 1-2 frases.",
  "sentiment": {{
    "label": "positive",
    "score": 0.6
  }}
}}

Retorne APENAS o JSON, sem markdown ou explicações."""

    try:
        start = time.time()

        response = bedrock.invoke_model(
            modelId=NOVA_MODEL,
            body=json.dumps({
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {
                    "max_new_tokens": 500,
                    "temperature": 0.0
                }
            })
        )

        latency = time.time() - start

        response_body = json.loads(response['body'].read())
        content_text = response_body.get('output', {}).get('message', {}).get('content', [{}])[0].get('text', '')

        # Extrair JSON
        if '```json' in content_text:
            content_text = content_text.split('```json')[1].split('```')[0].strip()
        elif '```' in content_text:
            content_text = content_text.split('```')[1].split('```')[0].strip()

        result = json.loads(content_text)
        result['_latency'] = latency

        return result

    except Exception as e:
        print(f"ERRO ao classificar: {e}")
        return None


def generate_report(results: List[Dict], output_dir: str):
    """Gera relatório detalhado dos resultados."""

    Path(output_dir).mkdir(parents=True, exist_ok=True)

    # Salvar resultados completos
    with open(f"{output_dir}/results_full.json", 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    # Estatísticas
    l1_dist = Counter()
    l2_dist = Counter()
    l3_dist = Counter()
    sentiments = Counter()
    latencies = []

    for r in results:
        if r['classification']:
            l1_dist[r['classification'].get('theme_1_level_1_label', 'unknown')] += 1
            l2_dist[r['classification'].get('theme_1_level_2_label', 'unknown')] += 1
            l3_dist[r['classification'].get('theme_1_level_3_label', 'unknown')] += 1
            sentiments[r['classification'].get('sentiment', {}).get('label', 'unknown')] += 1
            latencies.append(r['classification'].get('_latency', 0))

    # Relatório em texto
    report = f"""
================================================================================
RELATÓRIO DE QUALIDADE: Amazon Nova 2 Lite - Classificação Temática
================================================================================

Data/Hora: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Modelo: {NOVA_MODEL}
Taxonomia: arvore.yaml (25 categorias L1, 743 linhas)

AMOSTRA:
  Total de notícias: {len(results)}
  Classificadas com sucesso: {len([r for r in results if r['classification']])}
  Falhas: {len([r for r in results if not r['classification']])}

PERFORMANCE:
  Latência média: {sum(latencies)/len(latencies):.2f}s
  Latência mínima: {min(latencies):.2f}s
  Latência máxima: {max(latencies):.2f}s
  Latência p50: {sorted(latencies)[len(latencies)//2]:.2f}s
  Latência p95: {sorted(latencies)[int(len(latencies)*0.95)]:.2f}s

DISTRIBUIÇÃO L1 (Top 10):
"""

    for label, count in l1_dist.most_common(10):
        pct = (count / len(results)) * 100
        report += f"  {label:40s} {count:3d} ({pct:5.1f}%)\n"

    report += "\nDISTRIBUIÇÃO L2 (Top 15):\n"
    for label, count in l2_dist.most_common(15):
        pct = (count / len(results)) * 100
        report += f"  {label:50s} {count:3d} ({pct:5.1f}%)\n"

    report += "\nSENTIMENTO:\n"
    for label, count in sentiments.most_common():
        pct = (count / len(results)) * 100
        report += f"  {label:10s} {count:3d} ({pct:5.1f}%)\n"

    report += """
================================================================================
ANÁLISE MANUAL
================================================================================

Para revisar a qualidade das classificações:

1. Abra o arquivo: results_review.html
   - Visualização interativa das classificações
   - Mostra título, resumo, classificação L1/L2/L3 para cada notícia

2. Verifique se as classificações fazem sentido:
   - L1 (tema macro) está correto?
   - L2/L3 (subtemas) são apropriados?
   - Resumo captura a essência da notícia?

3. Anote divergências/problemas no arquivo: notes.txt

================================================================================
PRÓXIMOS PASSOS
================================================================================

1. Revisar sample manualmente (5-10 minutos)
2. Calcular accuracy aproximada (% de classificações corretas)
3. Criar Issue no data-science documentando:
   - Metodologia deste teste
   - Resultados (accuracy, latência)
   - Comparação com Issue #3 (Haiku 80.5%)
   - Recomendação: usar Nova para classificação + resumo?

================================================================================
"""

    with open(f"{output_dir}/report.txt", 'w', encoding='utf-8') as f:
        f.write(report)

    # HTML para revisão manual
    html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Nova 2 Lite - Revisão de Qualidade</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .news-item { background: white; margin: 20px 0; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .title { font-size: 18px; font-weight: bold; color: #333; margin-bottom: 10px; }
        .meta { color: #666; font-size: 14px; margin-bottom: 10px; }
        .summary { background: #e8f5e9; padding: 10px; border-radius: 4px; margin: 10px 0; }
        .classification { background: #e3f2fd; padding: 10px; border-radius: 4px; margin: 10px 0; }
        .label { font-weight: bold; }
        .sentiment { display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; }
        .positive { background: #c8e6c9; }
        .neutral { background: #fff9c4; }
        .negative { background: #ffcdd2; }
    </style>
</head>
<body>
    <h1>Amazon Nova 2 Lite - Revisão de Qualidade</h1>
    <p>Total de notícias: """ + str(len(results)) + """</p>
    <p>Instruções: Para cada notícia abaixo, avalie se a classificação faz sentido.</p>
    <hr>
"""

    for idx, r in enumerate(results, 1):
        if not r['classification']:
            continue

        c = r['classification']
        sentiment_class = c.get('sentiment', {}).get('label', 'neutral')

        html += f"""
    <div class="news-item">
        <div class="title">{idx}. {r['title']}</div>
        <div class="meta">ID: {r['unique_id']} | Agência: {r['agency']} | Data: {r['published_at']}</div>

        <div class="summary">
            <div class="label">Resumo (gerado):</div>
            {c.get('summary', 'N/A')}
        </div>

        <div class="classification">
            <div class="label">Classificação:</div>
            <div><strong>L1:</strong> {c.get('theme_1_level_1_code')} - {c.get('theme_1_level_1_label')}</div>
            <div><strong>L2:</strong> {c.get('theme_1_level_2_code')} - {c.get('theme_1_level_2_label')}</div>
            <div><strong>L3:</strong> {c.get('theme_1_level_3_code')} - {c.get('theme_1_level_3_label')}</div>
            <div><strong>Sentimento:</strong> <span class="sentiment {sentiment_class}">{sentiment_class}</span></div>
        </div>

        <div class="meta">Latência: {c.get('_latency', 0):.2f}s</div>
    </div>
"""

    html += """
</body>
</html>
"""

    with open(f"{output_dir}/results_review.html", 'w', encoding='utf-8') as f:
        f.write(html)

    # Arquivo para notas
    with open(f"{output_dir}/notes.txt", 'w', encoding='utf-8') as f:
        f.write("# NOTAS DE REVISÃO MANUAL\n\n")
        f.write("Use este arquivo para anotar problemas encontrados:\n\n")
        f.write("Exemplo:\n")
        f.write("- Notícia #5: classificou como Economia mas era Educação\n")
        f.write("- Notícia #12: resumo não capturou o ponto principal\n\n")
        f.write("=" * 80 + "\n\n")

    print(f"\n✓ Relatórios gerados em: {output_dir}/")
    print(f"  - report.txt (estatísticas)")
    print(f"  - results_review.html (revisão visual)")
    print(f"  - results_full.json (dados completos)")
    print(f"  - notes.txt (suas anotações)")


def main():
    print("="*80)
    print("TESTE DE QUALIDADE: Amazon Nova 2 Lite")
    print("="*80)
    print()

    # Carregar taxonomia
    print(f"Carregando taxonomia de {TAXONOMY_PATH}...")
    taxonomy = load_taxonomy()
    print(f"✓ Taxonomia carregada ({len(taxonomy.split(chr(10)))} linhas)")
    print()

    # Carregar sample de notícias
    print(f"Carregando sample de {SAMPLE_SIZE} notícias...")
    news_sample = load_news_sample(SAMPLE_SIZE)
    print()

    # Classificar cada notícia
    results = []

    for idx, news in enumerate(news_sample, 1):
        print(f"[{idx}/{len(news_sample)}] Classificando: {news['title'][:60]}...")

        classification = classify_with_nova(
            news['title'],
            news['content'],
            taxonomy
        )

        if classification:
            print(f"  ✓ L1: {classification.get('theme_1_level_1_label')}")
            print(f"  ✓ Latência: {classification.get('_latency', 0):.2f}s")
        else:
            print(f"  ✗ FALHOU")

        results.append({
            'unique_id': news['unique_id'],
            'title': news['title'],
            'content': news['content'][:500],  # Só preview
            'agency': news['agency'],
            'published_at': news['published_at'],
            'classification': classification
        })

        # Rate limiting
        time.sleep(1)

    print()
    print("="*80)
    print("Gerando relatórios...")
    generate_report(results, OUTPUT_DIR)

    print()
    print("="*80)
    print("CONCLUÍDO!")
    print("="*80)
    print()
    print(f"Abra o arquivo para revisar: {OUTPUT_DIR}/results_review.html")
    print(f"Leia o relatório: {OUTPUT_DIR}/report.txt")
    print()


if __name__ == "__main__":
    main()
