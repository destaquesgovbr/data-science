#!/usr/bin/env python3
"""
Teste Pragmático: Amazon Nova 2 Lite - Classificação de Notícias

Roda teste com 50-100 notícias reais e gera relatório HTML para revisão manual.

Fontes de dados (em ordem de preferência):
1. JSON de teste (Issue #2 ou #3) - se existir
2. Notícias de exemplo (sempre disponível - fallback)

Uso:
    python run_nova_classification_test.py
    python run_nova_classification_test.py --sample-size 100
    python run_nova_classification_test.py --json-file data/test_news.json
"""

import json
import boto3
import time
import argparse
from pathlib import Path
from typing import List, Dict, Optional
from collections import Counter
from datetime import datetime

# Configuração
NOVA_MODEL = "us.amazon.nova-2-lite-v1:0"
TAXONOMY_PATH = Path(__file__).parent.parent / "data" / "arvore.yaml"
OUTPUT_DIR = Path("/tmp/nova_pragmatic_test")

# Cliente Bedrock
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')


def load_taxonomy() -> str:
    """Carrega taxonomia do arquivo YAML."""
    with open(TAXONOMY_PATH, 'r', encoding='utf-8') as f:
        return f.read()


def load_news_from_json(filepath: str, sample_size: int) -> List[Dict]:
    """Carrega notícias de arquivo JSON."""
    print(f"Carregando notícias de {filepath}...")

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Adaptar para diferentes formatos de JSON
    if isinstance(data, list):
        news = data[:sample_size]
    elif isinstance(data, dict) and 'news' in data:
        news = data['news'][:sample_size]
    else:
        raise ValueError("Formato de JSON não suportado")

    print(f"✓ Carregadas {len(news)} notícias do JSON")
    return news


