"""
Generation pipeline for RAG system.

Orchestrates retrieval + LLM generation to produce answers with citations.
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
import time

from src.retrieval import Retriever, RetrievalResult
from src.llm_providers import LLMProvider, LLMResponse


@dataclass
class RAGResponse:
    """Complete RAG response with answer and sources."""

    # Main output
    answer: str
    sources: List[Dict]  # [{title, url, chunk_text, category, agency}]

    # Metadata
    query: str
    latency_breakdown: Dict[str, float]  # {retrieval_ms, generation_ms, total_ms}

    # Token usage & cost
    tokens_input: Optional[int] = None
    tokens_output: Optional[int] = None
    cost_usd: Optional[float] = None

    # Model info
    retrieval_config: Optional[Dict] = None
    llm_model: Optional[str] = None
    llm_provider: Optional[str] = None

    def __repr__(self):
        return (
            f"RAGResponse(query='{self.query[:50]}...', "
            f"answer_length={len(self.answer)}, "
            f"sources={len(self.sources)}, "
            f"latency={self.latency_breakdown['total_ms']:.0f}ms)"
        )


class Generator:
    """
    RAG Generator that combines retrieval + LLM.

    Example:
        generator = Generator(
            retriever=retriever,
            llm_provider=llm_provider
        )

        response = generator.generate("Qual foi o valor do Plano Safra?")

        print(response.answer)
        for source in response.sources:
            print(f"[{source['title']}] {source['url']}")
    """

    def __init__(
        self,
        retriever: Retriever,
        llm_provider: LLMProvider,
        prompt_template: Optional[str] = None,
        min_source_score: float = 0.0
    ):
        """
        Initialize generator.

        Args:
            retriever: Retriever instance
            llm_provider: LLM provider (Bedrock, Ollama, etc)
            prompt_template: Custom prompt template (optional)
            min_source_score: Minimum score for sources (default: 0.0)
                            Sources with score < threshold are filtered out
        """
        self.retriever = retriever
        self.llm = llm_provider
        self.prompt_template = prompt_template or self._default_prompt_template()
        self.min_source_score = min_source_score

    def generate(
        self,
        query: str,
        max_tokens: int = 2000,
        temperature: float = 0.0,
        filters: Optional[Dict] = None
    ) -> RAGResponse:
        """
        Generate answer for query using RAG.

        Args:
            query: User question
            max_tokens: Max tokens for LLM response
            temperature: LLM temperature (0 = deterministic)
            filters: Optional retrieval filters

        Returns:
            RAGResponse with answer and sources
        """

        latency_breakdown = {}

        # Step 1: Retrieval
        start = time.time()
        retrieval_results = self.retriever.retrieve(query, filters=filters)
        latency_breakdown['retrieval_ms'] = (time.time() - start) * 1000

        if not retrieval_results:
            # No results found
            return RAGResponse(
                answer="Não encontrei informações relevantes para responder sua pergunta no corpus disponível.",
                sources=[],
                query=query,
                latency_breakdown={
                    'retrieval_ms': latency_breakdown['retrieval_ms'],
                    'generation_ms': 0,
                    'total_ms': latency_breakdown['retrieval_ms']
                },
                llm_model=self.llm.model_id if hasattr(self.llm, 'model_id') else str(self.llm),
                llm_provider=getattr(self.llm, 'provider_name', 'unknown'),
                retrieval_config={
                    'num_results': 0,
                    'reranking': self.retriever.config.use_reranking
                }
            )

        # Step 2: Filter results by minimum score BEFORE building context
        # This ensures LLM only sees and cites sources that will be shown to user
        # IMPORTANT: Deduplicate by document_id first, then filter
        filtered_results = self._filter_and_deduplicate_results(retrieval_results, min_score=self.min_source_score)

        if not filtered_results:
            # All results filtered out (no relevant documents)
            return RAGResponse(
                answer="Não encontrei informações suficientemente relevantes para responder sua pergunta no corpus disponível.",
                sources=[],
                query=query,
                latency_breakdown={
                    'retrieval_ms': latency_breakdown['retrieval_ms'],
                    'generation_ms': 0,
                    'total_ms': latency_breakdown['retrieval_ms']
                },
                llm_model=self.llm.model_id if hasattr(self.llm, 'model_id') else str(self.llm),
                llm_provider=getattr(self.llm, 'provider_name', 'unknown'),
                retrieval_config={
                    'num_results': len(retrieval_results),
                    'filtered_results': 0,
                    'reranking': self.retriever.config.use_reranking
                }
            )

        # Step 3: Build context (only with filtered results)
        context = self._build_context(filtered_results)

        # Step 4: Build prompt
        prompt = self._build_prompt(query, context)

        # Step 5: LLM generation
        start = time.time()
        llm_response = self.llm.generate(
            prompt=prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            system="Você é um assistente especializado em responder perguntas sobre notícias e políticas governamentais brasileiras. Sempre cite suas fontes usando [1], [2], etc."
        )
        latency_breakdown['generation_ms'] = llm_response.latency_ms
        latency_breakdown['total_ms'] = latency_breakdown['retrieval_ms'] + latency_breakdown['generation_ms']

        # Step 6: Extract sources from filtered results
        # Now sources and context are perfectly aligned!
        sources = self._extract_sources(filtered_results, min_score=self.min_source_score)

        # Step 6: Build response
        return RAGResponse(
            answer=llm_response.text,
            sources=sources,
            query=query,
            latency_breakdown=latency_breakdown,
            tokens_input=llm_response.tokens_input,
            tokens_output=llm_response.tokens_output,
            cost_usd=llm_response.cost_usd,
            llm_model=llm_response.model,
            llm_provider=llm_response.provider,
            retrieval_config={
                'num_results': len(retrieval_results),
                'reranking': self.retriever.config.use_reranking
            }
        )

    def _filter_and_deduplicate_results(
        self,
        results: List[RetrievalResult],
        min_score: float = 0.0
    ) -> List[RetrievalResult]:
        """
        Filter and deduplicate retrieval results.

        This ensures that:
        1. Only relevant sources (score >= min_score) are used
        2. Each document appears with its best chunk only
        3. LLM sees exactly what user will see in sources

        Args:
            results: Raw retrieval results
            min_score: Minimum score threshold

        Returns:
            Filtered and deduplicated results, with ALL chunks from relevant docs
        """

        # Step 1: Group by document_id
        docs_chunks = {}
        for result in results:
            doc_id = result.document_id
            if doc_id not in docs_chunks:
                docs_chunks[doc_id] = []
            docs_chunks[doc_id].append(result)

        # Step 2: For each document, check if ANY chunk meets threshold
        # If yes, keep ALL chunks from that document (for rich context)
        filtered_results = []
        for doc_id, chunks in docs_chunks.items():
            # Find best score for this document
            best_score = max(chunk.score for chunk in chunks)

            # If best score meets threshold, include ALL chunks from this doc
            if best_score >= min_score:
                filtered_results.extend(chunks)

        # Step 3: Sort by score (best first)
        filtered_results.sort(key=lambda x: x.score, reverse=True)

        return filtered_results

    def _build_context(
        self,
        results: List[RetrievalResult],
        max_tokens: int = 8000
    ) -> str:
        """
        Build context string from retrieval results.

        Uses all chunks for rich context, but assigns source numbers by unique document_id.

        Format:
            [Fonte 1: Título do documento]
            Categoria: Agricultura
            Órgão: Ministério da Agricultura

            Conteúdo do chunk...

            ---

            [Fonte 2: ...]
            ...
        """

        context_parts = []
        total_chars = 0
        chars_per_token = 4  # Approximation for Portuguese
        max_chars = max_tokens * chars_per_token

        # Create mapping of document_id to source number (for unique documents)
        doc_to_source_num = {}
        current_source_num = 1

        for result in results:
            doc_id = result.document_id
            if doc_id not in doc_to_source_num:
                doc_to_source_num[doc_id] = current_source_num
                current_source_num += 1

        # Build context with correct source numbers
        for result in results:
            source_num = doc_to_source_num[result.document_id]

            # Format publication date for display
            published_info = ""
            if result.doc_published_at:
                # Try to format as Brazilian date (DD/MM/YYYY)
                try:
                    from datetime import datetime
                    if 'T' in result.doc_published_at:
                        dt = datetime.fromisoformat(result.doc_published_at.replace('Z', '+00:00'))
                    else:
                        dt = datetime.fromisoformat(result.doc_published_at)
                    published_info = f"Data de Publicação: {dt.strftime('%d/%m/%Y')}\n"
                except:
                    published_info = f"Data de Publicação: {result.doc_published_at}\n"

            chunk_text = f"""[Fonte {source_num}: {result.doc_title or 'Documento sem título'}]
