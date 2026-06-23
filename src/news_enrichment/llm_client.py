"""
BedrockLLMClient - Interface com AWS Bedrock para enriquecimento de notícias
Suporta batch processing para otimização de performance e custo
"""
import boto3
import json
import time
import logging
import re
import random
import hashlib
from typing import Optional, Dict, List, Tuple, Union
from concurrent.futures import ThreadPoolExecutor, as_completed
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# =============================================================================
# NER — Fase 2 (taxonomia evoluída)
# =============================================================================

# Versão do prompt NER. Incrementar ao mudar a taxonomia/few-shots/instruções.
# Gravado em news_llm_raw.prompt_version para rastreabilidade/idempotência.
NER_PROMPT_VERSION = "ner-v1"

# Modelos Bedrock — IDs SEMPRE configuráveis por env/config (nunca hardcode adivinhado).
#
# Chamada combinada (tema + resumo + sentimento): mantém o Haiku legado por ora.
DEFAULT_ENRICHMENT_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"
# Chamada NER dedicada: em produção é Claude Sonnet 4.6 via inference-profile do
# Bedrock, definido pela env var NER_MODEL_ID no deploy (Terraform).
# TODO(NER): definir NER_MODEL_ID em produção com o ID do inference-profile do
# Claude Sonnet 4.6 (algo como "us.anthropic.claude-sonnet-4-6-<...>"). NÃO
# inventar o sufixo aqui — confirmar no console do Bedrock (us-east-1). O default
# abaixo cai no Haiku legado apenas para que dev/testes locais funcionem sem env.
DEFAULT_NER_MODEL_ID = DEFAULT_ENRICHMENT_MODEL_ID

# Tipos sancionados na saída do NER. MISC NÃO é sancionado (vira resíduo descartado).
SANCTIONED_ENTITY_TYPES = frozenset(
    {"ORG", "PER", "LOC", "EVENT", "POLICY", "LAW", "WORK", "PRODUCT"}
)

# Normalização da cauda de tipos: variantes que o modelo às vezes emite → tipo sancionado.
_TYPE_TAIL_NORMALIZATION = {
    "PROGRAM": "POLICY",
    "PROGRAMA": "POLICY",
    "DECRETO": "POLICY",
    "DECREE": "POLICY",
    "AWARD": "EVENT",
    "PREMIO": "EVENT",
    "PRÊMIO": "EVENT",
}


def _extract_usage(response_body: dict) -> Dict[str, int]:
    """Extrai usage{input_tokens,output_tokens} do corpo Anthropic-on-Bedrock.

    Campos ausentes → 0 (nunca quebra o ledger de cota). Confirmado empiricamente:
    o corpo da resposta traz `usage.input_tokens` e `usage.output_tokens`.
    """
    usage = (response_body or {}).get("usage") or {}
    try:
        in_tok = int(usage.get("input_tokens", 0) or 0)
    except (TypeError, ValueError):
        in_tok = 0
    try:
        out_tok = int(usage.get("output_tokens", 0) or 0)
    except (TypeError, ValueError):
        out_tok = 0
    return {"input_tokens": in_tok, "output_tokens": out_tok}


# =============================================================================
# Content Safety — Guardrails para resumos gerados por LLM
# =============================================================================


