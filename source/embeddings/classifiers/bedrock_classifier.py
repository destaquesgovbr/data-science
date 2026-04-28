"""
Classificador universal para AWS Bedrock.

Suporta múltiplos providers:
- Anthropic (Claude)
- Amazon (Nova)
- Meta (Llama)
- Mistral
- Cohere
- Qwen, DeepSeek, etc.
"""

import boto3
import json
import time
from typing import Dict
from .base import BaseClassifier
from ..prompts.classification_prompts import get_prompt


class BedrockClassifier(BaseClassifier):
    """Classificador usando AWS Bedrock."""

    def __init__(
        self,
        model_id: str,
        model_name: str,
        provider: str,
        categories: list,
        region: str = 'us-east-1'
    ):
        """
        Inicializa classificador Bedrock.

        Args:
            model_id: ID do modelo no Bedrock (ex: 'anthropic.claude-sonnet-4-6')
            model_name: Nome amigável (ex: 'Claude Sonnet 4.6')
            provider: Provider do modelo ('anthropic', 'amazon', 'meta', etc.)
            categories: Lista de categorias válidas
            region: Região AWS
        """
        super().__init__(model_name, categories)
        self.model_id = model_id
        self.provider = provider.lower()
        self.region = region
        self.client = boto3.client('bedrock-runtime', region_name=region)

    def _build_request_body(self, prompt: str) -> str:
        """
        Constrói body da request adaptado ao provider.

        Cada provider tem formato diferente.
        """
        if self.provider == 'anthropic':
            # Claude usa Messages API
            body = {
                'anthropic_version': 'bedrock-2023-05-31',
                'max_tokens': 100,
                'temperature': 0,
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
                    'maxTokens': 100,
                    'temperature': 0
                }
            }

        elif self.provider in ['meta', 'mistral', 'qwen', 'deepseek', 'cohere', 'ai21']:
            # Formato genérico (funciona para maioria)
            body = {
                'prompt': prompt,
                'max_tokens': 100,
                'temperature': 0
            }

        elif self.provider == 'google':
            # Gemma via Bedrock
            body = {
                'prompt': prompt,
                'max_gen_len': 100,
                'temperature': 0
            }

        else:
            # Fallback: formato genérico
            body = {
                'prompt': prompt,
                'max_tokens': 100,
                'temperature': 0
            }

        return json.dumps(body)

    def _extract_response_text(self, response_body: dict) -> tuple:
        """
        Extrai texto da resposta adaptado ao provider.

        Returns:
            (response_text, input_tokens, output_tokens)
        """
        if self.provider == 'anthropic':
            # Claude
            text = response_body['content'][0]['text']
            input_tokens = response_body['usage']['input_tokens']
            output_tokens = response_body['usage']['output_tokens']

        elif self.provider == 'amazon':
            # Nova
            text = response_body['output']['message']['content'][0]['text']
            input_tokens = response_body['usage']['inputTokens']
            output_tokens = response_body['usage']['outputTokens']

        elif self.provider == 'meta':
            # Llama
            text = response_body.get('generation', response_body.get('outputs', [{}])[0].get('text', ''))
            input_tokens = response_body.get('prompt_token_count', 0)
            output_tokens = response_body.get('generation_token_count', 0)

        elif self.provider == 'mistral':
            # Mistral
            text = response_body['outputs'][0]['text']
            input_tokens = response_body.get('num_tokens_from_prompt', 0)
            output_tokens = response_body.get('num_tokens_from_completion', 0)

        elif self.provider == 'cohere':
            # Cohere
            text = response_body['generations'][0]['text']
            input_tokens = response_body.get('prompt_token_count', 0)
            output_tokens = response_body.get('generation_token_count', 0)

        elif self.provider == 'qwen':
            # Qwen
            text = response_body.get('output', {}).get('text', response_body.get('text', ''))
            input_tokens = response_body.get('usage', {}).get('input_tokens', 0)
            output_tokens = response_body.get('usage', {}).get('output_tokens', 0)

        elif self.provider == 'deepseek':
            # DeepSeek
            text = response_body.get('text', response_body.get('output', ''))
            input_tokens = response_body.get('usage', {}).get('prompt_tokens', 0)
            output_tokens = response_body.get('usage', {}).get('completion_tokens', 0)

        elif self.provider == 'google':
            # Gemma
            text = response_body.get('generation', '')
            input_tokens = response_body.get('prompt_token_count', 0)
            output_tokens = response_body.get('generation_token_count', 0)

        elif self.provider == 'ai21':
            # Jamba
            text = response_body['completions'][0]['data']['text']
            input_tokens = response_body.get('prompt', {}).get('tokens', [])
            input_tokens = len(input_tokens) if isinstance(input_tokens, list) else 0
            output_tokens = len(response_body['completions'][0]['data'].get('tokens', []))

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

    def classify(self, text: str, prompt_strategy: str = 'zero-shot') -> Dict:
        """
        Classifica texto usando Bedrock.

        Args:
            text: Texto a classificar
            prompt_strategy: 'zero-shot', 'few-shot', ou 'chain-of-thought'

        Returns:
            Dict com resultado da classificação
        """
        # Construir prompt
        prompt = get_prompt(text, self.categories, prompt_strategy)

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

            # Extrair categoria
            category = self._extract_category_from_response(response_text)

            latency = time.time() - start_time

            # Atualizar stats
            self.call_count += 1
            self.total_latency += latency
            self.total_input_tokens += input_tokens
            self.total_output_tokens += output_tokens

            return {
                'category': category,
                'confidence': None,  # Bedrock geralmente não retorna confidence
                'latency': latency,
                'input_tokens': input_tokens,
                'output_tokens': output_tokens,
                'raw_response': response_text,
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
                'category': 'Outros',  # Fallback
                'confidence': None,
                'latency': latency,
                'input_tokens': 0,
                'output_tokens': 0,
                'raw_response': f"ERROR: {error_msg}",
                'success': False,
            }
