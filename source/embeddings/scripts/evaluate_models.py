"""
Script para avaliar modelos de embedding usando métricas de retrieval

Métricas implementadas:
- NDCG@k (Normalized Discounted Cumulative Gain)
- MAP (Mean Average Precision)
- MRR (Mean Reciprocal Rank)
- Métricas de performance (throughput, latência)
"""

import time
import numpy as np
from typing import Dict, List, Tuple
from dataclasses import dataclass, asdict
import json
from pathlib import Path
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity


@dataclass
class EvaluationMetrics:
    """Resultado de avaliação de um modelo"""
    model_name: str
    ndcg_at_10_general: float
    ndcg_at_10_jargon: float
    ndcg_at_10_long_docs: float
    map_score: float
    mrr_score: float
    throughput_docs_per_sec: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    total_evaluation_time_sec: float


def dcg_at_k(relevances: List[int], k: int) -> float:
    """
    Calcula DCG@k (Discounted Cumulative Gain)

    Args:
        relevances: Lista de relevâncias (0-3) na ordem rankeada
        k: Número de posições a considerar

    Returns:
        DCG@k score
    """
    relevances = np.array(relevances[:k])
    if relevances.size == 0:
        return 0.0

    # DCG = sum(rel_i / log2(i+2)) para i=0..k-1
    discounts = np.log2(np.arange(2, relevances.size + 2))
    return np.sum(relevances / discounts)


def ndcg_at_k(relevances: List[int], k: int) -> float:
    """
    Calcula NDCG@k (Normalized DCG)

    Args:
        relevances: Lista de relevâncias (0-3) na ordem rankeada
        k: Número de posições a considerar

    Returns:
        NDCG@k score (0-1)
    """
    dcg = dcg_at_k(relevances, k)

    # IDCG = DCG do ranking ideal (relevâncias ordenadas decrescente)
    ideal_relevances = sorted(relevances, reverse=True)
    idcg = dcg_at_k(ideal_relevances, k)

    if idcg == 0:
        return 0.0

    return dcg / idcg


def average_precision(relevances: List[int]) -> float:
    """
    Calcula Average Precision (AP)

    Args:
        relevances: Lista de relevâncias (0/1 para binário, ou 0-3 para gradual)

    Returns:
        AP score
    """
    # Binarizar: >0 = relevante
    is_relevant = np.array(relevances) > 0

    if not np.any(is_relevant):
        return 0.0

    # Precision em cada posição relevante
    precisions = []
    num_relevant = 0

    for i, rel in enumerate(is_relevant):
        if rel:
            num_relevant += 1
            precision_at_i = num_relevant / (i + 1)
            precisions.append(precision_at_i)

    return np.mean(precisions) if precisions else 0.0


def reciprocal_rank(relevances: List[int]) -> float:
    """
    Calcula Reciprocal Rank (RR)

    Args:
        relevances: Lista de relevâncias

    Returns:
        RR score (1/rank do primeiro relevante)
    """
    for i, rel in enumerate(relevances):
        if rel > 0:  # Primeiro relevante
            return 1.0 / (i + 1)
    return 0.0


