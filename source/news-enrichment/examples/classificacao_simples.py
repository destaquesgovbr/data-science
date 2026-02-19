"""
Exemplo de uso do NewsClassifier
Classificação de notícias sem dependência de dataset
"""

from news_enrichment import NewsClassifier
import yaml
import json
from pathlib import Path

# Configuração de paths (independente de onde o script é executado)
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
ARVORE_PATH = PROJECT_ROOT / "arvore.yaml"
DATA_DIR = PROJECT_ROOT / "data"

# Carregar taxonomia (opcional)
print("Carregando taxonomia...")
with open(ARVORE_PATH, "r", encoding="utf-8") as f:
    taxonomy_raw = yaml.safe_load(f)

# Converter taxonomia do formato YAML para o formato esperado pelo cliente
def parse_taxonomy(taxonomy_raw):
    """Converte taxonomia YAML para formato estruturado."""
    taxonomy = {}

    for key, value in taxonomy_raw.items():
        code = key.split(" - ")[0].strip()
        label = key.split(" - ")[1].strip()

        taxonomy[code] = {
            "label": label,
            "subcategories": {}
        }

        if isinstance(value, dict):
            for subkey, subvalue in value.items():
                subcode = subkey.split(" - ")[0].strip()
                sublabel = subkey.split(" - ")[1].strip()

                taxonomy[code]["subcategories"][subcode] = {
                    "label": sublabel,
                    "subcategories": {}
                }

                if isinstance(subvalue, list):
                    for item in subvalue:
                        if isinstance(item, str) and " - " in item:
                            itemcode = item.split(" - ")[0].strip()
                            itemlabel = item.split(" - ")[1].strip()

                            taxonomy[code]["subcategories"][subcode]["subcategories"][itemcode] = {
                                "label": itemlabel
                            }

    return taxonomy

taxonomy = parse_taxonomy(taxonomy_raw)
print(f"✓ Taxonomia carregada: {len(taxonomy)} categorias principais\n")

# Inicializar classificador
print("="*80)
print("INICIALIZANDO CLASSIFICADOR")
print("="*80 + "\n")

classifier = NewsClassifier(
    model_id="anthropic.claude-3-haiku-20240307-v1:0",
    region="us-east-1",
    taxonomy=taxonomy,
    batch_size=4,
    sleep_between_batches=0.5,
    verbose=True
)

# Ver resumo da taxonomia
print("\n" + "="*80)
print("RESUMO DA TAXONOMIA")
print("="*80 + "\n")
taxonomy_summary = classifier.get_taxonomy_summary()
print(json.dumps(taxonomy_summary, indent=2, ensure_ascii=False))

# ============================================================================
# EXEMPLO 1: Classificar uma única notícia
# ============================================================================

print("\n" + "="*80)
print("EXEMPLO 1: CLASSIFICAÇÃO ÚNICA")
print("="*80 + "\n")

noticia_1 = {
    'unique_id': 'teste_001',
    'title': 'Governo federal assina acordo para regularizar situação fundiária em Teresópolis',
    'subtitle': 'Acordo encerra maior conflito fundiário urbano do país',
    'editorial_lead': 'Mais de 10 mil famílias de baixa renda serão beneficiadas',
    'content': '''
    O governo federal assinou um acordo histórico nesta terça-feira para regularizar
    a situação fundiária de mais de 10 mil famílias de baixa renda que vivem na região
    da Quinta do Lebrão, em Teresópolis (RJ). O acordo encerra o maior conflito fundiário
    urbano em trâmite na Justiça brasileira.

    A regularização fundiária vai garantir segurança jurídica para as famílias que vivem
    há décadas na região, permitindo o acesso a crédito, melhorias habitacionais e
    serviços públicos. O processo teve mediação do Ministério das Cidades e do Tribunal
    de Justiça do Rio de Janeiro.
    '''
}

# Classificar (retorna JSON string)
resultado_json = classifier.classify_single(noticia_1, return_format="json")

print("Resultado (JSON):")
print(resultado_json)

# Ou retornar como dict
resultado_dict = classifier.classify_single(noticia_1, return_format="dict")

