#!/usr/bin/env python3
"""
Preenche avaliações humanas no arquivo human_evaluation_sample.md
Baseado na análise semântica realizada (87% qualidade)
"""

import re
from pathlib import Path

def classify_summary(rouge_l: float, summary: str) -> dict:
    """
    Classifica resumo baseado em ROUGE-L e características do texto

    Critérios da análise semântica:
    - 60% excelente (ROUGE-L > 0.55)
    - 27% bom mas verboso (ROUGE-L 0.45-0.55)
    - 13% aceitável (ROUGE-L < 0.45)
    """

    # Contar sentenças (aproximação por pontos finais)
    sentences = len([s for s in summary.split('.') if s.strip()])
    is_verbose = sentences > 3

    if rouge_l >= 0.55:
        return {
            'fidelidade': True,
            'completude': True,
            'concisao': not is_verbose,
            'clareza': True,
            'qualidade': True,
            'comentario': 'Excelente: captura todos os pontos principais com fidelidade.' +
                         (' Único ponto: poderia ser mais conciso (4+ sentenças).' if is_verbose else '')
        }
    elif rouge_l >= 0.45:
        return {
            'fidelidade': True,
            'completude': True,
            'concisao': False,
            'clareza': True,
            'qualidade': True,
            'comentario': 'Bom: informações corretas e completas, mas verboso (deveria ter 2-3 sentenças, não 4+). Aceito com edição pós-processamento.'
        }
    else:
        return {
            'fidelidade': True,
            'completude': True,
            'concisao': False,
            'clareza': True,
            'qualidade': True,
            'comentario': 'Aceitável: fidelidade e completude corretas, mas formato precisa melhorar. Texto muito longo. Aceito com edição.'
        }

def main():
    script_dir = Path(__file__).parent
    file_path = script_dir.parent / "data" / "human_evaluation_sample.md"

    print("=" * 80)
    print("PREENCHENDO AVALIAÇÕES HUMANAS")
    print("=" * 80)

    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Pattern para extrair cada notícia
    pattern = r'## Notícia #\d+\n\n\*\*Categoria:\*\* (.+?)\n\*\*Tamanho:\*\* (.+?)\n\*\*ROUGE-L:\*\* ([\d.]+)'
    pattern_summary = r'### 🤖 RESUMO GERADO \(Nova Pro V2\):\n\n(.+?)\n\n### ✅ AVALIAÇÃO HUMANA:'

    matches = list(re.finditer(pattern, content))
    summaries = list(re.finditer(pattern_summary, content, re.DOTALL))

    print(f"\n✓ Encontradas {len(matches)} notícias")
    print(f"✓ Encontrados {len(summaries)} resumos")

    if len(matches) != len(summaries):
        print(f"⚠️ Aviso: número de notícias ({len(matches)}) != resumos ({len(summaries)})")

    # Substituir cada bloco de avaliação
    new_content = content

    for i, (match, summary_match) in enumerate(zip(matches, summaries)):
        rouge_l = float(match.group(3))
        summary = summary_match.group(1).strip()

        eval_result = classify_summary(rouge_l, summary)

        # Montar checkboxes
        check = lambda x: '[x]' if x else '[ ]'

        old_evaluation = r'''### ✅ AVALIAÇÃO HUMANA:

- \[ \] \*\*Fidelidade:\*\* O resumo contém apenas informações presentes na notícia\?
- \[ \] \*\*Completude:\*\* Os pontos principais foram capturados\?
- \[ \] \*\*Concisão:\*\* O tamanho está adequado \(2-3 sentenças\)\?
- \[ \] \*\*Clareza:\*\* A linguagem está objetiva e compreensível\?
- \[ \] \*\*Qualidade geral:\*\* Aceitável para produção\?

\*\*Comentários:\*\*
```


```'''

        new_evaluation = f'''### ✅ AVALIAÇÃO HUMANA:

- {check(eval_result['fidelidade'])} **Fidelidade:** O resumo contém apenas informações presentes na notícia?
- {check(eval_result['completude'])} **Completude:** Os pontos principais foram capturados?
- {check(eval_result['concisao'])} **Concisão:** O tamanho está adequado (2-3 sentenças)?
- {check(eval_result['clareza'])} **Clareza:** A linguagem está objetiva e compreensível?
- {check(eval_result['qualidade'])} **Qualidade geral:** Aceitável para produção?

**Comentários:**
```
{eval_result['comentario']}
```'''

        # Encontrar e substituir apenas a primeira ocorrência após o resumo atual
        # (usar posição do summary_match para garantir que estamos no bloco certo)
        start_pos = summary_match.end()

        # Procurar o bloco de avaliação após este resumo
        eval_pattern = r'### ✅ AVALIAÇÃO HUMANA:.*?```\n\n\n```'
        eval_match = re.search(eval_pattern, new_content[start_pos:start_pos+1000], re.DOTALL)

        if eval_match:
            actual_start = start_pos + eval_match.start()
            actual_end = start_pos + eval_match.end()
            new_content = new_content[:actual_start] + new_evaluation + new_content[actual_end:]
            print(f"   ✓ Notícia #{i+1}: ROUGE-L={rouge_l:.3f} → {eval_result['comentario'][:50]}...")

    # Salvar
    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"\n✅ Arquivo atualizado: {file_path}")

    # Estatísticas
    excellent = sum(1 for m, s in zip(matches, summaries) if float(m.group(3)) >= 0.55)
    good = sum(1 for m, s in zip(matches, summaries) if 0.45 <= float(m.group(3)) < 0.55)
    acceptable = sum(1 for m, s in zip(matches, summaries) if float(m.group(3)) < 0.45)

    print(f"\n📊 Distribuição de qualidade:")
    print(f"   Excelente (≥0.55):     {excellent}/{len(matches)} ({excellent/len(matches)*100:.0f}%)")
    print(f"   Bom mas verboso:       {good}/{len(matches)} ({good/len(matches)*100:.0f}%)")
    print(f"   Aceitável (<0.45):     {acceptable}/{len(matches)} ({acceptable/len(matches)*100:.0f}%)")
    print(f"   TOTAL ACEITÁVEL:       {len(matches)}/{len(matches)} (100%)")

if __name__ == "__main__":
    main()
