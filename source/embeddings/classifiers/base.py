"""
Classe base abstrata para classificadores LLM.

Define interface comum para todos os modelos.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, List
import time


class BaseClassifier(ABC):
    """Classe base para classificadores LLM."""

    def __init__(self, model_name: str, categories: List[str]):
        """
        Inicializa classificador.

        Args:
            model_name: Nome do modelo (ex: 'claude-sonnet-4-6')
            categories: Lista de categorias válidas
        """
        self.model_name = model_name
        self.categories = categories
        self.call_count = 0
        self.total_latency = 0.0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.errors = []

    @abstractmethod
    def classify(self, text: str, prompt_strategy: str = 'zero-shot') -> Dict:
        """
        Classifica texto em uma categoria.

        Args:
            text: Texto a classificar
            prompt_strategy: 'zero-shot', 'few-shot', ou 'chain-of-thought'

        Returns:
            Dict com:
                - category: str (categoria predita)
                - confidence: float (se disponível)
                - latency: float (segundos)
                - input_tokens: int
                - output_tokens: int
                - raw_response: str (resposta bruta do modelo)
        """
        pass

    def _validate_category(self, predicted: str) -> str:
        """
        Valida e normaliza categoria predita.

        Args:
            predicted: Categoria retornada pelo modelo

        Returns:
            Categoria normalizada ou 'Outros' se inválida
        """
        predicted = predicted.strip()

        # Exact match
        if predicted in self.categories:
            return predicted

        # Case-insensitive match
        predicted_lower = predicted.lower()
        for cat in self.categories:
            if cat.lower() == predicted_lower:
                return cat

        # Partial match (categoria está contida na resposta)
        for cat in self.categories:
            if cat.lower() in predicted_lower:
                return cat

        # Se nada bateu, retorna 'Outros' ou primeira categoria
        print(f"  ⚠️  Categoria inválida '{predicted}', usando 'Outros'")
        return 'Outros' if 'Outros' in self.categories else self.categories[0]

    def _extract_category_from_response(self, response: str) -> str:
        """
        Extrai categoria da resposta do modelo.

        Lida com respostas que incluem explicação ou formatação.

        Args:
            response: Resposta bruta do modelo

        Returns:
            Categoria extraída
        """
        response = response.strip()

        # Se resposta é curta (<=50 chars), provavelmente é só a categoria
        if len(response) <= 50:
            return self._validate_category(response)

        # Tenta extrair de linhas com "Categoria:"
        for line in response.split('\n'):
            if 'categoria:' in line.lower():
                category = line.split(':', 1)[1].strip()
                return self._validate_category(category)

        # Tenta extrair primeira linha
        first_line = response.split('\n')[0].strip()
        if len(first_line) <= 50:
            return self._validate_category(first_line)

        # Última tentativa: procura categoria na resposta inteira
        for cat in self.categories:
            if cat.lower() in response.lower():
                return cat

        # Se tudo falhou, retorna resposta bruta e deixa validação lidar
        return self._validate_category(response)

    def get_stats(self) -> Dict:
        """
        Retorna estatísticas agregadas do classificador.

        Returns:
            Dict com métricas de uso
        """
        return {
            'model_name': self.model_name,
            'total_calls': self.call_count,
            'total_latency': self.total_latency,
            'avg_latency': self.total_latency / self.call_count if self.call_count > 0 else 0,
            'total_input_tokens': self.total_input_tokens,
            'total_output_tokens': self.total_output_tokens,
            'total_errors': len(self.errors),
        }

    def reset_stats(self):
        """Reseta estatísticas."""
        self.call_count = 0
        self.total_latency = 0.0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.errors = []