print("\n" + "-"*80)
print("Resumo da classificação:")
print(f"  Tema Nível 1: {resultado_dict['theme_1_level_1_label']}")
print(f"  Tema Nível 2: {resultado_dict['theme_1_level_2_label']}")
print(f"  Tema Nível 3: {resultado_dict['theme_1_level_3_label']}")
print(f"  Resumo: {resultado_dict['summary']}")

# ============================================================================
# EXEMPLO 2: Classificar múltiplas notícias em batch
# ============================================================================

print("\n" + "="*80)
print("EXEMPLO 2: CLASSIFICAÇÃO EM BATCH")
print("="*80 + "\n")

noticias = [
    {
        'unique_id': 'teste_002',
        'title': 'Ministério da Educação anuncia expansão de vagas em universidades federais',
        'content': '''
        O Ministério da Educação (MEC) anunciou nesta quinta-feira a criação de 10 mil
        novas vagas em cursos de graduação de universidades federais para 2025. A expansão
        faz parte do programa de interiorização do ensino superior, com foco em regiões
        Norte e Nordeste do país.
        '''
    },
    {
        'unique_id': 'teste_003',
        'title': 'Banco Central mantém taxa Selic em 10,5% ao ano',
        'content': '''
        O Comitê de Política Monetária (Copom) do Banco Central decidiu, por unanimidade,
        manter a taxa básica de juros (Selic) em 10,5% ao ano. A decisão foi tomada em
        reunião concluída nesta quarta-feira e reflete o cenário de inflação controlada
        e crescimento econômico moderado.
        '''
    },
    {
        'unique_id': 'teste_004',
        'title': 'Ministério da Saúde lança campanha nacional de vacinação contra gripe',
        'content': '''
        O Ministério da Saúde lançou hoje a campanha nacional de vacinação contra a gripe
        (influenza) para 2025. A meta é imunizar 90% do público prioritário, que inclui
        idosos, crianças, gestantes, puérperas e profissionais de saúde. A campanha vai
        até o final de maio.
        '''
    }
]

# Classificar batch (retorna lista de dicts)
resultados = classifier.classify_batch(noticias, return_format="list")

print(f"✓ {len(resultados)} notícias classificadas\n")

# Exibir resumo
for idx, resultado in enumerate(resultados, 1):
    print(f"--- NOTÍCIA {idx} ---")
    print(f"ID: {resultado['unique_id']}")
    print(f"Tema: {resultado['most_specific_theme_label']}")
    print(f"Resumo: {resultado['summary'][:80]}...")
    print()

# Salvar resultados em arquivo JSON
output_path = DATA_DIR / "classificacoes_exemplo.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(resultados, f, ensure_ascii=False, indent=2)

print("="*80)
print(f"✓ Resultados salvos em: {output_path}")
print("="*80 + "\n")

# ============================================================================
# EXEMPLO 3: Uso sem taxonomia predefinida (classificação orgânica)
# ============================================================================

print("="*80)
print("EXEMPLO 3: CLASSIFICAÇÃO ORGÂNICA (SEM TAXONOMIA)")
print("="*80 + "\n")

classifier_organic = NewsClassifier(
    model_id="anthropic.claude-3-haiku-20240307-v1:0",
    region="us-east-1",
    taxonomy=None,  # Sem taxonomia predefinida
    verbose=False
)

noticia_teste = {
    'title': 'Petrobras anuncia descoberta de novo campo de petróleo no pré-sal',
    'content': '''
    A Petrobras anunciou hoje a descoberta de um novo campo de petróleo na camada do
    pré-sal da Bacia de Santos. Estima-se que o campo tenha reservas recuperáveis de
    1 bilhão de barris de óleo equivalente.
    '''
}

resultado_organic = classifier_organic.classify_single(noticia_teste, return_format="dict")

print("Classificação orgânica (LLM cria categorias):")
print(f"  Nível 1: {resultado_organic['theme_1_level_1_label']}")
print(f"  Nível 2: {resultado_organic['theme_1_level_2_label']}")
print(f"  Nível 3: {resultado_organic['theme_1_level_3_label']}")
print(f"  Resumo: {resultado_organic['summary']}")

print("\n" + "="*80)
print("EXEMPLOS CONCLUÍDOS!")
print("="*80)