Categoria: {result.doc_category or 'N/A'}
Órgão: {result.doc_agency or 'N/A'}
{published_info}
{result.content}

---
"""

            chunk_chars = len(chunk_text)

            # Check if adding this chunk exceeds limit
            if total_chars + chunk_chars > max_chars:
                break

            context_parts.append(chunk_text)
            total_chars += chunk_chars

        return "\n".join(context_parts)

    def _build_prompt(self, query: str, context: str) -> str:
        """Build final prompt with query and context."""

        return self.prompt_template.format(
            context=context,
            query=query
        )

    def _default_prompt_template(self) -> str:
        """
        Default prompt template for RAG.

        Format placeholders: {context}, {query}
        """

        return """Você é um assistente especializado em responder perguntas sobre notícias e políticas governamentais brasileiras.

Sua tarefa é responder a pergunta do usuário com base APENAS nas informações fornecidas nas fontes abaixo.

INSTRUÇÕES IMPORTANTES:
1. SEMPRE cite suas fontes usando [1], [2], etc. para cada informação que você mencionar
2. Se uma informação não estiver nas fontes fornecidas, diga claramente "não encontrei essa informação nas fontes disponíveis"
3. Não invente ou especule informações
4. Se a pergunta não puder ser respondida com as fontes disponíveis, seja honesto e explique isso
5. Mantenha um tom profissional e objetivo
6. Se houver valores monetários, datas ou números, sempre cite a fonte específica
7. ATENÇÃO À TEMPORALIDADE: Cada fonte possui uma "Data de Publicação". Quando relevante (perguntas sobre "recente", "último", "atual", etc.), considere a ordem cronológica das notícias. Mencione datas quando apropriado para contextualizar a informação.