def check_content_safety_regex(text: str) -> Tuple[bool, Optional[str]]:
    """
    Verifica segurança de conteúdo usando regex (< 1ms).

    Bloqueia conteúdo com:
    - PII: CPF, RG, telefone, email
    - Palavras ofensivas (lista customizada)

    Args:
        text: Texto a ser verificado (resumo)

    Returns:
        (is_safe, reason_if_unsafe)
        - is_safe: True se conteúdo é seguro
        - reason_if_unsafe: Descrição do problema se bloqueado

    Examples:
        >>> check_content_safety_regex("Resumo limpo sobre agricultura.")
        (True, None)

        >>> check_content_safety_regex("CPF: 123.456.789-00")
        (False, "CPF detectado")
    """
    # PII: CPF (formato XXX.XXX.XXX-XX)
    if re.search(r'\d{3}\.\d{3}\.\d{3}-\d{2}', text):
        return False, "CPF detectado"

    # PII: Telefone brasileiro (formato (XX) XXXXX-XXXX ou (XX) XXXX-XXXX)
    if re.search(r'\(\d{2}\)\s?\d{4,5}-?\d{4}', text):
        return False, "Telefone detectado"

    # PII: Email
    if re.search(r'\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b', text, re.IGNORECASE):
        return False, "Email detectado"

    # PII: RG (formato XX.XXX.XXX-X)
    if re.search(r'\d{2}\.\d{3}\.\d{3}-\d{1}', text):
        return False, "RG detectado"

    # Palavras ofensivas (lista básica - expandir conforme necessário)
    # NOTA: Lista conservadora para evitar falsos positivos
    offensive_words = [
        'idiota', 'imbecil', 'burro', 'estúpido', 'estupido',
        'cretino', 'débil', 'debil', 'retardado', 'mongolóide', 'mongoloide',
        # Adicionar mais conforme identificado em produção
    ]

    for word in offensive_words:
        # Word boundary para evitar falsos positivos (ex: "estudo" não contém "estúpido")
        pattern = rf'\b{re.escape(word)}\b'
        if re.search(pattern, text, re.IGNORECASE):
            return False, f"Linguagem ofensiva: {word}"

    return True, None


def verify_with_llm(
    summary: str,
    bedrock_client,
    model_id: str = DEFAULT_ENRICHMENT_MODEL_ID,
    max_retries: int = 2
) -> Tuple[bool, Optional[str]]:
    """
    Verifica segurança de conteúdo usando Haiku (~200ms).

    Usado apenas para casos suspeitos que passaram pelo regex mas contêm
    keywords ambíguas que requerem análise contextual.

    Args:
        summary: Texto a ser verificado
        bedrock_client: Cliente boto3 do Bedrock
        model_id: ID do modelo para verificação (default: Haiku)
        max_retries: Tentativas em caso de erro

    Returns:
        (is_safe, reason_if_unsafe)

    Examples:
        >>> verify_with_llm("Ministro anuncia programa social.", client)
        (True, None)

        >>> verify_with_llm("Texto com discurso de ódio...", client)
        (False, "Discurso de ódio detectado")
    """
    prompt = f"""Analise o seguinte resumo de notícia governamental brasileira e responda APENAS "SAFE" ou "UNSAFE: [razão]".

Marque como UNSAFE se o resumo contiver:
- Linguagem ofensiva, racista ou discriminatória
- Discurso de ódio contra grupos ou indivíduos
- Violência explícita ou ameaças
- Conteúdo sexual explícito
- Incitação a crimes

Marque como SAFE se o resumo for uma notícia governamental factual, mesmo que trate de temas sensíveis como segurança pública, saúde ou legislação.

RESUMO:
{summary}

RESPOSTA:"""

    for attempt in range(max_retries):
        try:
            response = bedrock_client.invoke_model(
                modelId=model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 50,
                    "temperature": 0.0,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ]
                })
            )

            response_body = json.loads(response["body"].read())
            result_text = response_body.get("content", [{}])[0].get("text", "").strip()

            if result_text.startswith("UNSAFE"):
                # Extrair razão após "UNSAFE:"
                reason = result_text.replace("UNSAFE:", "").strip()
                return False, reason if reason else "Conteúdo inapropriado"

            # Se começa com "SAFE" ou não tem "UNSAFE", considera seguro
            return True, None

        except ClientError as e:
            logger.warning(f"Erro ao verificar segurança com LLM (tentativa {attempt + 1}/{max_retries}): {e}")
            if attempt == max_retries - 1:
                # Última tentativa falhou - por segurança, considera suspeito
                logger.error(f"Todas as tentativas de verificação LLM falharam para: {summary[:100]}...")
                return False, "Erro na verificação de segurança (fail-safe)"

            time.sleep(0.5 * (attempt + 1))  # Backoff exponencial

    # Nunca deveria chegar aqui, mas por segurança
    return False, "Erro na verificação de segurança"


