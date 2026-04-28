"""
Classificador Bedrock com saída JSON.

Baseado na implementação working de news-enrichment.
Retorna classificação em formato JSON estruturado com campos separados
para cada nível da hierarquia.
"""

import boto3
import json
import time
import re
from typing import Dict
from .base import BaseClassifier
from ..prompts.classification_prompts_json import get_prompt_json


class BedrockClassifierJSON(BaseClassifier):
    """Classificador Bedrock com resposta JSON estruturada."""

    def __init__(
        self,
        model_id: str,
        model_name: str,
        provider: str,
        region: str = 'us-east-1',
        taxonomy_path: str = None
    ):
        """
        Inicializa classificador Bedrock JSON.

        Args:
            model_id: ID do modelo no Bedrock
            model_name: Nome amigável
            provider: Provider do modelo ('anthropic', 'amazon', 'meta', etc.)
            region: Região AWS
            taxonomy_path: Caminho para arvore.yaml (opcional)
        """
        super().__init__(model_name, taxonomy_path)
        self.model_id = model_id
        self.provider = provider.lower()
        self.region = region
        self.client = boto3.client('bedrock-runtime', region_name=region)

    def _build_request_body(self, prompt: str) -> str:
        """Constrói body da request adaptado ao provider."""
        if self.provider == 'anthropic':
            # Claude usa Messages API
            body = {
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': 1000,  # JSON precisa de mais tokens
                'temperature': 0.3,  # Mesma temperatura do working
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ]
            }

        elif self.provider == 'amazon':
            # Nova usa formato próprio
            body = {
                'messages': [
                    {
                        'role': 'user',
                        'content': [{'text': prompt}]
                    }
                ],
                'inferenceConfig': {
                    'maxTokens': 1000,
                    'temperature': 0.3
                }
            }

        elif self.provider == 'mistral':
            # Mistral usa Messages API similar ao Claude
            body = {
                'messages': [
                    {
                        'role': 'user',
                        'content': prompt
                    }
                ],
                'max_tokens': 1000,
                'temperature': 0.3
            }

        elif self.provider in ['meta', 'qwen', 'deepseek', 'cohere', 'ai21']:
            # Formato genérico
            body = {
                'prompt': prompt,
                'max_tokens': 1000,
                'temperature': 0.3
            }

        else:
            # Fallback: formato genérico
            body = {
                'prompt': prompt,
                'max_tokens': 1000,
                'temperature': 0.3
            }

        return json.dumps(body)

    def _extract_response_text(self, response_body: dict) -> tuple:
        """
        Extrai texto da resposta adaptado ao provider.

        Returns:
            (response_text, input_tokens, output_tokens)
        """
        if self.provider == 'anthropic':
            text = response_body['content'][0]['text']
            input_tokens = response_body['usage']['input_tokens']
            output_tokens = response_body['usage']['output_tokens']

        elif self.provider == 'amazon':
            text = response_body['output']['message']['content'][0]['text']
            input_tokens = response_body['usage']['inputTokens']
            output_tokens = response_body['usage']['outputTokens']

        elif self.provider == 'meta':
            text = response_body.get('generation', response_body.get('outputs', [{}])[0].get('text', ''))
            input_tokens = response_body.get('prompt_token_count', 0)
            output_tokens = response_body.get('generation_token_count', 0)

        elif self.provider == 'mistral':
            # Mistral com Messages API (similar ao Claude)
            if 'choices' in response_body:
                text = response_body['choices'][0]['message']['content']
                input_tokens = response_body.get('usage', {}).get('prompt_tokens', 0)
                output_tokens = response_body.get('usage', {}).get('completion_tokens', 0)
            else:
                # Fallback para formato antigo
                text = response_body['outputs'][0]['text']
                input_tokens = response_body.get('num_tokens_from_prompt', 0)
                output_tokens = response_body.get('num_tokens_from_completion', 0)

        elif self.provider == 'cohere':
            text = response_body['generations'][0]['text']
            input_tokens = response_body.get('prompt_token_count', 0)
            output_tokens = response_body.get('generation_token_count', 0)

        else:
            # Fallback: tenta campos genéricos
            text = (
                response_body.get('completion', '') or
                response_body.get('text', '') or
                response_body.get('output', '') or
                str(response_body)
            )
            input_tokens = 0
            output_tokens = 0

        return text, input_tokens, output_tokens

    def _parse_json_response(self, response: str) -> Dict:
        """
        Extrai e valida JSON da resposta do LLM.

        Similar a news_enrichment/llm_client.py:_parse_response()

        Args:
            response: Resposta do modelo

        Returns:
            Dict com campos do JSON ou None se falhou
        """
        # Tentar extrair JSON (remove markdown se houver)
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
            # Remove qualquer markdown block
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
        Classifica texto usando Bedrock com resposta JSON.

        Args:
            text: Texto a classificar
            prompt_strategy: Ignorado (sempre usa JSON)

        Returns:
            Dict com resultado da classificação
        """
        # Construir prompt JSON (passa taxonomia)
        prompt = get_prompt_json(text, self.taxonomy)

        # Construir body da request
        request_body = self._build_request_body(prompt)

        # Chamar Bedrock
        start_time = time.time()
        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=request_body
            )

            # Parse response
            response_body = json.loads(response['body'].read())

            # Extrair texto e tokens
            response_text, input_tokens, output_tokens = self._extract_response_text(response_body)

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
                'json_parsed': json_result,  # Incluir JSON completo para debug
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
