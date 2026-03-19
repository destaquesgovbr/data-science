"""
Script para preparar corpus de teste e queries para avaliação de embeddings

Estrutura de dados:
- 100 notícias (10 categorias × 10 docs)
- 30-40 queries (gerais, jargão BR, docs longos)
- Anotações de relevância (ground truth)
"""

import json
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass, asdict
import pandas as pd


@dataclass
class Document:
    """Documento do corpus"""
    id: str
    title: str
    content: str
    category: str
    length: int
    metadata: Dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}
        self.length = len(self.content.split())


@dataclass
class Query:
    """Query de busca"""
    id: str
    text: str
    query_type: str  # 'geral', 'jargao_br', 'doc_longo'
    expected_category: str
    metadata: Dict = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


@dataclass
class Annotation:
    """Anotação de relevância query-documento"""
    query_id: str
    doc_id: str
    relevance: int  # 0=irrelevante, 1=pouco, 2=relevante, 3=muito relevante
    notes: str = ""


class CorpusManager:
    """Gerenciador de corpus de teste"""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.docs_dir = self.data_dir / "documents"
        self.queries_dir = self.data_dir / "queries"
        self.annotations_dir = self.data_dir / "annotations"

        # Criar diretórios se não existirem
        for dir_path in [self.docs_dir, self.queries_dir, self.annotations_dir]:
            dir_path.mkdir(parents=True, exist_ok=True)

    def add_document(self, doc: Document) -> None:
        """Adiciona documento ao corpus"""
        doc_path = self.docs_dir / f"{doc.id}.json"
        with open(doc_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(doc), f, ensure_ascii=False, indent=2)

    def add_documents_batch(self, docs: List[Document]) -> None:
        """Adiciona múltiplos documentos"""
        for doc in docs:
            self.add_document(doc)
        print(f"✓ {len(docs)} documentos adicionados")

    def load_documents(self) -> List[Document]:
        """Carrega todos os documentos"""
        docs = []
        for doc_path in self.docs_dir.glob("*.json"):
            with open(doc_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                docs.append(Document(**data))
        return sorted(docs, key=lambda x: x.id)

    def add_query(self, query: Query) -> None:
        """Adiciona query"""
        query_path = self.queries_dir / f"{query.id}.json"
        with open(query_path, 'w', encoding='utf-8') as f:
            json.dump(asdict(query), f, ensure_ascii=False, indent=2)

    def add_queries_batch(self, queries: List[Query]) -> None:
        """Adiciona múltiplas queries"""
        for query in queries:
            self.add_query(query)
        print(f"✓ {len(queries)} queries adicionadas")

    def load_queries(self) -> List[Query]:
        """Carrega todas as queries"""
        queries = []
        for query_path in self.queries_dir.glob("*.json"):
            with open(query_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                queries.append(Query(**data))
        return sorted(queries, key=lambda x: x.id)

    def add_annotation(self, annotation: Annotation) -> None:
        """Adiciona anotação de relevância"""
        ann_file = self.annotations_dir / f"query_{annotation.query_id}.jsonl"
        with open(ann_file, 'a', encoding='utf-8') as f:
            json.dump(asdict(annotation), f, ensure_ascii=False)
            f.write('\n')

    def add_annotations_batch(self, annotations: List[Annotation]) -> None:
        """Adiciona múltiplas anotações"""
        for ann in annotations:
            self.add_annotation(ann)
        print(f"✓ {len(annotations)} anotações adicionadas")

    def load_annotations(self) -> List[Annotation]:
        """Carrega todas as anotações"""
        annotations = []
        for ann_file in self.annotations_dir.glob("*.jsonl"):
            with open(ann_file, 'r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():  # Pular linhas vazias
                        data = json.loads(line)  # loads, não load!
                        annotations.append(Annotation(**data))
        return annotations

    def get_corpus_stats(self) -> Dict:
        """Retorna estatísticas do corpus"""
        docs = self.load_documents()
        queries = self.load_queries()
        annotations = self.load_annotations()

        categories = {}
        for doc in docs:
            categories[doc.category] = categories.get(doc.category, 0) + 1

        query_types = {}
        for query in queries:
            query_types[query.query_type] = query_types.get(query.query_type, 0) + 1

        return {
            'total_documents': len(docs),
            'total_queries': len(queries),
            'total_annotations': len(annotations),
            'categories': categories,
            'query_types': query_types,
            'avg_doc_length': sum(d.length for d in docs) / len(docs) if docs else 0,
        }

    def export_to_dataframe(self) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Exporta corpus para DataFrames pandas"""
        docs = self.load_documents()
        queries = self.load_queries()
        annotations = self.load_annotations()

        df_docs = pd.DataFrame([asdict(d) for d in docs])
        df_queries = pd.DataFrame([asdict(q) for q in queries])
        df_annotations = pd.DataFrame([asdict(a) for a in annotations])

        return df_docs, df_queries, df_annotations


def create_sample_corpus(data_dir: Path) -> None:
    """Cria corpus de exemplo para teste"""
    manager = CorpusManager(data_dir)

    # Categorias do governo brasileiro
    categories = [
        "Saúde", "Educação", "Economia", "Meio Ambiente", "Segurança Pública",
        "Assistência Social", "Infraestrutura", "Cultura", "Ciência e Tecnologia", "Agricultura"
    ]

    # Documentos de exemplo (placeholder - você deve substituir por dados reais)
    sample_docs = []
    for i, category in enumerate(categories):
        for j in range(25):  # 25 docs por categoria = 250 total
            doc = Document(
                id=f"doc_{i:02d}_{j:02d}",
                title=f"Notícia sobre {category} - Exemplo {j+1}",
                content=f"Este é um documento de exemplo sobre {category}. "
                        f"O Ministério responsável anunciou novas medidas. "
                        f"[PLACEHOLDER - Substituir por conteúdo real de notícia do gov.br]",
                category=category,
                length=0  # será calculado no __post_init__
            )
            sample_docs.append(doc)

    manager.add_documents_batch(sample_docs)

    # Queries de exemplo (60 total: 25 geral + 25 jargão + 10 longos)
    sample_queries = []

    # 25 queries gerais
    for i in range(25):
        sample_queries.append(
            Query(f"q{i+1:03d}", f"exemplo query geral {i+1}", "geral", categories[i % 10])
        )

    # 25 queries jargão
    for i in range(25):
        sample_queries.append(
            Query(f"q{i+26:03d}", f"exemplo query jargao {i+1}", "jargao_br", categories[i % 10])
        )

    # 10 queries docs longos
    for i in range(10):
        sample_queries.append(
            Query(f"q{i+51:03d}", f"exemplo query doc longo {i+1}", "doc_longo", categories[i])
        )

    manager.add_queries_batch(sample_queries)

    # Anotações de exemplo (15 docs por query para as primeiras 5 queries)
    sample_annotations = []
    for query_id in ["q001", "q002", "q003", "q004", "q005"]:
        for doc_idx in range(15):
            relevance = 3 if doc_idx < 3 else (2 if doc_idx < 7 else (1 if doc_idx < 11 else 0))
            sample_annotations.append(
                Annotation(query_id, f"doc_00_{doc_idx:02d}", relevance, f"Exemplo relevância {relevance}")
            )

    manager.add_annotations_batch(sample_annotations)

    print("\n" + "="*80)
    print("CORPUS DE EXEMPLO CRIADO")
    print("="*80)
    print("\nEstatísticas:")
    stats = manager.get_corpus_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")
    print("\n⚠️  ATENÇÃO: Este é um corpus de EXEMPLO")
    print("   Corpus planejado: 250 docs + 60 queries + ~900 anotações")
    print("   Você deve substituir por dados reais de notícias do gov.br")
    print("="*80 + "\n")


# CLI
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Preparar corpus de teste")
    parser.add_argument(
        "--data-dir",
        type=str,
        default="../data",
        help="Diretório de dados"
    )
    parser.add_argument(
        "--create-sample",
        action="store_true",
        help="Criar corpus de exemplo"
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Mostrar estatísticas do corpus"
    )
    parser.add_argument(
        "--export",
        type=str,
        help="Exportar corpus para CSV (forneça prefixo do arquivo)"
    )

    args = parser.parse_args()

    data_dir = Path(__file__).parent.parent / args.data_dir
    manager = CorpusManager(data_dir)

    if args.create_sample:
        create_sample_corpus(data_dir)

    if args.stats:
        print("\n" + "="*80)
        print("ESTATÍSTICAS DO CORPUS")
        print("="*80 + "\n")
        stats = manager.get_corpus_stats()
        for key, value in stats.items():
            print(f"{key}: {value}")
        print()

    if args.export:
        df_docs, df_queries, df_annotations = manager.export_to_dataframe()
        df_docs.to_csv(f"{args.export}_documents.csv", index=False)
        df_queries.to_csv(f"{args.export}_queries.csv", index=False)
        df_annotations.to_csv(f"{args.export}_annotations.csv", index=False)
        print(f"✓ Corpus exportado para {args.export}_*.csv")