def check_summary_safety(
    summary: str,
    bedrock_client,
    model_id: str = DEFAULT_ENRICHMENT_MODEL_ID
) -> Tuple[bool, Optional[str]]:
    """
    Pipeline completo de verificação de segurança: Regex → (se suspeito) → LLM.

    Fluxo:
    1. Regex check (95% dos casos, < 1ms) - bloqueia PII e palavras ofensivas óbvias
    2. Detecta casos suspeitos (keywords ambíguas)
    3. LLM verification (5% dos casos, ~200ms) - análise contextual para casos ambíguos

    Args:
        summary: Texto a ser verificado
        bedrock_client: Cliente boto3 do Bedrock
        model_id: ID do modelo para verificação LLM (default: Haiku)

    Returns:
        (is_safe, reason_if_unsafe)
        - is_safe: True se conteúdo é seguro
        - reason_if_unsafe: Razão do bloqueio (prefixo indica método: "regex:" ou "llm:")

    Examples:
        >>> check_summary_safety("Ministério anuncia programa.", client)
        (True, None)

        >>> check_summary_safety("Contato: (11) 98765-4321", client)
        (False, "regex: Telefone detectado")
    """
    # Fase 1: Regex check (rápido, cobre 95% dos casos)
    is_safe_regex, reason = check_content_safety_regex(summary)
    if not is_safe_regex:
        return False, f"regex: {reason}"

    # Fase 2: Detectar casos suspeitos que requerem análise contextual
    # Keywords que indicam conteúdo potencialmente sensível (mas não necessariamente impróprio)
    suspicious_keywords = [
        'polêmica', 'polemica', 'conflito', 'disputa', 'confronto',
        'acusação', 'acusacao', 'denúncia', 'denuncia',
        'escândalo', 'escandalo', 'corrupção', 'corrupcao',
        'investigação', 'investigacao', 'operação', 'operacao',
        'prisão', 'prisao', 'detenção', 'detencao'
    ]

    is_suspicious = any(keyword in summary.lower() for keyword in suspicious_keywords)

    if is_suspicious:
        # Fase 3: LLM verification para casos suspeitos
        logger.info(f"Conteúdo suspeito detectado, verificando com LLM: {summary[:100]}...")
        is_safe_llm, reason = verify_with_llm(summary, bedrock_client, model_id)
        if not is_safe_llm:
            return False, f"llm: {reason}"

    # Passou por todas as verificações
    return True, None


