#!/usr/bin/env python3
"""
Teste CORRETO: Nova 2 Lite vs Haiku COM TAXONOMIA FIXA.

Este teste carrega a taxonomia do arquivo arvore.yaml e passa para ambos os modelos,
simulando o comportamento REAL de produção.
"""

import json
import boto3
import time
import os
from typing import Dict, Tuple
from pathlib import Path

# Configuração
HAIKU_MODEL = "anthropic.claude-3-haiku-20240307-v1:0"
NOVA_MODEL = "us.amazon.nova-2-lite-v1:0"
TAXONOMY_PATH = "/l/disk0/lpmoraes/environments/data-science/data/arvore.yaml"

# Cliente Bedrock
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')


def load_taxonomy_from_yaml(filepath: str) -> str:
    """Carrega taxonomia do arquivo YAML (já está formatado!)."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def build_classification_prompt(title: str, content: str, taxonomy_str: str) -> str:
    """Constrói prompt COM taxonomia fixa (modo produção)."""

    prompt = f"""Você é um especialista em classificação temática de notícias governamentais brasileiras.

Analise a notícia abaixo e retorne APENAS um JSON válido (sem markdown, sem explicações).

INSTRUÇÕES:
Escolha as categorias da taxonomia abaixo que melhor se adequam à notícia.
Use EXATAMENTE os códigos e labels fornecidos.

TAXONOMIA DISPONÍVEL:
{taxonomy_str}

TAREFAS OBRIGATÓRIAS:
1. Classifique a notícia em 3 níveis hierárquicos (theme_1_level_1/2/3).
2. Gere um campo "summary" com um resumo conciso da notícia em 1-2 frases.
3. Analise o sentimento da notícia (positive, neutral ou negative) e atribua um score entre -1.0 e 1.0.

NOTÍCIA:
Título: {title}
Conteúdo: {content[:1500]}

FORMATO DE SAÍDA (JSON VÁLIDO):
{{
  "theme_1_level_1": "Política",
  "theme_1_level_1_code": "01",
  "theme_1_level_1_label": "Política",
  "theme_1_level_2_code": "01.02",
  "theme_1_level_2_label": "Legislação",
  "theme_1_level_3_code": "01.02.03",
  "theme_1_level_3_label": "Reforma Tributária",
  "most_specific_theme_code": "01.02.03",
  "most_specific_theme_label": "Reforma Tributária",
  "summary": "Resumo conciso em 1-2 frases.",
  "sentiment": {{
    "label": "positive",
    "score": 0.6
  }}
}}

