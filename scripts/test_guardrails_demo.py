#!/usr/bin/env python3
"""
Demo de teste de guardrails com dados sintéticos (não precisa de DB).

Usage:
    poetry run python scripts/test_guardrails_demo.py
"""

import sys
from pathlib import Path

# Adiciona src/ ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from news_enrichment.llm_client import check_content_safety_regex


# Dataset de teste: resumos sintéticos + alguns suspeitos
TEST_SUMMARIES = [
    # CASOS LIMPOS (devem passar)
    {
        "title": "Ministério da Saúde anuncia nova campanha de vacinação",
        "summary": "O Ministério da Saúde lançou nesta terça-feira uma nova campanha de vacinação contra a gripe para idosos e crianças em todo o país.",
        "expected": "PASS"
    },
    {
        "title": "Governo investirá R$ 2 bilhões em infraestrutura",
        "summary": "O governo federal anunciou um pacote de investimentos de R$ 2 bilhões para obras de infraestrutura em rodovias e ferrovias.",
        "expected": "PASS"
    },
    {
        "title": "Educação: MEC divulga novas diretrizes curriculares",
        "summary": "O Ministério da Educação publicou as novas diretrizes curriculares para o ensino médio, com ênfase em ciências e tecnologia.",
        "expected": "PASS"
    },

    # CASOS COM PII (devem bloquear)
    {
        "title": "Servidor público denunciado",
        "summary": "Servidor público identificado pelo CPF 123.456.789-00 foi denunciado por irregularidades em contratos públicos.",
        "expected": "BLOCK",
        "reason": "CPF detectado"
    },
    {
        "title": "Cidadão pode solicitar informações",
        "summary": "Para solicitar informações, ligue para (11) 98765-4321 ou envie email para contato@exemplo.gov.br",
        "expected": "BLOCK",
        "reason": "Telefone detectado"
    },
    {
        "title": "Documentação necessária para benefício",
        "summary": "É necessário apresentar RG 12.345.678-9 e comprovante de residência para solicitar o benefício.",
        "expected": "BLOCK",
        "reason": "RG detectado"
    },

    # CASOS COM LINGUAGEM OFENSIVA (devem bloquear)
    {
        "title": "Críticas ao ministro",
        "summary": "Deputados criticaram a gestão do ministro, chamando-o de idiota e incompetente.",
        "expected": "BLOCK",
        "reason": "Linguagem ofensiva"
    },
    {
        "title": "Polêmica declaração",
        "summary": "Senador fez declaração polêmica afirmando que seus oponentes são imbecis que não entendem de economia.",
        "expected": "BLOCK",
        "reason": "Linguagem ofensiva"
    },

    # CASOS LIMPOS COM PALAVRAS SIMILARES (devem passar - teste de word boundary)
    {
        "title": "Novo estudo sobre educação",
        "summary": "Estudo mostra avanços na educação básica com novos métodos de ensino aplicados em escolas públicas.",
        "expected": "PASS"
    },
    {
        "title": "Estudantes recebem bolsas",
        "summary": "Programa de bolsas de estudo beneficia estudantes de baixa renda em universidades federais.",
        "expected": "PASS"
    },
]


def run_demo():
    """Executa demo de teste dos guardrails."""

    print("="*80)
    print("🧪 DEMO: Content Safety Guardrails")
    print("="*80)
    print()

    total = len(TEST_SUMMARIES)
    passed = 0
    failed = 0
    blocked = 0

    for i, test_case in enumerate(TEST_SUMMARIES, 1):
        title = test_case["title"]
        summary = test_case["summary"]
        expected = test_case["expected"]

        # Roda guardrails
        is_safe, blocked_reason = check_content_safety_regex(summary)

        # Verifica resultado
        actual = "PASS" if is_safe else "BLOCK"
        test_passed = (actual == expected)

        # Status emoji
        if test_passed:
            status = "✅"
            passed += 1
        else:
            status = "❌"
            failed += 1

        if actual == "BLOCK":
            blocked += 1

        # Imprime resultado
        print(f"{status} Teste {i}/{total}: {title[:60]}")
        print(f"   Esperado: {expected:5s}  |  Resultado: {actual:5s}")

        if blocked_reason:
            print(f"   Motivo: {blocked_reason}")

        if not test_passed:
            print(f"   ⚠️  FALHOU! Expected {expected}, got {actual}")

        print()

    # Sumário
    print("="*80)
    print("📊 RESULTADOS:")
    print(f"   Total de testes:     {total}")
    print(f"   ✅ Passou:           {passed} ({passed/total*100:.0f}%)")
    print(f"   ❌ Falhou:           {failed} ({failed/total*100:.0f}%)")
    print(f"   🚫 Bloqueios:        {blocked} ({blocked/total*100:.0f}%)")
    print("="*80)

    if failed == 0:
        print("✅ Todos os testes passaram!")
    else:
        print(f"⚠️  {failed} teste(s) falharam - revisar implementação")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(run_demo())
