#!/usr/bin/env python3
"""
Script de teste rápido: Nova 2 Lite vs Haiku para classificação.

Testa ambos os modelos com notícias reais e compara os resultados.
"""

import json
import boto3
import time
from typing import Dict, Tuple

# Configuração
HAIKU_MODEL = "anthropic.claude-3-haiku-20240307-v1:0"
NOVA_MODEL = "us.amazon.nova-2-lite-v1:0"  # Inference profile (mesmo usado em produção)

# Cliente Bedrock
bedrock = boto3.client('bedrock-runtime', region_name='us-east-1')


def build_classification_prompt(title: str, content: str) -> str:
    """Constrói prompt de classificação (mesmo usado em produção)."""

    prompt = f"""Você é um especialista em classificação temática de notícias governamentais brasileiras.

Analise a notícia abaixo e retorne APENAS um JSON válido (sem markdown, sem explicações).

INSTRUÇÕES:
1. Crie uma árvore temática hierárquica com 3 níveis:
   - Nível 1: Tema macro (ex: Política, Economia, Saúde, Educação, Infraestrutura)
   - Nível 2: Subtema (ex: Política -> Legislação, Economia -> Mercado Financeiro)
   - Nível 3: Tema específico (ex: Legislação -> Reforma Tributária)

2. Gere códigos numéricos hierárquicos:
   - Nível 1: "01", "02", "03", etc.
   - Nível 2: "01.01", "01.02", etc.
   - Nível 3: "01.01.01", "01.01.02", etc.

3. Crie um resumo conciso (máximo 2 frases) capturando os pontos principais.

4. Use categorias consistentes para facilitar agregação posterior.

TAREFAS OBRIGATÓRIAS:
1. Classifique a notícia em 3 níveis hierárquicos (theme_1_level_1/2/3).
2. Gere um campo "summary" com um resumo conciso da notícia em 1-2 frases. O summary é OBRIGATÓRIO.
3. Analise o sentimento da notícia (positive, neutral ou negative) e atribua um score entre -1.0 e 1.0.

NOTÍCIA:
Título: {title}
Conteúdo: {content[:1500]}

FORMATO DE SAÍDA (JSON VÁLIDO — todos os campos são obrigatórios):
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
  "summary": "Governo federal anuncia proposta de reforma tributária. Medida visa simplificar sistema e reduzir carga sobre empresas.",
  "sentiment": {{
    "label": "positive",
    "score": 0.6
  }}
}}

Retorne APENAS o JSON, sem markdown ou explicações."""

    return prompt


def call_bedrock(model_id: str, prompt: str) -> Tuple[Dict, float, Dict]:
    """
    Chama Bedrock e retorna resultado + latência + tokens.

    Returns:
        (parsed_json, latency_seconds, usage)
    """
    start = time.time()

    try:
        # Amazon Nova usa API diferente (não-Anthropic)
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
            # Amazon Nova format
            content = response_body.get('output', {}).get('message', {}).get('content', [{}])[0].get('text', '')
            usage = response_body.get('usage', {})
        else:
            # Claude (Anthropic) format
            content = response_body.get('content', [{}])[0].get('text', '')
            usage = response_body.get('usage', {})

        # Extrair JSON (pode vir com markdown)
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
    """Compara resultados dos dois modelos."""

    comparison = {
        "l1_match": (
            haiku_result.get('theme_1_level_1_code') == nova_result.get('theme_1_level_1_code')
        ),
        "l2_match": (
            haiku_result.get('theme_1_level_2_code') == nova_result.get('theme_1_level_2_code')
        ),
        "l3_match": (
            haiku_result.get('theme_1_level_3_code') == nova_result.get('theme_1_level_3_code')
        ),
        "sentiment_match": (
            haiku_result.get('sentiment', {}).get('label') ==
            nova_result.get('sentiment', {}).get('label')
        )
    }

    return comparison