def load_example_news(sample_size: int) -> List[Dict]:
    """Notícias de exemplo (fallback)."""

    examples = [
        # Saúde
        {"unique_id": "ex_001", "title": "MS amplia vacinação contra COVID-19 para idosos", "content": "O Ministério da Saúde anunciou a ampliação da campanha de vacinação contra COVID-19 para incluir todos os idosos acima de 60 anos. Serão distribuídas 20 milhões de doses da vacina bivalente em todo o país.", "agency": "ms", "published_at": "2024-03-15"},
        {"unique_id": "ex_002", "title": "SUS recebe R$ 500 milhões para atenção primária", "content": "O Ministério da Saúde repassou R$ 500 milhões aos municípios para fortalecer a atenção primária no SUS. Recursos serão usados para contratação de profissionais e aquisição de equipamentos.", "agency": "ms", "published_at": "2024-03-16"},
        {"unique_id": "ex_003", "title": "Anvisa aprova novo medicamento para diabetes", "content": "A Agência Nacional de Vigilância Sanitária aprovou novo medicamento para tratamento de diabetes tipo 2. O remédio estará disponível no SUS a partir de junho.", "agency": "anvisa", "published_at": "2024-03-17"},

        # Economia
        {"unique_id": "ex_004", "title": "Banco Central reduz Selic para 9,25%", "content": "O Comitê de Política Monetária do Banco Central decidiu reduzir a taxa básica de juros em 0,5 ponto percentual. É o sexto corte consecutivo desde março.", "agency": "bcb", "published_at": "2024-03-18"},
        {"unique_id": "ex_005", "title": "Receita Federal arrecada R$ 180 bi em fevereiro", "content": "A Receita Federal arrecadou R$ 180 bilhões em fevereiro, alta de 8% em relação ao mesmo período do ano passado. Resultado é o melhor para o mês desde o início da série histórica.", "agency": "receita", "published_at": "2024-03-19"},
        {"unique_id": "ex_006", "title": "BNDES aprova R$ 3 bi para infraestrutura", "content": "O Banco Nacional de Desenvolvimento Econômico e Social aprovou financiamento de R$ 3 bilhões para obras de infraestrutura em 5 estados.", "agency": "bndes", "published_at": "2024-03-20"},

        # Educação
        {"unique_id": "ex_007", "title": "MEC lança programa de bolsas para professores", "content": "O Ministério da Educação lançou programa com 50 mil bolsas para professores da educação básica cursarem pós-graduação. Investimento total é de R$ 600 milhões.", "agency": "mec", "published_at": "2024-03-21"},
        {"unique_id": "ex_008", "title": "Enem 2024 terá prova digital em 200 cidades", "content": "O Exame Nacional do Ensino Médio terá prova digital disponível em 200 cidades como projeto piloto. Inscrições começam em maio.", "agency": "inep", "published_at": "2024-03-22"},
        {"unique_id": "ex_009", "title": "Prouni oferece 300 mil vagas no primeiro semestre", "content": "Programa Universidade para Todos oferece 300 mil bolsas de estudo integrais e parciais para o primeiro semestre. Inscrições vão até dia 31.", "agency": "mec", "published_at": "2024-03-23"},

        # Segurança
        {"unique_id": "ex_010", "title": "PF desarticula quadrilha de tráfico internacional", "content": "Polícia Federal prendeu 20 pessoas em operação contra tráfico internacional de drogas. Foram apreendidos 1 tonelada de cocaína.", "agency": "pf", "published_at": "2024-03-24"},
        {"unique_id": "ex_011", "title": "PRF intensifica fiscalização nas rodovias federais", "content": "Polícia Rodoviária Federal iniciou operação especial de fiscalização em rodovias federais. Foco é combate ao crime organizado e segurança no trânsito.", "agency": "prf", "published_at": "2024-03-25"},
        {"unique_id": "ex_012", "title": "Ministério lança programa de videomonitoramento", "content": "Ministério da Justiça lançou programa para instalação de câmeras de videomonitoramento em cidades com alta criminalidade. Investimento é de R$ 200 milhões.", "agency": "mj", "published_at": "2024-03-26"},

        # Meio Ambiente
        {"unique_id": "ex_013", "title": "Ibama aplica R$ 50 mi em multas por desmatamento", "content": "Instituto Brasileiro do Meio Ambiente aplicou R$ 50 milhões em multas por desmatamento ilegal na Amazônia em fevereiro. Foram 150 autos de infração.", "agency": "ibama", "published_at": "2024-03-27"},
        {"unique_id": "ex_014", "title": "ICMBio cria nova unidade de conservação", "content": "Instituto Chico Mendes criou nova unidade de conservação federal com 200 mil hectares no Pará. Área protege floresta amazônica e nascentes de rios.", "agency": "icmbio", "published_at": "2024-03-28"},
        {"unique_id": "ex_015", "title": "Ministério lança plano de recuperação de áreas degradadas", "content": "Ministério do Meio Ambiente lançou plano para recuperar 1 milhão de hectares de áreas degradadas até 2030. Foco é Cerrado e Mata Atlântica.", "agency": "mma", "published_at": "2024-03-29"},

        # Infraestrutura
        {"unique_id": "ex_016", "title": "Governo autoriza duplicação de 500 km de rodovias", "content": "Governo federal autorizou obras de duplicação de 500 km de rodovias federais em 3 estados. Investimento total é de R$ 4 bilhões.", "agency": "dnit", "published_at": "2024-03-30"},
        {"unique_id": "ex_017", "title": "ANTT licita concessão de 3 aeroportos", "content": "Agência Nacional de Transportes Terrestres lançou edital para concessão de 3 aeroportos regionais. Leilão está previsto para junho.", "agency": "antt", "published_at": "2024-03-31"},
        {"unique_id": "ex_018", "title": "Ministério anuncia R$ 2 bi para saneamento", "content": "Ministério das Cidades anunciou repasse de R$ 2 bilhões para obras de saneamento básico em 100 municípios. Foco é universalização do acesso à água.", "agency": "mcid", "published_at": "2024-04-01"},

        # Cultura
        {"unique_id": "ex_019", "title": "MinC lança editais com R$ 50 mi para cultura", "content": "Ministério da Cultura lançou 10 editais com investimento total de R$ 50 milhões para projetos culturais em todo o país.", "agency": "mc", "published_at": "2024-04-02"},
        {"unique_id": "ex_020", "title": "Iphan tomba conjunto arquitetônico no Nordeste", "content": "Instituto do Patrimônio Histórico e Artístico Nacional tombou conjunto arquitetônico colonial em cidade do Nordeste.", "agency": "iphan", "published_at": "2024-04-03"},

        # Trabalho
        {"unique_id": "ex_021", "title": "Ministério fiscaliza 500 empresas por trabalho escravo", "content": "Ministério do Trabalho fiscalizou 500 empresas suspeitas de trabalho análogo à escravidão. Foram resgatados 80 trabalhadores.", "agency": "mtb", "published_at": "2024-04-04"},
        {"unique_id": "ex_022", "title": "Governo cria programa de qualificação profissional", "content": "Governo federal criou programa para qualificar 100 mil trabalhadores em áreas estratégicas. Investimento é de R$ 300 milhões.", "agency": "mtb", "published_at": "2024-04-05"},

        # Desenvolvimento Social
        {"unique_id": "ex_023", "title": "Bolsa Família atende 21 milhões de famílias", "content": "Programa Bolsa Família atende 21 milhões de famílias brasileiras. Investimento mensal é de R$ 14 bilhões.", "agency": "mds", "published_at": "2024-04-06"},
        {"unique_id": "ex_024", "title": "Governo lança programa de combate à fome", "content": "Governo federal lançou programa para combate à fome com meta de retirar 10 milhões de pessoas da insegurança alimentar até 2026.", "agency": "mds", "published_at": "2024-04-07"},

        # Ciência e Tecnologia
        {"unique_id": "ex_025", "title": "CNPq anuncia bolsas de R$ 400 mi para pesquisa", "content": "Conselho Nacional de Desenvolvimento Científico e Tecnológico anunciou 10 mil bolsas de pesquisa com investimento de R$ 400 milhões.", "agency": "cnpq", "published_at": "2024-04-08"},
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
        print(f"  ✗ ERRO: {e}")
        return None


def generate_html_report(results: List[Dict], output_dir: Path):
    """Gera relatório HTML para revisão manual."""

    output_dir.mkdir(parents=True, exist_ok=True)

    # Estatísticas
    l1_dist = Counter()
    l2_dist = Counter()
    latencies = []
    success_count = 0

    for r in results:
        if r['classification']:
            success_count += 1
            l1_dist[r['classification'].get('theme_1_level_1_label', 'unknown')] += 1
            l2_dist[r['classification'].get('theme_1_level_2_label', 'unknown')] += 1
            latencies.append(r['classification'].get('_latency', 0))

    # HTML
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Nova 2 Lite - Teste Pragmático</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }}
        .header {{ background: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
        .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }}
        .stat-card {{ background: white; padding: 15px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .stat-value {{ font-size: 24px; font-weight: bold; color: #1976d2; }}
        .stat-label {{ color: #666; font-size: 14px; margin-top: 5px; }}
        .news-item {{ background: white; margin: 20px 0; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .title {{ font-size: 18px; font-weight: bold; color: #333; margin-bottom: 10px; }}
        .meta {{ color: #666; font-size: 14px; margin-bottom: 10px; }}
        .summary {{ background: #e8f5e9; padding: 10px; border-radius: 4px; margin: 10px 0; }}
        .classification {{ background: #e3f2fd; padding: 10px; border-radius: 4px; margin: 10px 0; }}
        .label {{ font-weight: bold; }}
        .sentiment {{ display: inline-block; padding: 4px 8px; border-radius: 4px; font-size: 12px; }}
        .positive {{ background: #c8e6c9; }}
        .neutral {{ background: #fff9c4; }}
        .negative {{ background: #ffcdd2; }}
        .checkbox {{ margin-right: 10px; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Amazon Nova 2 Lite - Teste Pragmático de Classificação</h1>
        <p><strong>Data:</strong> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p><strong>Modelo:</strong> {NOVA_MODEL}</p>
        <p><strong>Objetivo:</strong> Validar qualidade de classificação temática antes de aprovar para produção</p>
    </div>

    <div class="stats">
        <div class="stat-card">
            <div class="stat-value">{len(results)}</div>
            <div class="stat-label">Total de Notícias</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{success_count}</div>
            <div class="stat-label">Classificadas com Sucesso</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{sum(latencies)/len(latencies) if latencies else 0:.2f}s</div>
            <div class="stat-label">Latência Média</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{len([r for r in results if r['classification'] and r['classification'].get('theme_1_level_1_label') == 'Saúde'])}</div>
            <div class="stat-label">Saúde</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{len([r for r in results if r['classification'] and r['classification'].get('theme_1_level_1_label') == 'Economia e Finanças'])}</div>
            <div class="stat-label">Economia</div>
        </div>
        <div class="stat-card">
            <div class="stat-value">{len([r for r in results if r['classification'] and r['classification'].get('theme_1_level_1_label') == 'Educação'])}</div>
            <div class="stat-label">Educação</div>
        </div>
    </div>

    <div class="header">
        <h2>Instruções para Revisão Manual</h2>
        <ol>
            <li>Para cada notícia abaixo, avalie se a classificação L1/L2/L3 faz sentido</li>
            <li>Marque o checkbox se a classificação estiver CORRETA</li>
            <li>Ao final, conte quantos você marcou como corretos</li>
            <li><strong>Accuracy = (marcados como corretos) / (total de notícias)</strong></li>
            <li><strong>Meta: ≥ 75% para aprovar Nova para produção</strong></li>
        </ol>
    </div>

    <hr>
"""

    for idx, r in enumerate(results, 1):
        if not r['classification']:
            continue

        c = r['classification']
        sentiment_class = c.get('sentiment', {}).get('label', 'neutral')

        html += f"""
    <div class="news-item">
        <input type="checkbox" class="checkbox" id="check_{idx}">
        <label for="check_{idx}"><strong>#{idx} - Classificação está CORRETA?</strong></label>

        <div class="title">{r['title']}</div>
        <div class="meta">ID: {r['unique_id']} | Agência: {r['agency']} | Data: {r['published_at']}</div>

        <div class="classification">
            <div class="label">Classificação:</div>
            <div><strong>L1:</strong> {c.get('theme_1_level_1_code')} - {c.get('theme_1_level_1_label')}</div>
            <div><strong>L2:</strong> {c.get('theme_1_level_2_code')} - {c.get('theme_1_level_2_label')}</div>
            <div><strong>L3:</strong> {c.get('theme_1_level_3_code')} - {c.get('theme_1_level_3_label')}</div>
        </div>

        <div class="summary">
            <div class="label">Resumo (gerado):</div>
            {c.get('summary', 'N/A')}
        </div>

        <div class="meta">Sentimento: <span class="sentiment {sentiment_class}">{sentiment_class}</span> | Latência: {c.get('_latency', 0):.2f}s</div>
    </div>
"""

    html += """
    <div class="header" style="margin-top: 30px;">
        <h2>Resultado da Revisão</h2>
        <p>Conte quantos checkboxes você marcou como corretos:</p>
        <p><strong>Accuracy = (corretos) / """ + str(success_count) + """ = ?%</strong></p>
        <p>Se ≥ 75%: ✓ Nova 2 Lite APROVADO para produção</p>
        <p>Se < 75%: ⚠ Considerar split de modelos (Haiku classificação + Nova resumo)</p>
    </div>
</body>
</html>
"""

    output_file = output_dir / "review.html"
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(html)

    # Salvar JSON completo
    with open(output_dir / "results.json", 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    return output_file


def main():
    parser = argparse.ArgumentParser(description='Teste pragmático Nova 2 Lite')
    parser.add_argument('--sample-size', type=int, default=25, help='Número de notícias (default: 25)')
    parser.add_argument('--json-file', type=str, help='Arquivo JSON com notícias de teste')
    args = parser.parse_args()

    print("="*80)
    print("TESTE PRAGMÁTICO: Amazon Nova 2 Lite para Classificação")
    print("="*80)
    print()

    # Carregar taxonomia
    print(f"Carregando taxonomia de {TAXONOMY_PATH}...")
    taxonomy = load_taxonomy()
    print(f"✓ Taxonomia carregada")
    print()

    # Carregar notícias
    if args.json_file and Path(args.json_file).exists():
        news_sample = load_news_from_json(args.json_file, args.sample_size)
    else:
        print(f"Usando {args.sample_size} notícias de exemplo...")
        news_sample = load_example_news(args.sample_size)

    print(f"Total: {len(news_sample)} notícias")
    print()

    # Classificar
    results = []

    for idx, news in enumerate(news_sample, 1):
        print(f"[{idx}/{len(news_sample)}] {news['title'][:60]}...")

        classification = classify_with_nova(
            news['title'],
            news['content'],
            taxonomy
        )

        if classification:
            print(f"  ✓ {classification.get('theme_1_level_1_label')} ({classification.get('_latency', 0):.2f}s)")

        results.append({
            'unique_id': news['unique_id'],
            'title': news['title'],
            'content': news.get('content', '')[:500],
            'agency': news.get('agency', 'unknown'),
            'published_at': news.get('published_at', ''),
            'classification': classification
        })

        time.sleep(1)  # Rate limiting

    # Gerar relatório
    print()
    print("="*80)
    print("Gerando relatório HTML...")
    output_file = generate_html_report(results, OUTPUT_DIR)

    print()
    print("="*80)
    print("✓ CONCLUÍDO!")
    print("="*80)
    print()
    print(f"Abra o arquivo para revisar: {output_file}")
    print()
    print("PRÓXIMOS PASSOS:")
    print("1. Abrir o HTML e revisar cada classificação")
    print("2. Marcar checkbox se a classificação estiver correta")
    print("3. Calcular accuracy = (corretos) / (total)")
    print("4. Se ≥ 75%: APROVAR Nova para produção")
    print("5. Se < 75%: Considerar split de modelos")
    print()


if __name__ == "__main__":
    main()
