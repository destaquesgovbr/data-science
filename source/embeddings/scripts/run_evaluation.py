"""
Script principal para executar avaliação completa dos modelos de embedding

Pipeline:
1. Carregar corpus de teste e queries
2. Carregar modelos de embedding
3. Avaliar cada modelo com métricas
4. Gerar relatório comparativo
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List
import pandas as pd
from datetime import datetime

from load_models import MODELS_TO_EVALUATE, load_model, ModelConfig
from prepare_corpus import CorpusManager, Document, Query, Annotation
from evaluate_models import evaluate_model_complete, save_evaluation_results, EvaluationMetrics


def load_corpus_for_evaluation(data_dir: Path) -> tuple:
    """
    Carrega corpus e prepara para avaliação

    Returns:
        (queries_general, queries_jargon, queries_long,
         documents, annotations,
         query_ids_general, query_ids_jargon, query_ids_long, doc_ids)
    """
    manager = CorpusManager(data_dir)

    # Carregar dados
    docs = manager.load_documents()
    queries = manager.load_queries()
    annotations = manager.load_annotations()

    # Separar queries por tipo
    queries_general = [q for q in queries if q.query_type == 'geral']
    queries_jargon = [q for q in queries if q.query_type == 'jargao_br']
    queries_long = [q for q in queries if q.query_type == 'doc_longo']

    # Preparar textos e IDs
    documents = [f"{d.title}\n\n{d.content}" for d in docs]
    doc_ids = [d.id for d in docs]

    query_ids_general = [q.id for q in queries_general]
    query_ids_jargon = [q.id for q in queries_jargon]
    query_ids_long = [q.id for q in queries_long]

    queries_general_text = [q.text for q in queries_general]
    queries_jargon_text = [q.text for q in queries_jargon]
    queries_long_text = [q.text for q in queries_long]

    # Preparar annotations em dict
    annotations_dict = {}
    for ann in annotations:
        if ann.query_id not in annotations_dict:
            annotations_dict[ann.query_id] = {}
        annotations_dict[ann.query_id][ann.doc_id] = ann.relevance

    return (
        queries_general_text, queries_jargon_text, queries_long_text,
        documents, annotations_dict,
        query_ids_general, query_ids_jargon, query_ids_long, doc_ids
    )


def generate_report(
    metrics_list: List[EvaluationMetrics],
    output_dir: Path
) -> None:
    """
    Gera relatório comparativo dos modelos

    Args:
        metrics_list: Lista de métricas de todos os modelos
        output_dir: Diretório para salvar relatório
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Converter para DataFrame
    df = pd.DataFrame([vars(m) for m in metrics_list])

    # Calcular score final (conforme roteiro)
    def calculate_score(row):
        score = 0
        # NDCG@10 Geral (25 pts)
        score += normalize(row['ndcg_at_10_general'], 0.70, 0.90) * 25
        # NDCG@10 Jargão BR (25 pts)
        score += normalize(row['ndcg_at_10_jargon'], 0.70, 0.90) * 25
        # MAP (10 pts)
        score += normalize(row['map_score'], 0.70, 0.90) * 10
        # MRR (5 pts)
        score += normalize(row['mrr_score'], 0.75, 0.95) * 5
        # Throughput (15 pts)
        score += normalize(row['throughput_docs_per_sec'], 50, 150) * 15
        # Latência P99 (10 pts) - menor é melhor
        score += normalize(row['latency_p99_ms'], 500, 100, reverse=True) * 10
        # Docs longos (10 pts)
        score += normalize(row['ndcg_at_10_long_docs'], 0.60, 0.85) * 10
        return round(score, 1)

    def normalize(value, min_val, max_val, reverse=False):
        """Normaliza valor para [0, 1]"""
        if reverse:
            value = max_val + min_val - value
            min_val, max_val = min_val, max_val
        normalized = (value - min_val) / (max_val - min_val)
        return max(0.0, min(1.0, normalized))

    df['final_score'] = df.apply(calculate_score, axis=1)

    # Ordenar por score
    df = df.sort_values('final_score', ascending=False)

    # Salvar resultados detalhados
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    # CSV completo
    csv_path = output_dir / f"evaluation_results_{timestamp}.csv"
    df.to_csv(csv_path, index=False)
    print(f"\n✓ Resultados detalhados: {csv_path}")

    # JSON completo
    json_path = output_dir / f"evaluation_results_{timestamp}.json"
    save_evaluation_results(metrics_list, json_path)

    # Relatório resumido em texto
    report_path = output_dir / f"evaluation_report_{timestamp}.txt"
    with open(report_path, 'w', encoding='utf-8') as f:
        f.write("="*100 + "\n")
        f.write("RELATÓRIO DE AVALIAÇÃO DOS MODELOS DE EMBEDDING\n")
        f.write("="*100 + "\n\n")
        f.write(f"Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"Modelos avaliados: {len(metrics_list)}\n\n")

        f.write("="*100 + "\n")
        f.write("RANKING FINAL\n")
        f.write("="*100 + "\n\n")

        f.write(f"{'Rank':<6} {'Modelo':<35} {'Score':<10} {'NDCG Geral':<12} {'NDCG Jargão':<12} {'Throughput':<15}\n")
        f.write("-"*100 + "\n")

        for rank, row in enumerate(df.itertuples(), 1):
            f.write(
                f"{rank:<6} "
                f"{row.model_name:<35} "
                f"{row.final_score:<10.1f} "
                f"{row.ndcg_at_10_general:<12.4f} "
                f"{row.ndcg_at_10_jargon:<12.4f} "
                f"{row.throughput_docs_per_sec:<15.1f}\n"
            )

        f.write("\n" + "="*100 + "\n")
        f.write("DETALHAMENTO DO VENCEDOR\n")
        f.write("="*100 + "\n\n")

        winner = df.iloc[0]
        f.write(f"Modelo: {winner['model_name']}\n")
        f.write(f"Score Final: {winner['final_score']:.1f}/100\n\n")
        f.write("Métricas de Qualidade:\n")
        f.write(f"  - NDCG@10 Geral:        {winner['ndcg_at_10_general']:.4f}\n")
        f.write(f"  - NDCG@10 Jargão BR:    {winner['ndcg_at_10_jargon']:.4f}\n")
        f.write(f"  - NDCG@10 Docs Longos:  {winner['ndcg_at_10_long_docs']:.4f}\n")
        f.write(f"  - MAP:                  {winner['map_score']:.4f}\n")
        f.write(f"  - MRR:                  {winner['mrr_score']:.4f}\n\n")
        f.write("Métricas de Performance:\n")
        f.write(f"  - Throughput:           {winner['throughput_docs_per_sec']:.1f} docs/sec\n")
        f.write(f"  - Latência P50:         {winner['latency_p50_ms']:.1f} ms\n")
        f.write(f"  - Latência P95:         {winner['latency_p95_ms']:.1f} ms\n")
        f.write(f"  - Latência P99:         {winner['latency_p99_ms']:.1f} ms\n\n")

        f.write("="*100 + "\n")

    print(f"✓ Relatório resumido: {report_path}")

    # Exibir ranking no console
    print("\n" + "="*100)
    print("RANKING FINAL DOS MODELOS")
    print("="*100 + "\n")
    print(f"{'Rank':<6} {'Modelo':<35} {'Score':<10} {'NDCG Geral':<12} {'NDCG Jargão':<12}")
    print("-"*100)
    for rank, row in enumerate(df.itertuples(), 1):
        print(
            f"{rank:<6} "
            f"{row.model_name:<35} "
            f"{row.final_score:<10.1f} "
            f"{row.ndcg_at_10_general:<12.4f} "
            f"{row.ndcg_at_10_jargon:<12.4f}"
        )
    print("="*100 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Avaliação completa de modelos de embedding"
    )
    parser.add_argument(
        "--data-dir",
        type=str,
        default="../data",
        help="Diretório com corpus de teste"
    )
    parser.add_argument(
        "--results-dir",
        type=str,
        default="../results",
        help="Diretório para salvar resultados"
    )
    parser.add_argument(
        "--models",
        type=str,
        nargs='+',
        help="Modelos específicos para avaliar (padrão: todos)"
    )
    parser.add_argument(
        "--category",
        choices=["multilingual", "pt-specific", "all"],
        default="all",
        help="Categoria de modelos para avaliar"
    )
    parser.add_argument(
        "--device",
        choices=["cuda", "cpu", "auto"],
        default="auto",
        help="Device para processamento"
    )
    parser.add_argument(
        "--k",
        type=int,
        default=10,
        help="Tamanho do ranking para NDCG@k"
    )

    args = parser.parse_args()

    # Paths
    script_dir = Path(__file__).parent
    data_dir = script_dir.parent / args.data_dir
    results_dir = script_dir.parent / args.results_dir

    print("\n" + "="*100)
    print("PIPELINE DE AVALIAÇÃO DE MODELOS DE EMBEDDING")
    print("="*100 + "\n")

    # 1. Carregar corpus
    print("1. Carregando corpus de teste...")
    corpus_data = load_corpus_for_evaluation(data_dir)
    (queries_general, queries_jargon, queries_long,
     documents, annotations,
     query_ids_general, query_ids_jargon, query_ids_long, doc_ids) = corpus_data

    print(f"   ✓ {len(documents)} documentos")
    print(f"   ✓ {len(queries_general)} queries gerais")
    print(f"   ✓ {len(queries_jargon)} queries jargão BR")
    print(f"   ✓ {len(queries_long)} queries docs longos")
    print(f"   ✓ {len(annotations)} anotações")

    # 2. Selecionar modelos
    print("\n2. Selecionando modelos...")
    configs_to_evaluate = MODELS_TO_EVALUATE

    if args.category != "all":
        configs_to_evaluate = [c for c in configs_to_evaluate if c.category == args.category]

    if args.models:
        configs_to_evaluate = [c for c in configs_to_evaluate if c.name in args.models]

    print(f"   ✓ {len(configs_to_evaluate)} modelos selecionados")

    # 3. Avaliar cada modelo
    print("\n3. Avaliando modelos...\n")
    device = None if args.device == "auto" else args.device
    all_metrics = []

    for i, config in enumerate(configs_to_evaluate, 1):
        print(f"\n{'='*100}")
        print(f"MODELO {i}/{len(configs_to_evaluate)}: {config.name}")
        print(f"{'='*100}\n")

        try:
            # Carregar modelo
            model = load_model(config, device=device)

            # Avaliar
            metrics = evaluate_model_complete(
                model=model,
                model_name=config.name,
                queries_general=queries_general,
                queries_jargon=queries_jargon,
                queries_long=queries_long,
                documents=documents,
                annotations=annotations,
                query_ids_general=query_ids_general,
                query_ids_jargon=query_ids_jargon,
                query_ids_long=query_ids_long,
                doc_ids=doc_ids,
                k=args.k
            )

            all_metrics.append(metrics)

            # Liberar memória
            del model
            import torch
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        except Exception as e:
            print(f"\n✗ Erro ao avaliar {config.name}: {e}")
            print("Continuando com próximo modelo...\n")
            continue

    # 4. Gerar relatório
    if all_metrics:
        print("\n4. Gerando relatório comparativo...")
        generate_report(all_metrics, results_dir)
        print("\n✓ Avaliação completa!")
    else:
        print("\n✗ Nenhum modelo foi avaliado com sucesso.")


if __name__ == "__main__":
    main()