class BedrockLLMClient:
    """Cliente para AWS Bedrock com batch processing."""

    def __init__(
        self,
        model_id: str = DEFAULT_ENRICHMENT_MODEL_ID,
        region: str = "us-east-1",
        taxonomy: Optional[Dict] = None,
        batch_size: int = 8,
        sleep_between_batches: float = 0.2,
        max_retries: int = 3,
        ner_model_id: Optional[str] = None,
        # Credenciais AWS (opcionais - para portabilidade)
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None
    ):
        """
        Inicializa o cliente Bedrock.

        Args:
            model_id: ID do modelo Claude para a chamada COMBINADA (tema+resumo+sentimento)
            region: Região AWS
            taxonomy: Taxonomia predefinida (opcional)
            batch_size: Número de notícias processadas em paralelo
            sleep_between_batches: Delay entre batches (rate limiting)
            max_retries: Número máximo de tentativas em caso de erro
            ner_model_id: ID do modelo Claude para a chamada NER dedicada
                (Sonnet 4.6 em prod). Se None, usa DEFAULT_NER_MODEL_ID.
            aws_access_key_id: AWS Access Key (opcional - usa env vars se None)
            aws_secret_access_key: AWS Secret Key (opcional - usa env vars se None)
            aws_session_token: Token de sessão AWS (opcional - para credenciais temporárias)
        """
        self.model_id = model_id
        self.ner_model_id = ner_model_id or DEFAULT_NER_MODEL_ID
        self.region = region
        self.taxonomy = taxonomy
        self.batch_size = batch_size
        self.sleep_between_batches = sleep_between_batches
        self.max_retries = max_retries

        # Criar cliente Bedrock com credenciais flexíveis
        client_kwargs = {'region_name': region}

        # Se credenciais explícitas fornecidas, adicionar ao kwargs
        if aws_access_key_id and aws_secret_access_key:
            client_kwargs['aws_access_key_id'] = aws_access_key_id
            client_kwargs['aws_secret_access_key'] = aws_secret_access_key
            if aws_session_token:
                client_kwargs['aws_session_token'] = aws_session_token
            logger.info("Usando credenciais AWS explícitas fornecidas")
        else:
            logger.info("Usando credenciais AWS do ambiente (env vars, ~/.aws/credentials ou IAM role)")

        self.client = boto3.client('bedrock-runtime', **client_kwargs)
        logger.info(
            f"Cliente Bedrock inicializado: enrichment={model_id} "
            f"ner={self.ner_model_id} na região {region}"
        )

    def enrich_news_batch(self, rows: List[Dict]) -> List[Dict]:
        """
        Enriquece múltiplas notícias em batch usando ThreadPoolExecutor.

        Args:
            rows: Lista de dicionários com dados das notícias

        Returns:
            Lista de dicionários com campos enriquecidos
        """
        results = []

        # Processar em batches
        for i in range(0, len(rows), self.batch_size):
            batch = rows[i:i + self.batch_size]
            batch_num = i // self.batch_size + 1
            logger.info(f"Processando batch {batch_num} ({len(batch)} notícias)...")

            # Processar batch em paralelo
            with ThreadPoolExecutor(max_workers=self.batch_size) as executor:
                future_to_row = {
                    executor.submit(self._enrich_single_news, row): row
                    for row in batch
                }

                for future in as_completed(future_to_row):
                    row = future_to_row[future]
                    try:
                        enriched = future.result()
                        results.append(enriched)
                    except Exception as e:
                        logger.error(f"Erro ao processar notícia {row.get('unique_id', 'unknown')}: {e}")
                        # Fallback: adicionar campos null
                        results.append(self._create_fallback_result(row))

            # Rate limiting entre batches
            if i + self.batch_size < len(rows):
                time.sleep(self.sleep_between_batches)

        return results

    def _enrich_single_news(self, row: Dict) -> Dict:
        """
        Enriquece uma única notícia com retry logic.

        Args:
            row: Dicionário com dados da notícia

        Returns:
            Dicionário com campos enriquecidos
        """
        for attempt in range(self.max_retries):
            try:
                # Construir prompt
                prompt = self._build_prompt(row)

                # Chamar Bedrock
                response, usage = self._call_bedrock(prompt)

                # Parse response
                enriched_data = self._parse_response(response)

                # Combinar com dados originais. `_usage` (tokens da chamada
                # combinada) flui até o worker, que grava no ledger de cota
                # contra o modelo combinado (model_id). Prefixo `_` para sinalizar
                # metadado interno (não é um campo de classificação).
                result = {**row, **enriched_data, "_usage": usage, "_model_id": self.model_id}
                return result

            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                is_throttling = error_code == 'ThrottlingException'

                logger.warning(
                    f"Tentativa {attempt + 1}/{self.max_retries} falhou "
                    f"para notícia {row.get('unique_id', 'unknown')}: {error_code} - {e}"
                )

                if attempt < self.max_retries - 1:
                    # Backoff diferenciado para throttling vs outros erros
                    if is_throttling:
                        # Throttling: backoff mais agressivo + jitter
                        base_sleep = 1.0 * (2 ** attempt)  # 1s, 2s, 4s
                        jitter = random.uniform(0, 0.5)  # Jitter de 0-500ms
                        sleep_time = base_sleep + jitter
                        logger.info(f"ThrottlingException: aguardando {sleep_time:.2f}s antes de retry")
                    else:
                        # Outros erros: backoff normal
                        sleep_time = 0.2 * (2 ** attempt)  # 0.2s, 0.4s, 0.8s

                    time.sleep(sleep_time)
                else:
                    # Última tentativa falhou
                    logger.error(f"Todas as tentativas falharam para notícia {row.get('unique_id', 'unknown')}")
                    return self._create_fallback_result(row)

            except Exception as e:
                # Outros erros não-AWS
                logger.warning(
                    f"Tentativa {attempt + 1}/{self.max_retries} falhou "
                    f"para notícia {row.get('unique_id', 'unknown')}: {e}"
                )

                if attempt < self.max_retries - 1:
                    # Backoff normal para erros genéricos
                    sleep_time = 0.2 * (2 ** attempt)
                    time.sleep(sleep_time)
                else:
                    # Última tentativa falhou
                    logger.error(f"Todas as tentativas falharam para notícia {row.get('unique_id', 'unknown')}")
                    return self._create_fallback_result(row)

        return self._create_fallback_result(row)

    def _build_prompt(self, row: Dict) -> str:
        """
        Constrói prompt estruturado para o LLM.

        Args:
            row: Dicionário com dados da notícia

        Returns:
            String com o prompt
        """
        # Concatenar conteúdo relevante
        title = row.get('title', '')
        subtitle = row.get('subtitle', '')
        editorial_lead = row.get('editorial_lead', '')
        content = row.get('content', '')

        # Limitar conteúdo para não exceder contexto
        content_preview = content[:2000] if content else ''

        # Construir instruções de taxonomia
        taxonomy_instructions = ""
        if self.taxonomy:
            taxonomy_instructions = f"""
INSTRUÇÕES:
Escolha as categorias da taxonomia abaixo que melhor se adequam à notícia.
Use EXATAMENTE os códigos e labels fornecidos.

TAXONOMIA DISPONÍVEL:
{self._format_taxonomy()}
"""
        else:
            taxonomy_instructions = """
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
"""

        prompt = f"""Você é um especialista em classificação temática de notícias governamentais brasileiras.

Analise a notícia abaixo e retorne APENAS um JSON válido (sem markdown, sem explicações).

{taxonomy_instructions}

TAREFAS OBRIGATÓRIAS:
1. Classifique a notícia em 3 níveis hierárquicos (theme_1_level_1/2/3).
2. Gere um campo "summary" com um resumo conciso da notícia em 1-2 frases. O summary é OBRIGATÓRIO.
3. Analise o sentimento da notícia (positive, neutral ou negative) e atribua um score entre -1.0 e 1.0.

NOTÍCIA:
Título: {title}
Subtítulo: {subtitle}
Lead: {editorial_lead}
Conteúdo: {content_preview}

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
    "label": "positive" | "neutral" | "negative",
    "score": <float entre -1.0 e 1.0>
  }}
}}"""

        return prompt

    def _format_taxonomy(self) -> str:
        """Formata taxonomia para inclusão no prompt."""
        if not self.taxonomy:
            return ""

        # TODO: Implementar formatação hierárquica da taxonomia
        return json.dumps(self.taxonomy, indent=2, ensure_ascii=False)

    def _call_bedrock(self, prompt: str) -> Tuple[str, Dict[str, int]]:
        """
        Realiza chamada ao Bedrock (chamada combinada).

        Args:
            prompt: Prompt para o modelo

        Returns:
            (texto, usage) onde usage = {input_tokens, output_tokens} extraído do
            corpo da resposta (para o ledger de cota). Campos ausentes → 0.
        """
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "temperature": 0.3,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(request_body)
        )

        # Parse response
        response_body = json.loads(response['body'].read())
        content = response_body['content'][0]['text']

        return content, _extract_usage(response_body)

    def _parse_response(self, response: str) -> Dict:
        """
        Extrai e valida JSON da resposta do LLM.

        Args:
            response: Resposta do modelo

        Returns:
            Dicionário com campos enriquecidos

        Raises:
            ValueError: Se JSON inválido ou malformado
        """
        # Tentar extrair JSON
        start_idx = response.find('{')
        end_idx = response.rfind('}') + 1

        if start_idx == -1 or end_idx <= start_idx:
            raise ValueError("JSON não encontrado na resposta")

        json_str = response[start_idx:end_idx]

        try:
            result = json.loads(json_str)

            # Validar campos obrigatórios
            required_fields = [
                'theme_1_level_1', 'theme_1_level_1_code', 'theme_1_level_1_label',
                'theme_1_level_2_code', 'theme_1_level_2_label',
                'theme_1_level_3_code', 'theme_1_level_3_label',
                'most_specific_theme_code', 'most_specific_theme_label',
                'summary'
            ]

            for field in required_fields:
                if field not in result:
                    logger.warning(f"Campo obrigatório ausente: {field}")
                    result[field] = None

            return result

        except json.JSONDecodeError as e:
            raise ValueError(f"Erro ao parsear JSON: {e}")

    def _create_fallback_result(self, row: Dict) -> Dict:
        """
        Cria resultado com campos null para notícias que falharam.

        Args:
            row: Dados originais da notícia

        Returns:
            Dicionário com campos originais + campos enriquecidos null
        """
        fallback_fields = {
            'theme_1_level_1': None,
            'theme_1_level_1_code': None,
            'theme_1_level_1_label': None,
            'theme_1_level_2_code': None,
            'theme_1_level_2_label': None,
            'theme_1_level_3_code': None,
            'theme_1_level_3_label': None,
            'most_specific_theme_code': None,
            'most_specific_theme_label': None,
            'summary': None,
            'sentiment': None
        }

        return {**row, **fallback_fields}

    # =========================================================================
    # NER — chamada Bedrock dedicada (Fase 2)
    # =========================================================================

    def _build_ner_prompt(self, article: Dict) -> str:
        """
        Constrói o prompt PT do NER com taxonomia explícita e bloco
        "NÃO é entidade". Pede forma_canonica + salience por entidade.
        NÃO pede QID do Wikidata (linkagem é fase posterior).

        Args:
            article: Dicionário com title/subtitle/editorial_lead/content

        Returns:
            String com o prompt (determinística para o mesmo artigo).
        """
        title = article.get('title', '') or ''
        subtitle = article.get('subtitle', '') or ''
        editorial_lead = article.get('editorial_lead', '') or ''
        content = article.get('content', '') or ''
        content_preview = content[:3000]

        prompt = f"""Você é um especialista em extração de entidades nomeadas (NER) em notícias governamentais brasileiras.

Sua tarefa é identificar as ENTIDADES mencionadas no texto e classificá-las segundo a taxonomia abaixo. Responda APENAS com um JSON válido (sem markdown, sem comentários, sem explicações).

TAXONOMIA (use EXATAMENTE estes tipos):
- ORG — organização nomeada: órgão público, empresa, instituição, partido, time. Ex.: "Ministério da Educação (MEC)", "Petrobras", "Finep".
- PER — pessoa específica (nome próprio). Ex.: "Luiz Inácio Lula da Silva", "Fernanda Torres".
- LOC — local nomeado: país, estado, município, região, bioma. Ex.: "Brasil", "São Paulo", "Amazônia".
- EVENT — evento nomeado e datável: campeonato, conferência, edição de prova, prêmio. Ex.: "Copa do Mundo Feminina da FIFA 2027", "Enem 2026", "COP30".
- POLICY — política ou programa público nomeado. Ex.: "Bolsa Família", "Pé-de-Meia", "Novo PAC", "Minha Casa, Minha Vida", "Cadastro Único".
- LAW — norma jurídica nomeada: lei, decreto, medida provisória, emenda. Ex.: "Lei Maria da Penha", "Constituição Federal".
- WORK — obra nomeada (livro, filme, álbum, plano/relatório nomeado). Use só quando claramente uma obra. Ex.: "Plano Safra".
- PRODUCT — produto/serviço nomeado de marca. Use só quando claramente um produto. Ex.: "Pix".

NÃO é entidade (NUNCA inclua estes — omita-os da saída):
- Tópicos/conceitos genéricos: "inteligência artificial", "dólar", "inflação", "mudança climática", "vacinação".
- Grupos demográficos / categorias de pessoas: "mulheres", "quilombolas", "idosos", "trabalhadores", "estudantes".
- Cargos e papéis genéricos sem nome próprio: "o presidente", "o ministro", "a secretária".
- Datas, números, valores monetários soltos.
Se algo não couber claramente em UM dos tipos da taxonomia, NÃO o inclua. Nunca invente tipos genéricos de "diversos"/"outro" — só os tipos da taxonomia são válidos.

EXEMPLOS DE CLASSIFICAÇÃO:
- "Bolsa Família" → POLICY · "Copa do Mundo Feminina da FIFA 2027" → EVENT · "Ministério da Saúde" → ORG.
- IMPORTANTE: "Ministério da Saúde" (Brasil) e "Ministério da Saúde do Líbano" são entidades DISTINTAS — mantenha o nome como aparece no texto; não funda.

PARA CADA ENTIDADE, retorne:
- "text": a forma de superfície exatamente como aparece no texto.
- "type": um dos tipos da taxonomia acima.
- "forma_canonica": o nome normalizado da entidade no contexto deste artigo (resolva siglas/variações para a forma mais completa mencionada no texto). Não consulte fontes externas.
- "salience": número entre 0.0 e 1.0 indicando o quão central a entidade é para a notícia.
- "count": estimativa APROXIMADA do número de ocorrências da entidade no texto (inteiro ≥ 1). Não conte com precisão — apenas estime.

NOTÍCIA:
Título: {title}
Subtítulo: {subtitle}
Lead: {editorial_lead}
Conteúdo: {content_preview}

FORMATO DE SAÍDA (JSON VÁLIDO):
{{
  "entities": [
    {{"text": "Bolsa Família", "type": "POLICY", "forma_canonica": "Bolsa Família", "salience": 0.9, "count": 3}}
  ]
}}"""

        return prompt

    def _call_bedrock_ner(self, prompt: str) -> Tuple[str, Dict[str, int]]:
        """Realiza a chamada NER ao Bedrock usando o modelo NER configurável.

        Returns:
            (texto, usage) onde usage = {input_tokens, output_tokens} extraído do
            corpo da resposta (para o ledger de cota). Campos ausentes → 0.
        """
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2000,
            "temperature": 0.0,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        response = self.client.invoke_model(
            modelId=self.ner_model_id,
            body=json.dumps(request_body)
        )

        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text'], _extract_usage(response_body)

    def extract_entities(
        self, article: Dict, return_raw: bool = False
    ) -> Union[List[Dict], Tuple[List[Dict], Optional[Dict]]]:
        """
        Extrai entidades de um artigo via chamada Bedrock dedicada (NER).

        Resiliente: qualquer falha (Bedrock, parse) resulta em lista vazia,
        nunca levanta exceção.

        Args:
            article: Dicionário com campos do artigo.
            return_raw: Se True, também devolve metadados da resposta crua
                (model_id, prompt_version, prompt_hash, raw_response) para
                gravação em news_llm_raw.

        Returns:
            Lista de entidades parseadas, OU (entities, raw_meta) se return_raw.
            raw_meta é None quando a chamada Bedrock falhou.
        """
        prompt = self._build_ner_prompt(article)
        prompt_hash = hashlib.sha256(prompt.encode("utf-8")).hexdigest()

        raw_text: Optional[str] = None
        usage: Dict[str, int] = {"input_tokens": 0, "output_tokens": 0}
        max_retries = getattr(self, "max_retries", 3)
        for attempt in range(max_retries):
            try:
                raw_text, usage = self._call_bedrock_ner(prompt)
                break
            except ClientError as e:
                error_code = e.response.get('Error', {}).get('Code', '')
                logger.warning(
                    f"NER tentativa {attempt + 1}/{max_retries} falhou "
                    f"para {article.get('unique_id', 'unknown')}: {error_code} - {e}"
                )
                if attempt < max_retries - 1:
                    sleep_time = 0.5 * (2 ** attempt) + random.uniform(0, 0.5)
                    time.sleep(sleep_time)
            except Exception as e:
                logger.warning(
                    f"NER tentativa {attempt + 1}/{max_retries} falhou "
                    f"para {article.get('unique_id', 'unknown')}: {e}"
                )
                if attempt < max_retries - 1:
                    time.sleep(0.2 * (2 ** attempt))

        if raw_text is None:
            logger.error(
                f"NER falhou em todas as tentativas para "
                f"{article.get('unique_id', 'unknown')}"
            )
            return ([], None) if return_raw else []

        entities = self._parse_entities(raw_text)

        if return_raw:
            # Armazena o objeto estruturado em news_llm_raw.raw_response (JSONB),
            # NÃO a string crua — senão psycopg2 grava um escalar JSON
            # ("{...}") e todo re-parse futuro precisaria de json.loads duplo.
            # Fallback de prosa: resposta não-JSON vira {"raw_text": ...},
            # ainda um objeto (evita double-encoding no caso comum).
            try:
                parsed_raw = json.loads(raw_text)
            except (ValueError, TypeError):
                parsed_raw = {"raw_text": raw_text}
            raw_meta = {
                "model_id": self.ner_model_id,
                "prompt_version": NER_PROMPT_VERSION,
                "prompt_hash": prompt_hash,
                "raw_response": parsed_raw,
                # usage (tokens) para o ledger de cota; o caller grava em
                # llm_daily_usage (quota_governor.record_usage). NÃO gravamos
                # aqui — o llm_client permanece sem dependência de conexão.
                "usage": usage,
            }
            return entities, raw_meta
        return entities

    def _parse_entities(self, response: str) -> List[Dict]:
        """
        Parser tolerante da resposta NER.

        - JSON malformado / ausente → lista vazia (nunca levanta).
        - count ausente → 1; salience ausente → None; forma_canonica ausente → text.
        - Normaliza cauda de tipos (PROGRAM/PROGRAMA/DECRETO→POLICY, AWARD→EVENT).
        - Descarta qualquer tipo fora do conjunto sancionado (trata como não-entidade).

        Args:
            response: Texto bruto retornado pelo modelo.

        Returns:
            Lista de menções com shape {text, type, forma_canonica, salience, count}.
        """
        if not response:
            return []

        # Localiza o JSON (objeto OU lista) tolerando markdown/texto ao redor.
        parsed = self._extract_json(response)
        if parsed is None:
            return []

        if isinstance(parsed, dict):
            raw_entities = parsed.get("entities")
        elif isinstance(parsed, list):
            raw_entities = parsed
        else:
            return []

        if not isinstance(raw_entities, list):
            return []

        entities: List[Dict] = []
        for raw in raw_entities:
            ent = self._normalize_entity(raw)
            if ent is not None:
                entities.append(ent)
        return entities

    @staticmethod
    def _extract_json(response: str):
        """Tenta extrair um objeto ou lista JSON de um texto. Retorna None se falhar."""
        candidates = []
        obj_start = response.find('{')
        obj_end = response.rfind('}')
        if obj_start != -1 and obj_end > obj_start:
            candidates.append(response[obj_start:obj_end + 1])
        list_start = response.find('[')
        list_end = response.rfind(']')
        if list_start != -1 and list_end > list_start:
            candidates.append(response[list_start:list_end + 1])

        # Prioriza o que aparece primeiro no texto.
        candidates.sort(key=lambda c: response.find(c[0]))
        for candidate in candidates:
            try:
                return json.loads(candidate)
            except (json.JSONDecodeError, ValueError):
                continue
        return None

    @staticmethod
    def _normalize_entity(raw) -> Optional[Dict]:
        """
        Normaliza uma entidade crua para o shape sancionado, ou None se inválida.
        """
        if not isinstance(raw, dict):
            return None

        text = raw.get("text")
        raw_type = raw.get("type")
        if not text or not isinstance(text, str) or not raw_type:
            return None
        if not isinstance(raw_type, str):
            return None

        # Normaliza o tipo: upper + tail-mapping + filtro de sancionados.
        ent_type = raw_type.strip().upper()
        ent_type = _TYPE_TAIL_NORMALIZATION.get(ent_type, ent_type)
        if ent_type not in SANCTIONED_ENTITY_TYPES:
            # Resíduo (inclui MISC e tópicos/grupos rotulados errado) → não-entidade.
            return None

        # count → int ≥ 1, default 1.
        count = raw.get("count", 1)
        try:
            count = int(count)
        except (TypeError, ValueError):
            count = 1
        if count < 1:
            count = 1

        # salience → float em [0,1] ou None.
        salience = raw.get("salience")
        if salience is not None:
            try:
                salience = float(salience)
                if salience < 0.0:
                    salience = 0.0
                elif salience > 1.0:
                    salience = 1.0
            except (TypeError, ValueError):
                salience = None

        forma_canonica = raw.get("forma_canonica")
        if not forma_canonica or not isinstance(forma_canonica, str):
            forma_canonica = text

        return {
            "text": text,
            "type": ent_type,
            "forma_canonica": forma_canonica,
            "salience": salience,
            "count": count,
        }
