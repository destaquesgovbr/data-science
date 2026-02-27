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
from typing import Optional, Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class BedrockLLMClient:
    """Cliente para AWS Bedrock com batch processing."""

    def __init__(
        self,
        model_id: str = "anthropic.claude-3-haiku-20240307-v1:0",
        region: str = "us-east-1",
        taxonomy: Optional[Dict] = None,
        batch_size: int = 8,
        sleep_between_batches: float = 0.2,
        max_retries: int = 3,
        # Credenciais AWS (opcionais - para portabilidade)
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None
    ):
        """
        Inicializa o cliente Bedrock.

        Args:
            model_id: ID do modelo Claude no Bedrock
            region: Região AWS
            taxonomy: Taxonomia predefinida (opcional)
            batch_size: Número de notícias processadas em paralelo
            sleep_between_batches: Delay entre batches (rate limiting)
            max_retries: Número máximo de tentativas em caso de erro
            aws_access_key_id: AWS Access Key (opcional - usa env vars se None)
            aws_secret_access_key: AWS Secret Key (opcional - usa env vars se None)
            aws_session_token: Token de sessão AWS (opcional - para credenciais temporárias)
        """
        self.model_id = model_id
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
        logger.info(f"Cliente Bedrock inicializado: {model_id} na região {region}")

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
                response = self._call_bedrock(prompt)

                # Parse response
                enriched_data = self._parse_response(response)

                # Combinar com dados originais
                result = {**row, **enriched_data}
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
  "summary": "Governo federal anuncia proposta de reforma tributária. Medida visa simplificar sistema e reduzir carga sobre empresas."
}}"""

        return prompt

    def _format_taxonomy(self) -> str:
        """Formata taxonomia para inclusão no prompt."""
        if not self.taxonomy:
            return ""

        # TODO: Implementar formatação hierárquica da taxonomia
        return json.dumps(self.taxonomy, indent=2, ensure_ascii=False)

    def _call_bedrock(self, prompt: str) -> str:
        """
        Realiza chamada ao Bedrock.

        Args:
            prompt: Prompt para o modelo

        Returns:
            Resposta do modelo (texto)
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

        return content

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
            'summary': None
        }

        return {**row, **fallback_fields}