# Notícias de teste (reais do corpus gov.br)
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
    print("TESTE: Nova 2 Lite vs Haiku para Classificação Hierárquica")
    print("="*80)
    print()

    results = []

    for case in TEST_CASES:
        print(f"\n{'='*80}")
        print(f"TESTE #{case['id']}: {case['title'][:60]}...")
        print('='*80)

        prompt = build_classification_prompt(case['title'], case['content'])

        # Teste Haiku
        print(f"\n[1/2] Testando HAIKU...")
        haiku_result, haiku_latency, haiku_usage = call_bedrock(HAIKU_MODEL, prompt)

        if haiku_result:
            print(f"  ✓ Latência: {haiku_latency:.2f}s")
            print(f"  ✓ Tokens: {haiku_usage.get('input_tokens', 0)} in, {haiku_usage.get('output_tokens', 0)} out")
            print(f"  ✓ L1: {haiku_result.get('theme_1_level_1_label')}")
            print(f"  ✓ L2: {haiku_result.get('theme_1_level_2_label')}")
            print(f"  ✓ L3: {haiku_result.get('theme_1_level_3_label')}")
            print(f"  ✓ Resumo: {haiku_result.get('summary', '')[:80]}...")
        else:
            print("  ✗ FALHOU")

        time.sleep(1)  # Rate limit

        # Teste Nova
        print(f"\n[2/2] Testando NOVA 2 LITE...")
        nova_result, nova_latency, nova_usage = call_bedrock(NOVA_MODEL, prompt)

        if nova_result:
            print(f"  ✓ Latência: {nova_latency:.2f}s")
            print(f"  ✓ Tokens: {nova_usage.get('input_tokens', 0)} in, {nova_usage.get('output_tokens', 0)} out")
            print(f"  ✓ L1: {nova_result.get('theme_1_level_1_label')}")
            print(f"  ✓ L2: {nova_result.get('theme_1_level_2_label')}")
            print(f"  ✓ L3: {nova_result.get('theme_1_level_3_label')}")
            print(f"  ✓ Resumo: {nova_result.get('summary', '')[:80]}...")
        else:
            print("  ✗ FALHOU")

        # Comparação
        if haiku_result and nova_result:
            comparison = compare_results(haiku_result, nova_result)

            print(f"\n📊 COMPARAÇÃO:")
            print(f"  L1 Match: {'✓' if comparison['l1_match'] else '✗'} ({haiku_result.get('theme_1_level_1_label')} vs {nova_result.get('theme_1_level_1_label')})")
            print(f"  L2 Match: {'✓' if comparison['l2_match'] else '✗'} ({haiku_result.get('theme_1_level_2_label')} vs {nova_result.get('theme_1_level_2_label')})")
            print(f"  L3 Match: {'✓' if comparison['l3_match'] else '✗'} ({haiku_result.get('theme_1_level_3_label')} vs {nova_result.get('theme_1_level_3_label')})")
            print(f"  Latência: Haiku {haiku_latency:.2f}s vs Nova {nova_latency:.2f}s ({'Nova mais rápido' if nova_latency < haiku_latency else 'Haiku mais rápido'})")

            results.append({
                'case_id': case['id'],
                'haiku': haiku_result,
                'nova': nova_result,
                'comparison': comparison,
                'latency': {'haiku': haiku_latency, 'nova': nova_latency}
            })

        time.sleep(2)  # Rate limit entre casos

    # Sumário final
    print(f"\n\n{'='*80}")
    print("📊 SUMÁRIO FINAL")
    print('='*80)

    if results:
        l1_matches = sum(1 for r in results if r['comparison']['l1_match'])
        l2_matches = sum(1 for r in results if r['comparison']['l2_match'])
        l3_matches = sum(1 for r in results if r['comparison']['l3_match'])

        total = len(results)

        print(f"\nAcordo entre modelos:")
        print(f"  L1 (Tema):      {l1_matches}/{total} ({l1_matches/total*100:.0f}%)")
        print(f"  L2 (Subtema):   {l2_matches}/{total} ({l2_matches/total*100:.0f}%)")
        print(f"  L3 (Específico): {l3_matches}/{total} ({l3_matches/total*100:.0f}%)")

        avg_haiku_latency = sum(r['latency']['haiku'] for r in results) / total
        avg_nova_latency = sum(r['latency']['nova'] for r in results) / total

        print(f"\nLatência média:")
        print(f"  Haiku: {avg_haiku_latency:.2f}s")
        print(f"  Nova:  {avg_nova_latency:.2f}s")
        print(f"  Diferença: {abs(avg_haiku_latency - avg_nova_latency):.2f}s ({'Nova' if nova_latency < haiku_latency else 'Haiku'} mais rápido)")

        print(f"\n💡 ANÁLISE:")
        if l1_matches == total and l2_matches == total and l3_matches == total:
            print("  ✓ EXCELENTE: Nova 2 Lite classificou IDENTICAMENTE ao Haiku em todos os casos!")
        elif l1_matches >= total * 0.8:
            print(f"  ⚠ BOM: Nova 2 Lite teve {l1_matches/total*100:.0f}% de acordo no L1 (tema principal)")
            print(f"    Diferenças em L2/L3 podem indicar nuances diferentes, não necessariamente erro.")
        else:
            print(f"  ⚠ ATENÇÃO: Nova teve apenas {l1_matches/total*100:.0f}% de acordo no L1")
            print(f"    Recomenda-se teste maior para validar qualidade.")

    print(f"\n{'='*80}\n")

    # Salvar resultados
    with open('/tmp/nova_vs_haiku_results.json', 'w') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print("Resultados salvos em: /tmp/nova_vs_haiku_results.json")


if __name__ == "__main__":
    main()