Retorne APENAS o JSON, sem markdown ou explicações."""

    return prompt


def call_bedrock(model_id: str, prompt: str) -> Tuple[Dict, float, Dict]:
    """Chama Bedrock e retorna resultado + latência + tokens."""
    start = time.time()

    try:
        # Amazon Nova usa API diferente
        if 'nova' in model_id:
            body = {
                "messages": [{"role": "user", "content": [{"text": prompt}]}],
                "inferenceConfig": {
                    "max_new_tokens": 500,
                    "temperature": 0.0
                }
            }
        else:
            # Claude (Anthropic)
            body = {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 500,
                "temperature": 0.0,
                "messages": [{"role": "user", "content": prompt}]
            }

        response = bedrock.invoke_model(
            modelId=model_id,
            body=json.dumps(body)
        )

        latency = time.time() - start

        response_body = json.loads(response['body'].read())

        # Parse response (API diferente para Nova vs Claude)
        if 'nova' in model_id:
            content = response_body.get('output', {}).get('message', {}).get('content', [{}])[0].get('text', '')
            usage = response_body.get('usage', {})
        else:
            content = response_body.get('content', [{}])[0].get('text', '')
            usage = response_body.get('usage', {})

        # Extrair JSON
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0].strip()
        elif '```' in content:
            content = content.split('```')[1].split('```')[0].strip()

        result = json.loads(content)

        return result, latency, usage

    except Exception as e:
        print(f"ERRO ao chamar {model_id}: {e}")
        return None, 0, {}


def compare_results(haiku_result: Dict, nova_result: Dict) -> Dict:
    """Compara resultados focando nos CÓDIGOS (não labels)."""

    comparison = {
        "l1_code_match": (
            haiku_result.get('theme_1_level_1_code') == nova_result.get('theme_1_level_1_code')
        ),
        "l2_code_match": (
            haiku_result.get('theme_1_level_2_code') == nova_result.get('theme_1_level_2_code')
        ),
        "l3_code_match": (
            haiku_result.get('theme_1_level_3_code') == nova_result.get('theme_1_level_3_code')
        ),
        "sentiment_match": (
            haiku_result.get('sentiment', {}).get('label') ==
            nova_result.get('sentiment', {}).get('label')
        )
    }

    return comparison


# Notícias de teste
TEST_CASES = [
    {
        "id": 1,
        "title": "Ministério da Saúde anuncia nova campanha de vacinação contra COVID-19",
        "content": """O Ministério da Saúde anunciou nesta terça-feira (15) o lançamento de uma nova
        campanha nacional de vacinação contra a COVID-19. A iniciativa tem como público-alvo idosos
        acima de 60 anos e pessoas imunossuprimidas. Segundo a pasta, serão distribuídas 20 milhões
        de doses da vacina bivalente, que protege contra as variantes mais recentes do vírus.
        A campanha começa na próxima semana em todos os postos de saúde do país."""
    },
    {
        "id": 2,
        "title": "Banco Central mantém taxa Selic em 10,75% ao ano",
        "content": """O Comitê de Política Monetária (Copom) do Banco Central decidiu, por unanimidade,
        manter a taxa básica de juros (Selic) em 10,75% ao ano. A decisão era esperada pelo mercado
        e reflete a estratégia de combate à inflação. Segundo o comunicado do BC, a inflação continua
        acima da meta, mas há sinais de desaceleração. A próxima reunião do Copom está prevista
        para março."""
    },
    {
        "id": 3,
        "title": "MEC divulga cronograma do ENEM 2024",
        "content": """O Ministério da Educação (MEC) divulgou nesta quarta-feira o cronograma completo
        do Exame Nacional do Ensino Médio (ENEM) 2024. As inscrições começam em maio e as provas
        serão aplicadas em dois domingos de novembro. A taxa de inscrição será de R$ 85, mas
        estudantes de baixa renda podem solicitar isenção. Novidade este ano: haverá prova digital
        em algumas cidades como projeto piloto."""
    },
    {
        "id": 4,
        "title": "Polícia Federal deflagra operação contra esquema de corrupção em licitações",
        "content": """A Polícia Federal deflagrou na manhã desta quinta-feira a Operação Licitação Limpa,
        que investiga um esquema de fraude em licitações públicas. Segundo as investigações, o grupo
        teria desviado mais de R$ 50 milhões em contratos de obras públicas nos últimos três anos.
        Foram cumpridos 15 mandados de busca e apreensão em quatro estados. Três pessoas foram presas
        preventivamente."""
    },
    {
        "id": 5,
        "title": "Ibama aplica maior multa da história por desmatamento na Amazônia",
        "content": """O Instituto Brasileiro do Meio Ambiente e dos Recursos Naturais Renováveis (Ibama)
        aplicou a maior multa da história por desmatamento ilegal: R$ 1,2 bilhão. A empresa autuada
        é responsável pelo desmatamento de 5 mil hectares de floresta primária no Amazonas. Além da
        multa, a área será embargada e a empresa responderá criminalmente. O Ibama reforça que a
        fiscalização será intensificada."""
    }
]


def main():
    print("="*80)
    print("TESTE COM TAXONOMIA: Nova 2 Lite vs Haiku")
    print("="*80)
    print()

    # Carregar taxonomia do PostgreSQL
    print(f"Carregando taxonomia de {TAXONOMY_PATH}...")
    try:
        taxonomy_str = load_taxonomy_from_yaml(TAXONOMY_PATH)
        lines = taxonomy_str.strip().split("\n")
        l1_count = len([l for l in lines if l.startswith(tuple('0123456789')) and ' - ' in l and not l.startswith(' ')])
        print(f"Taxonomia carregada: {l1_count} categorias L1, {len(lines)} linhas totais")
        print(f"Preview (primeiras 10 linhas):")
        print("\n".join(lines[:10]))
        print()
    except Exception as e:
        print(f"ERRO ao carregar taxonomia: {e}")
        print(f"Verifique se o arquivo existe: {TAXONOMY_PATH}")
        return

    results = []

    for case in TEST_CASES:
        print(f"\n{'='*80}")
        print(f"TESTE #{case['id']}: {case['title'][:60]}...")
        print('='*80)

        prompt = build_classification_prompt(case['title'], case['content'], taxonomy_str)

        # Teste Haiku
        print(f"\n[1/2] Testando HAIKU...")
        haiku_result, haiku_latency, haiku_usage = call_bedrock(HAIKU_MODEL, prompt)

        if haiku_result:
            print(f"  ✓ Latência: {haiku_latency:.2f}s")
            print(f"  ✓ Tokens: {haiku_usage.get('input_tokens', 0)} in, {haiku_usage.get('output_tokens', 0)} out")
            print(f"  ✓ L1: {haiku_result.get('theme_1_level_1_code')} - {haiku_result.get('theme_1_level_1_label')}")
            print(f"  ✓ L2: {haiku_result.get('theme_1_level_2_code')} - {haiku_result.get('theme_1_level_2_label')}")
            print(f"  ✓ L3: {haiku_result.get('theme_1_level_3_code')} - {haiku_result.get('theme_1_level_3_label')}")
        else:
            print("  ✗ FALHOU")

        time.sleep(1)

        # Teste Nova
        print(f"\n[2/2] Testando NOVA 2 LITE...")
        nova_result, nova_latency, nova_usage = call_bedrock(NOVA_MODEL, prompt)

        if nova_result:
            print(f"  ✓ Latência: {nova_latency:.2f}s")
            print(f"  ✓ Tokens: {nova_usage.get('input_tokens', 0)} in, {nova_usage.get('output_tokens', 0)} out")
            print(f"  ✓ L1: {nova_result.get('theme_1_level_1_code')} - {nova_result.get('theme_1_level_1_label')}")
            print(f"  ✓ L2: {nova_result.get('theme_1_level_2_code')} - {nova_result.get('theme_1_level_2_label')}")
            print(f"  ✓ L3: {nova_result.get('theme_1_level_3_code')} - {nova_result.get('theme_1_level_3_label')}")
        else:
            print("  ✗ FALHOU")

        # Comparação
        if haiku_result and nova_result:
            comparison = compare_results(haiku_result, nova_result)

            print(f"\n📊 COMPARAÇÃO (códigos):")
            print(f"  L1: {'✓' if comparison['l1_code_match'] else '✗'} ({haiku_result.get('theme_1_level_1_code')} vs {nova_result.get('theme_1_level_1_code')})")
            print(f"  L2: {'✓' if comparison['l2_code_match'] else '✗'} ({haiku_result.get('theme_1_level_2_code')} vs {nova_result.get('theme_1_level_2_code')})")
            print(f"  L3: {'✓' if comparison['l3_code_match'] else '✗'} ({haiku_result.get('theme_1_level_3_code')} vs {nova_result.get('theme_1_level_3_code')})")
            print(f"  Latência: Haiku {haiku_latency:.2f}s vs Nova {nova_latency:.2f}s")

            results.append({
                'case_id': case['id'],
                'haiku': haiku_result,
                'nova': nova_result,
                'comparison': comparison,
                'latency': {'haiku': haiku_latency, 'nova': nova_latency}
            })

        time.sleep(2)

    # Sumário final
    print(f"\n\n{'='*80}")
    print("📊 SUMÁRIO FINAL (COM TAXONOMIA FIXA)")
    print('='*80)

    if results:
        l1_matches = sum(1 for r in results if r['comparison']['l1_code_match'])
        l2_matches = sum(1 for r in results if r['comparison']['l2_code_match'])
        l3_matches = sum(1 for r in results if r['comparison']['l3_code_match'])

        total = len(results)

        print(f"\nAcordo entre modelos (CÓDIGOS):")
        print(f"  L1: {l1_matches}/{total} ({l1_matches/total*100:.0f}%)")
        print(f"  L2: {l2_matches}/{total} ({l2_matches/total*100:.0f}%)")
        print(f"  L3: {l3_matches}/{total} ({l3_matches/total*100:.0f}%)")

        avg_haiku_latency = sum(r['latency']['haiku'] for r in results) / total
        avg_nova_latency = sum(r['latency']['nova'] for r in results) / total

        print(f"\nLatência média:")
        print(f"  Haiku: {avg_haiku_latency:.2f}s")
        print(f"  Nova:  {avg_nova_latency:.2f}s")
        print(f"  Ganho:  {((avg_haiku_latency - avg_nova_latency) / avg_haiku_latency * 100):.0f}% mais rápido")

        print(f"\n💡 ANÁLISE:")
        if l3_matches == total:
            print("  ✓✓✓ PERFEITO: Nova 2 Lite classificou IDENTICAMENTE ao Haiku!")
            print("      Com Issue #3 validando Haiku (80.5%), Nova também passa no teste!")
        elif l3_matches >= total * 0.8:
            print(f"  ✓ BOM: Nova teve {l3_matches/total*100:.0f}% de acordo no L3")
            print(f"    Diferenças podem ser aceitáveis (múltiplas classificações válidas)")
        else:
            print(f"  ⚠ ATENÇÃO: Nova teve apenas {l3_matches/total*100:.0f}% de acordo no L3")
            print(f"    Recomenda-se teste maior ou investigação das divergências")

    print(f"\n{'='*80}\n")

    # Salvar resultados
    with open('/tmp/nova_vs_haiku_with_taxonomy.json', 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("Resultados salvos em: /tmp/nova_vs_haiku_with_taxonomy.json")


if __name__ == "__main__":
    main()
