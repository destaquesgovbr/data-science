"""
LocalLLMClient - Interface com Ollama para enriquecimento de notícias
Suporta batch processing e múltiplos modelos locais (Qwen, DeepSeek, Mistral, Llama)
"""
import json
import time
import logging
import random
import requests
from typing import Optional, Dict, List
from concurrent.futures import ThreadPoolExecutor, as_completed

logger = logging.getLogger(__name__)


class LocalLLMClient:
    """Cliente para modelos locais via Ollama com batch processing."""

    # Modelos suportados com suas configurações otimizadas
    SUPPORTED_MODELS = {
        # Tier 1 - Qualidade/Performance Balanceada
        'qwen2.5:7b': {'size': '4.7GB', 'tier': 1},
        'deepseek-r1:7b': {'size': '4.7GB', 'tier': 1},
        'mistral:7b': {'size': '4.1GB', 'tier': 1},

        # Tier 2 - Mais Leves
        'qwen2.5:3b': {'size': '2.0GB', 'tier': 2},
        'llama3.2:3b': {'size': '2.0GB', 'tier': 2},
    }

    def __init__(
        self,
        model: str = "qwen2.5:7b",
        base_url: str = "http://localhost:11434",
        taxonomy: Optional[Dict] = None,
        batch_size: int = 2,  # Menor que Bedrock (modelo local mais lento, CPU-friendly)
        sleep_between_batches: float = 0.1,
        max_retries: int = 3,
        temperature: float = 0.3,
        timeout: int = 300  # Timeout para chamadas HTTP (5 minutos para CPU)
    ):
        """
        Inicializa o cliente Ollama.

        Args:
            model: Nome do modelo Ollama (ex: 'qwen2.5:7b', 'deepseek-r1:7b')
            base_url: URL base do Ollama (padrão: http://localhost:11434)
            taxonomy: Taxonomia predefinida (opcional)
            batch_size: Número de notícias processadas em paralelo (padrão: 4)
            sleep_between_batches: Delay entre batches
            max_retries: Número máximo de tentativas em caso de erro
            temperature: Temperatura do modelo (0.0-1.0)
            timeout: Timeout em segundos para chamadas HTTP
        """
        self.model = model
        self.base_url = base_url.rstrip('/')
        self.taxonomy = taxonomy
        self.batch_size = batch_size
        self.sleep_between_batches = sleep_between_batches
        self.max_retries = max_retries
        self.temperature = temperature
        self.timeout = timeout

        # Validar modelo
        if model not in self.SUPPORTED_MODELS:
            logger.warning(
                f"Modelo '{model}' não está na lista de recomendados. "
                f"Modelos recomendados: {list(self.SUPPORTED_MODELS.keys())}"
            )

        # Verificar se Ollama está rodando
        self._check_ollama_connection()

        logger.info(f"LocalLLMClient inicializado: {model} (via Ollama em {base_url})")

    def _check_ollama_connection(self):
        """Verifica se Ollama está rodando e o modelo está disponível."""
        try:
            # Verificar se Ollama está rodando
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            response.raise_for_status()

            # Verificar se modelo está disponível
            models = response.json().get('models', [])
            model_names = [m['name'] for m in models]

            if self.model not in model_names:
                logger.warning(
                    f"Modelo '{self.model}' não encontrado. "
                    f"Execute: ollama pull {self.model}"
                )
                logger.info(f"Modelos disponíveis: {model_names}")
            else:
                logger.info(f"✓ Modelo '{self.model}' disponível")

        except requests.exceptions.ConnectionError:
            logger.error(
                f"Ollama não está rodando em {self.base_url}. "
                "Instale com: curl -fsSL https://ollama.com/install.sh | sh"
            )
            raise ConnectionError(f"Não foi possível conectar ao Ollama em {self.base_url}")
        except Exception as e:
            logger.warning(f"Erro ao verificar conexão com Ollama: {e}")

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

                # Chamar Ollama
                response = self._call_ollama(prompt)

                # Parse response
                enriched_data = self._parse_response(response)

                # Combinar com dados originais
                result = {**row, **enriched_data}
                return result

            except requests.exceptions.Timeout:
                logger.warning(
                    f"Tentativa {attempt + 1}/{self.max_retries} timeout "
                    f"para notícia {row.get('unique_id', 'unknown')}"
                )

                if attempt < self.max_retries - 1:
                    sleep_time = 1.0 * (2 ** attempt) + random.uniform(0, 0.5)
                    logger.info(f"Timeout: aguardando {sleep_time:.2f}s antes de retry")
                    time.sleep(sleep_time)
                else:
                    logger.error(f"Todas as tentativas falharam (timeout) para notícia {row.get('unique_id', 'unknown')}")
                    return self._create_fallback_result(row)

            except Exception as e:
                logger.warning(
                    f"Tentativa {attempt + 1}/{self.max_retries} falhou "
                    f"para notícia {row.get('unique_id', 'unknown')}: {e}"
                )

                if attempt < self.max_retries - 1:
                    sleep_time = 0.2 * (2 ** attempt)
                    time.sleep(sleep_time)
                else:
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

        # Limitar conteúdo
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

NOTÍCIA:
Título: {title}
Subtítulo: {subtitle}
Lead: {editorial_lead}
Conteúdo: {content_preview}

FORMATO DE SAÍDA (JSON VÁLIDO):
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
        return json.dumps(self.taxonomy, indent=2, ensure_ascii=False)

    def _call_ollama(self, prompt: str) -> str:
        """
        Realiza chamada ao Ollama.

        Args:
            prompt: Prompt para o modelo

        Returns:
            Resposta do modelo (texto)
        """
        url = f"{self.base_url}/api/generate"

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": self.temperature,
                "num_predict": 1000  # Limite de tokens
            }
        }

        response = requests.post(
            url,
            json=payload,
            timeout=self.timeout
        )
        response.raise_for_status()

        result = response.json()
        return result.get('response', '')

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