class ModelEvaluator:
    """Avaliador de modelos de embedding"""

    def __init__(self, model: SentenceTransformer, model_name: str):
        self.model = model
        self.model_name = model_name

    def encode_documents(self, documents: List[str], show_progress: bool = True) -> np.ndarray:
        """Codifica documentos em embeddings"""
        return self.model.encode(
            documents,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
            normalize_embeddings=True
        )

    def encode_queries(self, queries: List[str], show_progress: bool = False) -> np.ndarray:
        """Codifica queries em embeddings"""
        return self.model.encode(
            queries,
            show_progress_bar=show_progress,
            convert_to_numpy=True,
            normalize_embeddings=True
        )

    def rank_documents(
        self,
        query_embedding: np.ndarray,
        doc_embeddings: np.ndarray,
        top_k: int = 100
    ) -> List[int]:
        """
        Rankeia documentos por similaridade com a query

        Args:
            query_embedding: Embedding da query (1D)
            doc_embeddings: Embeddings dos documentos (2D)
            top_k: Número de documentos a retornar

        Returns:
            Índices dos documentos rankeados por similaridade (ordem decrescente)
        """
        # Cosine similarity (embeddings já normalizados)
        similarities = cosine_similarity(
            query_embedding.reshape(1, -1),
            doc_embeddings
        )[0]

        # Índices ordenados por similaridade (maior primeiro)
        ranked_indices = np.argsort(similarities)[::-1][:top_k]

        return ranked_indices.tolist()

    def evaluate_queries(
        self,
        queries: List[str],
        documents: List[str],
        annotations: Dict[str, Dict[str, int]],  # {query_id: {doc_id: relevance}}
        query_ids: List[str],
        doc_ids: List[str],
        k: int = 10
    ) -> Tuple[float, float, float]:
        """
        Avalia queries e retorna métricas

        Args:
            queries: Lista de textos das queries
            documents: Lista de textos dos documentos
            annotations: Anotações de relevância
            query_ids: IDs das queries
            doc_ids: IDs dos documentos
            k: Número de documentos para NDCG@k

        Returns:
            (NDCG@k, MAP, MRR)
        """
        # Codificar todos os documentos uma vez
        print(f"Codificando {len(documents)} documentos...")
        doc_embeddings = self.encode_documents(documents)

        # Codificar queries
        print(f"Codificando {len(queries)} queries...")
        query_embeddings = self.encode_queries(queries)

        # Avaliar cada query
        ndcg_scores = []
        map_scores = []
        mrr_scores = []

        for i, (query_id, query_emb) in enumerate(zip(query_ids, query_embeddings)):
            # Rankear documentos
            ranked_doc_indices = self.rank_documents(query_emb, doc_embeddings, top_k=k)

            # Obter relevâncias na ordem rankeada
            relevances = []
            for doc_idx in ranked_doc_indices:
                doc_id = doc_ids[doc_idx]
                relevance = annotations.get(query_id, {}).get(doc_id, 0)
                relevances.append(relevance)

            # Calcular métricas
            ndcg_scores.append(ndcg_at_k(relevances, k))
            map_scores.append(average_precision(relevances))
            mrr_scores.append(reciprocal_rank(relevances))

        return (
            np.mean(ndcg_scores),
            np.mean(map_scores),
            np.mean(mrr_scores)
        )

    def benchmark_performance(
        self,
        documents: List[str],
        num_iterations: int = 3
    ) -> Tuple[float, List[float]]:
        """
        Mede throughput e latência

        Args:
            documents: Lista de documentos para processar
            num_iterations: Número de iterações para média

        Returns:
            (throughput_docs_per_sec, latencies_ms)
        """
        latencies = []

        for _ in range(num_iterations):
            start = time.time()
            _ = self.encode_documents(documents, show_progress=False)
            elapsed = time.time() - start
            latencies.append(elapsed * 1000)  # ms

        # Throughput = docs/segundo
        avg_latency_sec = np.mean(latencies) / 1000
        throughput = len(documents) / avg_latency_sec if avg_latency_sec > 0 else 0

        return throughput, latencies


