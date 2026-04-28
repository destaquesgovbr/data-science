"""
Reanota dataset de teste usando o classificador working (Claude Haiku).

O problema: test dataset tem categorias simples ("Agricultura", "Saúde")
            mas precisamos de códigos de taxonomia ("10.03.02 - Crédito Agrícola")

Solução: Usar Claude Haiku (modelo working confirmado pelo usuário) para
         classificar todas as 200 notícias e criar novo ground truth.

Output: news_classification_test_annotated.csv com coluna 'category_code'
"""

import sys
from pathlib import Path
import pandas as pd
from tqdm import tqdm

# Adicionar path para imports
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR.parent))

from embeddings.classifiers.bedrock_classifier_json import BedrockClassifierJSON


def main():
    """Reanota dataset de teste."""
    print("="*80)
    print("🔄 REANOTAÇÃO DO DATASET DE TESTE")
    print("="*80)

    # Paths
    input_path = BASE_DIR / 'data' / 'classification' / 'news_classification_test.csv'
    output_path = BASE_DIR / 'data' / 'classification' / 'news_classification_test_annotated.csv'
    taxonomy_path = BASE_DIR / 'data' / 'classification' / 'arvore.yaml'

    # Carregar dataset
    print(f"\n📊 Carregando dataset: {input_path}")
    df = pd.read_csv(input_path)
    print(f"   ✓ {len(df)} notícias carregadas")
    print(f"   ✓ Categorias originais: {df['category'].unique().tolist()}")

    # Criar classificador (Claude Haiku - working confirmado)
    print("\n🤖 Inicializando Claude Haiku (modelo working)...")
    classifier = BedrockClassifierJSON(
        model_id="anthropic.claude-3-haiku-20240307-v1:0",
        model_name="Claude 3 Haiku",
        provider="anthropic",
        region="us-east-1",
        taxonomy_path=str(taxonomy_path)
    )
    # Configurar pricing
    classifier.input_price_per_mtok = 0.25
    classifier.output_price_per_mtok = 1.25
    print("   ✓ Classificador inicializado")

    # Classificar todas as notícias
    print("\n" + "="*80)
    print("📝 CLASSIFICANDO NOTÍCIAS (isto pode levar alguns minutos)")
    print("="*80)

    annotations = []

    for idx, row in tqdm(df.iterrows(), total=len(df), desc="Classificando"):
        # Combinar title e content
        text = f"{row['title']}\n\n{row['content']}"

        # Classificar
        result = classifier.classify(text)

        # Extrair informações
        json_res = result.get('json_parsed')

        if json_res and result['success']:
            annotations.append({
                'category_code': result['category'],  # XX.XX.XX - Label
                'level_1_code': json_res.get('theme_1_level_1_code'),
                'level_1_label': json_res.get('theme_1_level_1_label'),
                'level_2_code': json_res.get('theme_1_level_2_code'),
                'level_2_label': json_res.get('theme_1_level_2_label'),
                'level_3_code': json_res.get('theme_1_level_3_code'),
                'level_3_label': json_res.get('theme_1_level_3_label'),
                'success': True,
                'latency': result['latency']
            })
        else:
            # Falha na classificação
            annotations.append({
                'category_code': '20.01.01 - Controle Interno',  # Fallback
                'level_1_code': '20',
                'level_1_label': 'Administração Pública',
                'level_2_code': '20.01',
                'level_2_label': 'Gestão Interna',
                'level_3_code': '20.01.01',
                'level_3_label': 'Controle Interno',
                'success': False,
                'latency': result['latency']
            })

    # Criar DataFrame anotado
    annotations_df = pd.DataFrame(annotations)

    # Combinar com dados originais
    df_annotated = pd.concat([df, annotations_df], axis=1)

    # Salvar
    print(f"\n💾 Salvando dataset anotado: {output_path}")
    df_annotated.to_csv(output_path, index=False)
    print("   ✓ Dataset salvo com sucesso!")

    # Estatísticas
    print("\n" + "="*80)
    print("📊 ESTATÍSTICAS DA REANOTAÇÃO")
    print("="*80)
    stats = classifier.get_stats()
    print(f"Total de notícias: {len(df)}")
    print(f"Classificações bem-sucedidas: {annotations_df['success'].sum()}")
    print(f"Falhas: {(~annotations_df['success']).sum()}")
    print(f"\nLatência média: {stats['avg_latency']:.3f}s")
    print(f"Input tokens: {stats['total_input_tokens']:,}")
    print(f"Output tokens: {stats['total_output_tokens']:,}")
    print(f"Custo estimado: ${stats['total_cost']:.4f}")

    # Distribuição por nível 1
    print(f"\n📊 Distribuição por Grande Área (Nível 1):")
    level1_dist = df_annotated['level_1_label'].value_counts().head(10)
    for label, count in level1_dist.items():
        print(f"   {label}: {count} notícias ({count/len(df)*100:.1f}%)")

    print("\n" + "="*80)
    print("✅ REANOTAÇÃO CONCLUÍDA!")
    print("="*80)
    print(f"\n📄 Novo dataset: {output_path}")
    print(f"   Use este arquivo como ground truth para avaliação comparativa.")


if __name__ == '__main__':
    main()
