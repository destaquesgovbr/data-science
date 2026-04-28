"""
Classe base abstrata para classificadores LLM.

Define interface comum para todos os modelos.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, List
import time
from pathlib import Path
import sys

# Importar TaxonomyParser
BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR.parent))
from embeddings.utils.taxonomy_parser import TaxonomyParser


class BaseClassifier(ABC):
    """Classe base para classificadores LLM."""

    def __init__(self, model_name: str, taxonomy_path: str = None):
        """
        Inicializa classificador.

        Args:
            model_name: Nome do modelo (ex: 'claude-sonnet-4-6')
            taxonomy_path: Caminho para arvore.yaml (opcional)
        """
        self.model_name = model_name

        # Carregar taxonomia
        if taxonomy_path is None:
            taxonomy_path = BASE_DIR / "data" / "classification" / "arvore.yaml"
        self.taxonomy = TaxonomyParser(taxonomy_path)

        # Categorias são nível 3 (tópicos específicos)
        self.categories = [cat['level3'] for cat in self.taxonomy.flat_categories]

        self.call_count = 0
        self.total_latency = 0.0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.errors = []

        # Pricing (deve ser configurado depois da inicialização)
        self.input_price_per_mtok = 0.0
        self.output_price_per_mtok = 0.0

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
        Valida e normaliza categoria predita contra taxonomia.

        Args:
            predicted: Categoria retornada pelo modelo (formato: "XX.XX.XX - Nome")

        Returns:
            Categoria normalizada (formato padronizado)
        """
        predicted = predicted.strip()

        # Tentar extrair código (ex: "01.01.01" de "01.01.01 - Política Fiscal")
        if ' - ' in predicted:
            code_part = predicted.split(' - ')[0].strip()
        else:
            code_part = predicted

        # Buscar na taxonomia por código exato
        for cat in self.taxonomy.flat_categories:
            if cat['level3_code'] == code_part:
                return cat['level3']  # Retorna formato completo: "XX.XX.XX - Nome"

        # Tentar match exato no formato completo
        for cat in self.taxonomy.flat_categories:
            if cat['level3'] == predicted:
                return cat['level3']

        # Tentar match case-insensitive
        predicted_lower = predicted.lower()
        for cat in self.taxonomy.flat_categories:
            if cat['level3'].lower() == predicted_lower:
                return cat['level3']

        # Tentar match parcial pelo nome (ignora código)
        for cat in self.taxonomy.flat_categories:
            cat_name = cat['level3_name'].lower()
            if cat_name in predicted_lower or predicted_lower in cat_name:
                return cat['level3']

        # Se nada bateu, tentar encontrar nível 1 ou 2 e retornar primeira opção daquela área
        for cat in self.taxonomy.flat_categories:
            if cat['level1_name'].lower() in predicted_lower:
                # Retorna primeiro tópico dessa grande área
                print(f"  ⚠️  Categoria inválida '{predicted}', inferindo '{cat['level3']}' (mesma grande área)")
                return cat['level3']

        # Último recurso: retorna primeiro tópico de "Políticas Públicas" (catch-all)
        fallback = [c for c in self.taxonomy.flat_categories if c['level1_code'] == '20'][0]
        print(f"  ⚠️  Categoria inválida '{predicted}', usando fallback: {fallback['level3']}")
        return fallback['level3']

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
        # Calcular custo
        input_cost = (self.total_input_tokens / 1_000_000) * self.input_price_per_mtok
        output_cost = (self.total_output_tokens / 1_000_000) * self.output_price_per_mtok
        total_cost = input_cost + output_cost

        return {
            'model_name': self.model_name,
            'total_calls': self.call_count,
            'total_latency': self.total_latency,
            'avg_latency': self.total_latency / self.call_count if self.call_count > 0 else 0,
            'total_input_tokens': self.total_input_tokens,
            'total_output_tokens': self.total_output_tokens,
            'total_cost': total_cost,
            'errors': self.errors,
        }

    def reset_stats(self):
        """Reseta estatísticas."""
        self.call_count = 0
        self.total_latency = 0.0
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.errors = []