FONTES DISPONÍVEIS:
{context}

PERGUNTA DO USUÁRIO:
{query}

RESPOSTA (com citações):"""

    def _extract_sources(
        self,
        results: List[RetrievalResult],
        min_score: float = 0.0
    ) -> List[Dict]:
        """
        Extract source metadata from retrieval results.

        NOTE: Filtering should be done BEFORE calling this method via
        _filter_and_deduplicate_results(). This method just deduplicates
        and formats for display.

        Args:
            results: List of retrieval results (already filtered)
            min_score: Minimum score threshold (for safety check)

        Returns list of dicts with source information.
        """

        # Deduplicate by document_id, keeping best score
        seen_docs = {}

        for result in results:
            doc_id = result.document_id

            if doc_id not in seen_docs:
                # First time seeing this document
                seen_docs[doc_id] = result
            else:
                # Already seen - keep the one with better score
                if result.score > seen_docs[doc_id].score:
                    seen_docs[doc_id] = result

        # Convert to list of sources (in order of best score)
        unique_results = sorted(seen_docs.values(), key=lambda x: x.score, reverse=True)

        # Safety filter (should already be filtered, but just in case)
        filtered_results = [r for r in unique_results if r.score >= min_score]

        sources = []
        for i, result in enumerate(filtered_results, 1):
            # Format publication date for API response
            published_date = None
            if result.doc_published_at:
                try:
                    from datetime import datetime
                    if 'T' in result.doc_published_at:
                        dt = datetime.fromisoformat(result.doc_published_at.replace('Z', '+00:00'))
                    else:
                        dt = datetime.fromisoformat(result.doc_published_at)
                    published_date = dt.strftime('%d/%m/%Y')
                except:
                    published_date = result.doc_published_at

            sources.append({
                'index': i,
                'title': result.doc_title or 'Documento sem título',
                'url': result.doc_url or 'URL não disponível',
                'category': result.doc_category or 'N/A',
                'agency': result.doc_agency or 'N/A',
                'published_at': published_date,
                'chunk_text': result.content[:300] + '...' if len(result.content) > 300 else result.content,
                'score': result.score
            })

        return sources


class PromptLibrary:
    """
    Library of different prompt templates for different scenarios.

    Usage:
        template = PromptLibrary.get('factual')
        generator = Generator(retriever, llm, prompt_template=template)
    """

    TEMPLATES = {
        'default': """Você é um assistente especializado em responder perguntas sobre notícias e políticas governamentais brasileiras.

