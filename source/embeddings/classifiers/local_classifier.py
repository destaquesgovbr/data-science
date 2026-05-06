"""
Classificador local usando modelos open source via Ollama.

Suporta qualquer modelo disponível no Ollama (Llama, Mistral, Qwen, Gemma, Phi, etc).
Reutiliza mesma interface BaseClassifier para compatibilidade com pipeline existente.
"""

import requests
import json
import time
from typing import Dict, Optional
from .base import BaseClassifier


class LocalClassifier(BaseClassifier):
    """Classificador local usando Ollama."""

    def __init__(
        self,
        model_id: str,
        model_name: str,
        ollama_host: str = "http://localhost:11434",
        taxonomy_path: str = None,
        timeout: int = 300
    ):
        """
        Inicializa classificador local.

        Args:
            model_id: ID do modelo no Ollama (ex: 'llama3.1:8b-instruct-q4_K_M')
            model_name: Nome amigável (ex: 'Llama 3.1 8B')
            ollama_host: URL do servidor Ollama
            taxonomy_path: Caminho para arvore.yaml
            timeout: Timeout em segundos
        """
        super().__init__(model_name, taxonomy_path)
        self.model_id = model_id
        self.ollama_host = ollama_host
        self.timeout = timeout

        # Verificar se modelo está disponível
        self._check_model_availability()

    def _check_model_availability(self):
        """Verifica se modelo está instalado no Ollama."""
        try:
            response = requests.get(
                f"{self.ollama_host}/api/tags",
                timeout=10
            )
            response.raise_for_status()

            models = response.json().get('models', [])
            model_names = [m['name'] for m in models]

            if self.model_id not in model_names:
                print(f"⚠️  Modelo '{self.model_id}' não encontrado no Ollama.")
                print(f"   Modelos disponíveis: {model_names}")
                print(f"\n   Para instalar: ollama pull {self.model_id}")
                raise ValueError(f"Modelo não disponível: {self.model_id}")

            print(f"✅ Modelo '{self.model_id}' encontrado no Ollama")

        except requests.exceptions.ConnectionError:
            raise ConnectionError(
                f"Não foi possível conectar ao Ollama em {self.ollama_host}. "
                "Certifique-se de que o Ollama está rodando."
            )

    def _build_prompt(self, text: str) -> str:
        """
        Constrói prompt JSON para o modelo.

        Reutiliza mesma estrutura dos experimentos API para comparabilidade.
        """
        from ..prompts.classification_prompts_json import get_prompt_json
        return get_prompt_json(text, self.taxonomy)

    def _call_ollama(self, prompt: str) -> tuple:
        """
        Chama API Ollama.

        Args:
            prompt: Prompt completo

        Returns:
            (response_text, input_tokens, output_tokens)
        """
        payload = {
            "model": self.model_id,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.3,
                "num_predict": 1000  # max_tokens
            }
        }

        response = requests.post(
            f"{self.ollama_host}/api/generate",
            json=payload,
            timeout=self.timeout
        )

        response.raise_for_status()
        result = response.json()

        # Extrair resposta
        response_text = result.get('response', '')

        # Extrair tokens (Ollama retorna contagens)
        input_tokens = result.get('prompt_eval_count', 0)
        output_tokens = result.get('eval_count', 0)

        return response_text, input_tokens, output_tokens

    def _call_ollama_raw(self, prompt: str) -> str:
        """
        Chama Ollama e retorna apenas o texto da resposta.

        Método simplificado para classificação hierárquica.

        Args:
            prompt: Prompt completo

        Returns:
            response_text: Texto da resposta
        """
        response_text, _, _ = self._call_ollama(prompt)
        return response_text

    def _parse_json_response(self, response: str) -> Optional[Dict]:
        """
        Extrai e valida JSON da resposta do modelo.

        Mesmo método usado em BedrockClassifierJSON para compatibilidade.
        """
        import re

        json_str = response

        # Remover markdown wrapper se existir
        if '```json' in json_str:
            start_marker = '```json'
            end_marker = '```'
            start_idx = json_str.find(start_marker) + len(start_marker)
            end_idx = json_str.find(end_marker, start_idx)
            if end_idx > start_idx:
                json_str = json_str[start_idx:end_idx].strip()
        elif '```' in json_str:
            json_str = re.sub(r'```[a-z]*\n', '', json_str)
            json_str = json_str.replace('```', '')

        # Extrair JSON puro
        start_idx = json_str.find('{')
        end_idx = json_str.rfind('}') + 1

        if start_idx == -1 or end_idx <= start_idx:
            return None

        json_str = json_str[start_idx:end_idx]

        try:
            result = json.loads(json_str)

            # Validar campos obrigatórios
            required_fields = [
                'theme_1_level_1_code',
                'theme_1_level_2_code',
                'theme_1_level_3_code',
                'most_specific_theme_code',
                'most_specific_theme_label'
            ]

            for field in required_fields:
                if field not in result or result[field] is None:
                    return None

            return result

        except json.JSONDecodeError:
            return None

    def classify(self, text: str, prompt_strategy: str = 'json') -> Dict:
        """
        Classifica texto usando modelo local.

        Args:
            text: Texto a classificar
            prompt_strategy: Ignorado (sempre usa JSON)

        Returns:
            Dict com resultado da classificação
        """
        # Construir prompt
        prompt = self._build_prompt(text)

        # Chamar Ollama
        start_time = time.time()
        try:
            response_text, input_tokens, output_tokens = self._call_ollama(prompt)

            # Parse JSON
            json_result = self._parse_json_response(response_text)

            if json_result is None:
                raise ValueError("Falha ao parsear JSON da resposta")

            # Extrair código e label mais específicos (nível 3)
            most_specific_code = json_result.get('most_specific_theme_code', '')
            most_specific_label = json_result.get('most_specific_theme_label', '')

            # Formato: "XX.XX.XX - Label"
            category_full = f"{most_specific_code} - {most_specific_label}"

            # Validar categoria usando método da base
            category = self._validate_category(category_full)

            latency = time.time() - start_time

            # Atualizar stats
            self.call_count += 1
            self.total_latency += latency
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens

            return {
                'category': category,
                'confidence': None,
                'latency': latency,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'raw_response': response_text,
                'json_parsed': json_result,
                'success': True,
            }

        except Exception as e:
            latency = time.time() - start_time
            error_msg = str(e)
            self.errors.append({
                'text_preview': text[:100],
                'error': error_msg,
                'latency': latency
            })

            print(f"  ❌ Erro ao classificar com {self.model_name}: {error_msg}")

            return {
                'category': '20.01.01 - Controle Interno',  # Fallback
                'confidence': None,
                'latency': latency,
                'input_tokens': 0,
                'output_tokens': 0,
                'raw_response': f"ERROR: {error_msg}",
                'json_parsed': None,
                'success': False,
            }

    def get_model_info(self) -> Dict:
        """
        Obtém informações do modelo (tamanho, parâmetros, etc).

        Returns:
            Dict com metadados do modelo
        """
        try:
            response = requests.post(
                f"{self.ollama_host}/api/show",
                json={"name": self.model_id},
                timeout=10
            )
            response.raise_for_status()
            return response.json()

        except Exception as e:
            print(f"⚠️  Não foi possível obter info do modelo: {e}")
            return {}
