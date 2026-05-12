"""
Sumarizadores Abstractive usando LLMs via AWS Bedrock
Fase 3: Geração de resumos com modelos de linguagem
"""

from summarizers import BaseSummarizer
import boto3
import json
import time
from typing import Dict, Any, Optional


class BedrockAbstractiveSummarizer(BaseSummarizer):
    """
    Sumarizador abstractive usando AWS Bedrock
    Suporta múltiplos modelos (Claude, Nova, Llama, etc)
    """

    def __init__(
        self,
        model_id: str,
        model_name: str = None,
        region: str = "us-east-1",
        max_tokens: int = 300,
        temperature: float = 0.3
    ):
        """
        Args:
            model_id: ID do modelo no Bedrock (ex: anthropic.claude-sonnet-4-6)
            model_name: Nome amigável para exibição (opcional)
            region: Região AWS
            max_tokens: Tokens máximos no resumo
            temperature: Temperatura (0.0-1.0, menor = mais determinístico)
        """
        name = model_name or model_id.split('.')[-1].replace('-', ' ').title()
        super().__init__(name)
        self.model_id = model_id
        self.region = region
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.client = boto3.client('bedrock-runtime', region_name=region)

    def _build_prompt(self, text: str, target_sentences: int = 3) -> str:
        """
        Constrói prompt otimizado para sumarização

        Args:
            text: Texto completo
            target_sentences: Número alvo de sentenças (orientativo)
        """
        prompt = f"""Resuma esta notícia governamental brasileira em {target_sentences} sentenças concisas e informativas.

REQUISITOS:
- Capture os pontos principais e informações essenciais
- Use linguagem clara e objetiva
- Mantenha fidelidade aos fatos do texto original
- Não adicione informações externas
- Escreva em português brasileiro

NOTÍCIA:
{text}

RESUMO:"""
        return prompt

    def _invoke_claude(self, prompt: str) -> str:
        """Invoca modelos Claude (Anthropic)"""
        body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        }

        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(body)
        )

        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text'].strip()

    def _invoke_nova(self, prompt: str) -> str:
        """Invoca modelos Amazon Nova"""
        body = {
            "messages": [
                {
                    "role": "user",
                    "content": [{"text": prompt}]
                }
            ],
            "inferenceConfig": {
                "max_new_tokens": self.max_tokens,
                "temperature": self.temperature
            }
        }

        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(body)
        )

        response_body = json.loads(response['body'].read())
        return response_body['output']['message']['content'][0]['text'].strip()

    def _invoke_llama(self, prompt: str) -> str:
        """Invoca modelos Meta Llama"""
        body = {
            "prompt": prompt,
            "max_gen_len": self.max_tokens,
            "temperature": self.temperature,
            "top_p": 0.9
        }

        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(body)
        )

        response_body = json.loads(response['body'].read())
        return response_body['generation'].strip()

    def _invoke_mistral(self, prompt: str) -> str:
        """Invoca modelos Mistral"""
        body = {
            "prompt": f"<s>[INST] {prompt} [/INST]",
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "top_p": 0.9
        }

        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(body)
        )

        response_body = json.loads(response['body'].read())
        return response_body['outputs'][0]['text'].strip()

    def _invoke_deepseek(self, prompt: str) -> str:
        """Invoca modelos DeepSeek"""
        body = {
            "messages": [
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature
        }

        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(body)
        )

        response_body = json.loads(response['body'].read())
        return response_body['choices'][0]['message']['content'].strip()

    def _invoke_model(self, prompt: str) -> str:
        """
        Detecta provider e invoca modelo apropriado
        """
        # Remove prefixo de região (us., global., etc)
        model_parts = self.model_id.split('.')
        if len(model_parts) > 2 and model_parts[0] in ['us', 'global']:
            provider = model_parts[1]
        else:
            provider = model_parts[0]

        if provider == 'anthropic':
            return self._invoke_claude(prompt)
        elif provider == 'amazon':
            return self._invoke_nova(prompt)
        elif provider == 'meta':
            return self._invoke_llama(prompt)
        elif provider == 'mistral':
            return self._invoke_mistral(prompt)
        elif provider == 'deepseek':
            return self._invoke_deepseek(prompt)
        else:
            raise ValueError(f"Provider não suportado: {provider}")

    def summarize(
        self,
        text: str,
        target_sentences: int = 3,
        **kwargs
    ) -> str:
        """
        Gera resumo abstractive usando LLM

        Args:
            text: Texto completo
            target_sentences: Número alvo de sentenças

        Returns:
            Resumo gerado pelo LLM
        """
        # Construir prompt
        prompt = self._build_prompt(text, target_sentences)

        # Invocar modelo
        summary = self._invoke_model(prompt)

        return summary


class ClaudeSonnet4Summarizer(BedrockAbstractiveSummarizer):
    """Claude Sonnet 4.6 - Melhor custo-benefício"""
    def __init__(self):
        super().__init__(
            model_id="us.anthropic.claude-sonnet-4-6",
            model_name="Claude Sonnet 4.6"
        )


class ClaudeOpus4Summarizer(BedrockAbstractiveSummarizer):
    """Claude Opus 4.7 - Máxima qualidade"""
    def __init__(self):
        super().__init__(
            model_id="us.anthropic.claude-opus-4-7",
            model_name="Claude Opus 4.7"
        )


class NovaPremiererSummarizer(BedrockAbstractiveSummarizer):
    """Amazon Nova Premier - Flagship AWS"""
    def __init__(self):
        super().__init__(
            model_id="us.amazon.nova-premier-v1:0",
            model_name="Amazon Nova Premier"
        )


class ClaudeHaiku4Summarizer(BedrockAbstractiveSummarizer):
    """Claude Haiku 4.5 - Rápido e eficiente"""
    def __init__(self):
        super().__init__(
            model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
            model_name="Claude Haiku 4.5"
        )


class Nova2LiteSummarizer(BedrockAbstractiveSummarizer):
    """Amazon Nova 2 Lite - Leve e rápido"""
    def __init__(self):
        super().__init__(
            model_id="us.amazon.nova-2-lite-v1:0",
            model_name="Amazon Nova 2 Lite"
        )


class Llama4MaverickSummarizer(BedrockAbstractiveSummarizer):
    """Llama 4 Maverick 17B - Open-weights"""
    def __init__(self):
        super().__init__(
            model_id="us.meta.llama4-maverick-17b-instruct-v1:0",
            model_name="Llama 4 Maverick 17B"
        )


class DeepSeekR1Summarizer(BedrockAbstractiveSummarizer):
    """DeepSeek-R1 - Raciocínio avançado"""
    def __init__(self):
        super().__init__(
            model_id="us.deepseek.r1-v1:0",
            model_name="DeepSeek-R1"
        )


class MistralLarge3Summarizer(BedrockAbstractiveSummarizer):
    """Mistral Large 3 - 675B parâmetros"""
    def __init__(self):
        super().__init__(
            model_id="mistral.mistral-large-3-675b-instruct",
            model_name="Mistral Large 3"
        )


class Llama33Summarizer(BedrockAbstractiveSummarizer):
    """Llama 3.3 70B - Baseline comprovado"""
    def __init__(self):
        super().__init__(
            model_id="us.meta.llama3-3-70b-instruct-v1:0",
            model_name="Llama 3.3 70B"
        )
