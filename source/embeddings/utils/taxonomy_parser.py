"""
Parser para árvore de classificação hierárquica (3 níveis).

Lê arvore.yaml e constrói estrutura de categorias:
- Nível 1: Grandes áreas (25)
- Nível 2: Subcategorias
- Nível 3: Tópicos específicos
"""

import yaml
from pathlib import Path
from typing import Dict, List, Tuple


class TaxonomyParser:
    """Parser para taxonomia hierárquica."""

    def __init__(self, taxonomy_path: Path):
        """
        Inicializa parser.

        Args:
            taxonomy_path: Caminho para arvore.yaml
        """
        self.taxonomy_path = taxonomy_path
        self.taxonomy = self._load_taxonomy()
        self.flat_categories = self._flatten_taxonomy()

    def _load_taxonomy(self) -> Dict:
        """Carrega YAML com taxonomia."""
        with open(self.taxonomy_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    def _flatten_taxonomy(self) -> List[Dict]:
        """
        Converte taxonomia hierárquica em lista flat.

        Returns:
            Lista de dicts com:
                - level1: str (ex: "01 - Economia e Finanças")
                - level2: str (ex: "01.01 - Política Econômica")
                - level3: str (ex: "01.01.01 - Política Fiscal")
                - full_code: str (ex: "01.01.01")
                - full_name: str (ex: "Economia e Finanças > Política Econômica > Política Fiscal")
        """
        flat = []

        for level1_key, level1_value in self.taxonomy.items():
            level1_code = level1_key.split(' - ')[0]
            level1_name = level1_key.split(' - ')[1]

            if not isinstance(level1_value, dict):
                continue

            for level2_key, level2_value in level1_value.items():
                level2_code = level2_key.split(' - ')[0]
                level2_name = level2_key.split(' - ')[1]

                if not isinstance(level2_value, list):
                    continue

                for level3_item in level2_value:
                    level3_code = level3_item.split(' - ')[0]
                    level3_name = level3_item.split(' - ')[1]

                    flat.append({
                        'level1': level1_key,
                        'level1_code': level1_code,
                        'level1_name': level1_name,
                        'level2': level2_key,
                        'level2_code': level2_code,
                        'level2_name': level2_name,
                        'level3': level3_item,
                        'level3_code': level3_code,
                        'level3_name': level3_name,
                        'full_code': level3_code,
                        'full_name': f"{level1_name} > {level2_name} > {level3_name}"
                    })

        return flat

    def get_level1_categories(self) -> List[str]:
        """Retorna lista de categorias nível 1."""
        return list(set([c['level1'] for c in self.flat_categories]))

    def get_level2_categories(self, level1: str = None) -> List[str]:
        """
        Retorna lista de categorias nível 2.

        Args:
            level1: Filtrar por nível 1 (opcional)
        """
        if level1:
            return list(set([c['level2'] for c in self.flat_categories if c['level1'] == level1]))
        return list(set([c['level2'] for c in self.flat_categories]))

    def get_level3_categories(self, level1: str = None, level2: str = None) -> List[str]:
        """
        Retorna lista de categorias nível 3.

        Args:
            level1: Filtrar por nível 1 (opcional)
            level2: Filtrar por nível 2 (opcional)
        """
        filtered = self.flat_categories

        if level1:
            filtered = [c for c in filtered if c['level1'] == level1]

        if level2:
            filtered = [c for c in filtered if c['level2'] == level2]

        return [c['level3'] for c in filtered]

    def get_full_path(self, level3_code: str) -> Tuple[str, str, str]:
        """
        Retorna caminho completo dado um código nível 3.

        Args:
            level3_code: Código nível 3 (ex: "01.01.01")

        Returns:
            Tupla (level1, level2, level3)
        """
        for cat in self.flat_categories:
            if cat['level3_code'] == level3_code:
                return (cat['level1'], cat['level2'], cat['level3'])

        return (None, None, None)

    def format_for_prompt(self, level: int = 1) -> str:
        """
        Formata taxonomia para uso em prompts.

        Args:
            level: Nível de profundidade (1, 2 ou 3)

        Returns:
            String formatada para prompt
        """
        if level == 1:
            # Apenas nível 1
            cats = sorted(set([c['level1'] for c in self.flat_categories]))
            return '\n'.join([f"- {cat}" for cat in cats])

        elif level == 2:
            # Níveis 1 e 2
            output = []
            for cat in sorted(set([c['level1'] for c in self.flat_categories])):
                output.append(f"\n{cat}:")
                subcats = sorted(set([c['level2'] for c in self.flat_categories if c['level1'] == cat]))
                for subcat in subcats:
                    output.append(f"  - {subcat}")
            return '\n'.join(output)

        else:
            # Todos os 3 níveis (pode ficar muito grande para prompt!)
            output = []
            for cat in sorted(set([c['level1'] for c in self.flat_categories])):
                output.append(f"\n{cat}:")
                for subcat in sorted(set([c['level2'] for c in self.flat_categories if c['level1'] == cat])):
                    output.append(f"  {subcat}:")
                    topics = [c['level3'] for c in self.flat_categories if c['level2'] == subcat]
                    for topic in sorted(set(topics)):
                        output.append(f"    - {topic}")
            return '\n'.join(output)

    def get_stats(self) -> Dict:
        """Retorna estatísticas da taxonomia."""
        return {
            'total_level1': len(set([c['level1'] for c in self.flat_categories])),
            'total_level2': len(set([c['level2'] for c in self.flat_categories])),
            'total_level3': len(self.flat_categories),
        }


def main():
    """Teste do parser."""
    import sys
    base_dir = Path(__file__).parent.parent
    taxonomy_path = base_dir / "data" / "classification" / "arvore.yaml"

    parser = TaxonomyParser(taxonomy_path)

    print("="*80)
    print("TAXONOMIA - ESTATÍSTICAS")
    print("="*80)

    stats = parser.get_stats()
    print(f"\nNível 1 (Grandes áreas): {stats['total_level1']}")
    print(f"Nível 2 (Subcategorias): {stats['total_level2']}")
    print(f"Nível 3 (Tópicos): {stats['total_level3']}")

    print("\n" + "="*80)
    print("NÍVEL 1 - GRANDES ÁREAS")
    print("="*80)
    for cat in sorted(parser.get_level1_categories()):
        print(f"  {cat}")

    print("\n" + "="*80)
    print("EXEMPLO: Economia e Finanças (NÍVEL 2)")
    print("="*80)
    level2 = parser.get_level2_categories("01 - Economia e Finanças")
    for cat in sorted(level2):
        print(f"  {cat}")

    print("\n" + "="*80)
    print("EXEMPLO: Política Econômica (NÍVEL 3)")
    print("="*80)
    level3 = parser.get_level3_categories(
        level1="01 - Economia e Finanças",
        level2="01.01 - Política Econômica"
    )
    for cat in sorted(level3):
        print(f"  {cat}")


if __name__ == "__main__":
    main()