Sua tarefa é responder a pergunta do usuário com base APENAS nas informações fornecidas nas fontes abaixo.

INSTRUÇÕES IMPORTANTES:
1. SEMPRE cite suas fontes usando [1], [2], etc. para cada informação que você mencionar
2. Se uma informação não estiver nas fontes fornecidas, diga claramente "não encontrei essa informação nas fontes disponíveis"
3. Não invente ou especule informações
4. Se a pergunta não puder ser respondida com as fontes disponíveis, seja honesto e explique isso
5. Mantenha um tom profissional e objetivo
6. Se houver valores monetários, datas ou números, sempre cite a fonte específica

FONTES DISPONÍVEIS:
{context}

PERGUNTA DO USUÁRIO:
{query}

RESPOSTA (com citações):""",

        'factual': """Você é um assistente que responde perguntas factuais sobre notícias governamentais brasileiras.

Responda com precisão usando APENAS as informações das fontes fornecidas. SEMPRE cite fontes [1], [2].

REGRAS:
- Para valores, datas, nomes: SEMPRE cite a fonte exata
- Se não souber: "Não encontrei essa informação nas fontes"
- Seja conciso e direto
- Priorize fatos sobre interpretações

FONTES:
{context}

PERGUNTA: {query}

RESPOSTA:""",

        'summary': """Você é um assistente que cria resumos de políticas governamentais brasileiras.

Sintetize as informações das fontes fornecidas em um resumo claro e estruturado. Cite fontes [1], [2].

INSTRUÇÕES:
- Organize em tópicos principais
- Destaque valores e datas importantes
- Mencione órgãos/agências responsáveis
- Seja objetivo e completo
- SEMPRE cite fontes para cada informação

FONTES:
{context}

PERGUNTA: {query}

RESUMO:""",

        'comparison': """Você é um assistente que compara políticas e programas governamentais brasileiros.

Compare as informações das fontes fornecidas de forma estruturada. Cite fontes [1], [2].

FORMATO:
1. Aspectos em comum
2. Diferenças principais
3. Valores/números (com fontes)
4. Conclusão

FONTES:
{context}

PERGUNTA: {query}

COMPARAÇÃO:"""
    }

    @classmethod
    def get(cls, template_name: str = 'default') -> str:
        """Get prompt template by name."""

        if template_name not in cls.TEMPLATES:
            raise ValueError(
                f"Unknown template: {template_name}. "
                f"Available: {list(cls.TEMPLATES.keys())}"
            )

        return cls.TEMPLATES[template_name]

    @classmethod
    def list_templates(cls) -> List[str]:
        """List available template names."""
        return list(cls.TEMPLATES.keys())