def evaluate_model_complete(
    model: SentenceTransformer,
    model_name: str,
    queries_general: List[str],
    queries_jargon: List[str],
    queries_long: List[str],
    documents: List[str],
    annotations: Dict[str, Dict[str, int]],
    query_ids_general: List[str],
    query_ids_jargon: List[str],
    query_ids_long: List[str],
    doc_ids: List[str],
    k: int = 10
) -> EvaluationMetrics:
    """
    Avaliação completa de um modelo

    Args:
        model: Modelo a avaliar
        model_name: Nome do modelo
        queries_general: Queries gerais
        queries_jargon: Queries com jargão BR
        queries_long: Queries para docs longos
        documents: Corpus de documentos
        annotations: Anotações {query_id: {doc_id: relevance}}
        query_ids_*: IDs das queries de cada tipo
        doc_ids: IDs dos documentos
        k: Tamanho do ranking para NDCG@k

    Returns:
        EvaluationMetrics com todas as métricas
    """
    evaluator = ModelEvaluator(model, model_name)

    start_time = time.time()

    print(f"\n{'='*80}")
    print(f"AVALIANDO MODELO: {model_name}")
    print(f"{'='*80}\n")

    # 1. NDCG@10 Geral
    print("1. Avaliando queries gerais...")
    ndcg_general, map_general, mrr_general = evaluator.evaluate_queries(
        queries_general, documents, annotations,
        query_ids_general, doc_ids, k=k
    )

    # 2. NDCG@10 Jargão BR
    print("\n2. Avaliando queries com jargão BR...")
    ndcg_jargon, map_jargon, mrr_jargon = evaluator.evaluate_queries(
        queries_jargon, documents, annotations,
        query_ids_jargon, doc_ids, k=k
    )

    # 3. NDCG@10 Docs Longos
    print("\n3. Avaliando queries para docs longos...")
    ndcg_long, _, _ = evaluator.evaluate_queries(
        queries_long, documents, annotations,
        query_ids_long, doc_ids, k=k
    )

    # 4. MAP e MRR médios (todas as queries)
    all_queries = queries_general + queries_jargon + queries_long
    all_query_ids = query_ids_general + query_ids_jargon + query_ids_long
    _, map_avg, mrr_avg = evaluator.evaluate_queries(
        all_queries, documents, annotations,
        all_query_ids, doc_ids, k=k
    )

    # 5. Benchmark de performance
    print("\n4. Benchmark de performance...")
    throughput, latencies = evaluator.benchmark_performance(documents, num_iterations=3)

    total_time = time.time() - start_time

    metrics = EvaluationMetrics(
        model_name=model_name,
        ndcg_at_10_general=ndcg_general,
        ndcg_at_10_jargon=ndcg_jargon,
        ndcg_at_10_long_docs=ndcg_long,
        map_score=map_avg,
        mrr_score=mrr_avg,
        throughput_docs_per_sec=throughput,
        latency_p50_ms=float(np.percentile(latencies, 50)),
        latency_p95_ms=float(np.percentile(latencies, 95)),
        latency_p99_ms=float(np.percentile(latencies, 99)),
        total_evaluation_time_sec=total_time
    )

    print(f"\n{'='*80}")
    print("RESULTADOS:")
    print(f"{'='*80}")
    print(f"  NDCG@10 Geral:      {metrics.ndcg_at_10_general:.4f}")
    print(f"  NDCG@10 Jargão BR:  {metrics.ndcg_at_10_jargon:.4f}")
    print(f"  NDCG@10 Docs Longos:{metrics.ndcg_at_10_long_docs:.4f}")
    print(f"  MAP:                {metrics.map_score:.4f}")
    print(f"  MRR:                {metrics.mrr_score:.4f}")
    print(f"  Throughput:         {metrics.throughput_docs_per_sec:.1f} docs/sec")
    print(f"  Latência P99:       {metrics.latency_p99_ms:.1f} ms")
    print(f"  Tempo total:        {metrics.total_evaluation_time_sec:.1f}s")
    print(f"{'='*80}\n")

    return metrics


def save_evaluation_results(metrics: List[EvaluationMetrics], output_path: Path) -> None:
    """Salva resultados da avaliação em JSON"""
    results = [asdict(m) for m in metrics]

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"✓ Resultados salvos em {output_path}")


# CLI para testes
if __name__ == "__main__":
    # Teste unitário das métricas
    print("="*80)
    print("TESTES UNITÁRIOS DAS MÉTRICAS")
    print("="*80 + "\n")

    # Teste NDCG
    print("1. Teste NDCG@10")
    relevances = [3, 2, 3, 0, 1, 2, 0, 0, 0, 0]  # Ranking do modelo
    ndcg = ndcg_at_k(relevances, k=10)
    print(f"   Relevâncias: {relevances}")
    print(f"   NDCG@10: {ndcg:.4f}")

    # Ranking ideal
    ideal = sorted(relevances, reverse=True)
    ndcg_ideal = ndcg_at_k(ideal, k=10)
    print(f"   Ideal: {ideal}")
    print(f"   NDCG@10 (ideal): {ndcg_ideal:.4f} (deve ser 1.0)")

    # Teste MAP
    print("\n2. Teste MAP")
    relevances_binary = [1, 0, 1, 0, 1, 0, 0, 0, 0, 0]
    ap = average_precision(relevances_binary)
    print(f"   Relevâncias: {relevances_binary}")
    print(f"   AP: {ap:.4f}")

    # Teste MRR
    print("\n3. Teste MRR")
    relevances_mrr = [0, 0, 1, 2, 0, 0]
    rr = reciprocal_rank(relevances_mrr)
    print(f"   Relevâncias: {relevances_mrr}")
    print(f"   RR: {rr:.4f} (1/3 = {1/3:.4f})")

    print("\n" + "="*80)
    print("✓ Testes concluídos")
    print("="*80 + "\n")
