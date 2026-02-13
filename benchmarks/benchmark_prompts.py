"""
Benchmark Completo: Cogfy vs Bedrock | Haiku vs Sonnet
========================================================

Compara 4 abordagens:
1. Prompt Cogfy (original) + Haiku
2. Prompt Cogfy (original) + Sonnet
3. Prompt Bedrock (atual) + Haiku
4. Prompt Bedrock (atual) + Sonnet

Usando as mesmas 10 notícias e a árvore temática como taxonomia balizadora.
"""

import yaml
import json
import time
import polars as pl
import pandas as pd
from datetime import datetime
from pathlib import Path
from news_enrichment import NewsDatasetManager
import boto3
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def carregar_taxonomia_yaml():
    """Carrega e formata a árvore temática do YAML."""
    print("\n" + "="*80)
    print("CARREGANDO TAXONOMIA")
    print("="*80 + "\n")

    with open("arvore.yaml", "r", encoding="utf-8") as f:
        taxonomia_raw = yaml.safe_load(f)

    # Formatar para uso no prompt
    taxonomia_texto = ""
    for nivel1_key, nivel1_data in taxonomia_raw.items():
        taxonomia_texto += f"\n{nivel1_key}\n"

        for nivel2_key, nivel2_data in nivel1_data.items():
            taxonomia_texto += f"  {nivel2_key}\n"

            if isinstance(nivel2_data, list):
                for nivel3 in nivel2_data:
                    taxonomia_texto += f"    {nivel3}\n"

    print(f"✓ Taxonomia carregada: {len(taxonomia_raw)} categorias principais")
    return taxonomia_texto


def filtrar_noticias_recentes(n=10):
    """Filtra as N notícias mais recentes com data válida."""
    print("\n" + "="*80)
    print("FILTRANDO NOTÍCIAS PARA TESTE")
    print("="*80 + "\n")

    dataset_manager = NewsDatasetManager(cache_dir="./data")
    df = dataset_manager.load_cached()

    # Filtrar apenas com data válida
    df = df.filter(pl.col('updated_datetime').is_not_null())

    # Ordenar por data (mais recente primeiro)
    df = df.sort('updated_datetime', descending=True)

    # Pegar as N mais recentes
    sample = df.head(n)

    print(f"✓ Selecionadas {len(sample)} notícias mais recentes")
    print(f"  Data mais recente: {sample['updated_datetime'].max()}")
    print(f"  Data mais antiga: {sample['updated_datetime'].min()}")

    return sample


class LLMClientCogfy:
    """Cliente com prompt estilo Cogfy (original) - separado em 2 chamadas."""

    def __init__(self, model_id, region, taxonomia_texto):
        self.model_id = model_id
        self.region = region
        self.taxonomia_texto = taxonomia_texto
        self.client = boto3.client('bedrock-runtime', region_name=region)

    def enrich_news(self, row):
        """Enriquece uma notícia com 2 chamadas separadas (classificação + resumo)."""
        try:
            # Chamada 1: Classificação
            classificacao = self._classify_news(row)

            time.sleep(0.3)  # Small delay entre chamadas

            # Chamada 2: Resumo
            resumo = self._summarize_news(row)

            # Combinar resultados
            result = {**row, **classificacao, 'summary': resumo}
            return result

        except Exception as e:
            logger.error(f"Erro ao processar notícia {row.get('unique_id')}: {e}")
            return self._create_fallback(row)

    def _classify_news(self, row):
        """Classificação temática (Prompt Cogfy)."""
        prompt = f"""Classifique a notícia abaixo em até 3 níveis temáticos, usando a taxonomia fornecida.

Taxonomia:
{self.taxonomia_texto}

Notícia:
Título: {row.get('title', '')}
Conteúdo: {row.get('content', '')[:2000]}

Responda no formato:
- Nível 1: XX - Nome
- Nível 2: XX.YY - Nome (se aplicável)
- Nível 3: XX.YY.ZZ - Nome (se aplicável)

Forneça APENAS a classificação nos 3 níveis, sem explicações adicionais."""

        response = self._call_bedrock(prompt)

        # Parse response (formato texto estruturado)
        return self._parse_classification_response(response)

    def _summarize_news(self, row):
        """Geração de resumo (Prompt Cogfy)."""
        prompt = f"""Gere um resumo conciso (2-3 frases) da notícia abaixo, destacando os pontos principais.

Título: {row.get('title', '')}
Conteúdo: {row.get('content', '')[:2000]}

Resumo:"""

        response = self._call_bedrock(prompt)
        return response.strip()

    def _call_bedrock(self, prompt):
        """Chama o Bedrock."""
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "temperature": 0.3,
            "messages": [{"role": "user", "content": prompt}]
        }

        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(request_body)
        )

        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text']

    def _parse_classification_response(self, response):
        """Parse resposta de classificação em formato texto."""
        import re

        result = {
            'theme_1_level_1': None,
            'theme_1_level_1_code': None,
            'theme_1_level_1_label': None,
            'theme_1_level_2_code': None,
            'theme_1_level_2_label': None,
            'theme_1_level_3_code': None,
            'theme_1_level_3_label': None,
            'most_specific_theme_code': None,
            'most_specific_theme_label': None
        }

        # Parse níveis
        nivel1_match = re.search(r'Nível 1:\s*(\d+)\s*-\s*(.+)', response)
        nivel2_match = re.search(r'Nível 2:\s*([\d.]+)\s*-\s*(.+)', response)
        nivel3_match = re.search(r'Nível 3:\s*([\d.]+)\s*-\s*(.+)', response)

        if nivel1_match:
            code, label = nivel1_match.groups()
            result['theme_1_level_1'] = label.strip()
            result['theme_1_level_1_code'] = code.strip()
            result['theme_1_level_1_label'] = label.strip()

        if nivel2_match:
            code, label = nivel2_match.groups()
            result['theme_1_level_2_code'] = code.strip()
            result['theme_1_level_2_label'] = label.strip()

        if nivel3_match:
            code, label = nivel3_match.groups()
            result['theme_1_level_3_code'] = code.strip()
            result['theme_1_level_3_label'] = label.strip()
            result['most_specific_theme_code'] = code.strip()
            result['most_specific_theme_label'] = label.strip()
        elif nivel2_match:
            result['most_specific_theme_code'] = result['theme_1_level_2_code']
            result['most_specific_theme_label'] = result['theme_1_level_2_label']
        elif nivel1_match:
            result['most_specific_theme_code'] = result['theme_1_level_1_code']
            result['most_specific_theme_label'] = result['theme_1_level_1_label']

        return result

    def _create_fallback(self, row):
        """Fallback para erros."""
        return {
            **row,
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


class LLMClientBedrock:
    """Cliente com prompt estilo Bedrock (atual) - 1 chamada JSON."""

    def __init__(self, model_id, region, taxonomia_texto):
        self.model_id = model_id
        self.region = region
        self.taxonomia_texto = taxonomia_texto
        self.client = boto3.client('bedrock-runtime', region_name=region)

    def enrich_news(self, row):
        """Enriquece uma notícia com 1 chamada (classificação + resumo em JSON)."""
        try:
            prompt = self._build_prompt(row)
            response = self._call_bedrock(prompt)
            enriched_data = self._parse_json_response(response)
            return {**row, **enriched_data}

        except Exception as e:
            logger.error(f"Erro ao processar notícia {row.get('unique_id')}: {e}")
            return self._create_fallback(row)

    def _build_prompt(self, row):
        """Prompt atual (Bedrock) - JSON estruturado."""
        title = row.get('title', '')
        subtitle = row.get('subtitle', '')
        editorial_lead = row.get('editorial_lead', '')
        content = row.get('content', '')[:2000]

        prompt = f"""Você é um especialista em classificação temática de notícias governamentais brasileiras.

Analise a notícia abaixo e retorne APENAS um JSON válido (sem markdown, sem explicações).

TAXONOMIA DISPONÍVEL:
{self.taxonomia_texto}

INSTRUÇÕES:
1. Classifique a notícia usando EXATAMENTE os códigos e labels da taxonomia fornecida
2. Use até 3 níveis hierárquicos (quando aplicável)
3. Gere um resumo conciso (máximo 2 frases) capturando os pontos principais

NOTÍCIA:
Título: {title}
Subtítulo: {subtitle}
Lead: {editorial_lead}
Conteúdo: {content}

FORMATO DE SAÍDA (JSON VÁLIDO):
{{
  "theme_1_level_1": "Economia e Finanças",
  "theme_1_level_1_code": "01",
  "theme_1_level_1_label": "Economia e Finanças",
  "theme_1_level_2_code": "01.02",
  "theme_1_level_2_label": "Fiscalização e Tributação",
  "theme_1_level_3_code": "01.02.03",
  "theme_1_level_3_label": "Combate à Evasão Fiscal",
  "most_specific_theme_code": "01.02.03",
  "most_specific_theme_label": "Combate à Evasão Fiscal",
  "summary": "Governo federal anuncia medidas para combater evasão fiscal. Iniciativa visa aumentar arrecadação e reduzir sonegação."
}}"""

        return prompt

    def _call_bedrock(self, prompt):
        """Chama o Bedrock."""
        request_body = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 1000,
            "temperature": 0.3,
            "messages": [{"role": "user", "content": prompt}]
        }

        response = self.client.invoke_model(
            modelId=self.model_id,
            body=json.dumps(request_body)
        )

        response_body = json.loads(response['body'].read())
        return response_body['content'][0]['text']

    def _parse_json_response(self, response):
        """Parse resposta JSON."""
        # Extrair JSON
        start_idx = response.find('{')
        end_idx = response.rfind('}') + 1

        if start_idx == -1 or end_idx <= start_idx:
            raise ValueError("JSON não encontrado na resposta")

        json_str = response[start_idx:end_idx]
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
                result[field] = None

        return result

    def _create_fallback(self, row):
        """Fallback para erros."""
        return {
            **row,
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


def testar_abordagem(nome, client, sample_df):
    """Testa uma abordagem (prompt + modelo)."""
    print("\n" + "="*80)
    print(f"TESTANDO: {nome}")
    print("="*80 + "\n")

    start_time = time.time()
    results = []

    rows = sample_df.to_dicts()

    for i, row in enumerate(rows, 1):
        print(f"Processando notícia {i}/{len(rows)}...")
        enriched = client.enrich_news(row)
        results.append(enriched)
        time.sleep(0.5)  # Rate limiting

    total_time = time.time() - start_time

    # Calcular sucesso
    success_count = sum(1 for r in results if r['most_specific_theme_label'] is not None)
    success_rate = success_count / len(results) * 100

    print(f"\n✓ Concluído em {total_time:.1f}s")
    print(f"✓ Taxa de sucesso: {success_count}/{len(results)} ({success_rate:.1f}%)")

    return {
        'nome': nome,
        'results': results,
        'total_time': total_time,
        'success_count': success_count,
        'success_rate': success_rate,
        'avg_time': total_time / len(results)
    }


def comparar_resultados(resultados):
    """Compara os 4 resultados."""
    print("\n" + "="*80)
    print("COMPARAÇÃO GERAL")
    print("="*80 + "\n")

    print(f"{'Abordagem':<40} {'Sucesso':<15} {'Tempo Total':<15} {'Tempo/Notícia':<15}")
    print("-" * 85)

    for res in resultados:
        print(f"{res['nome']:<40} "
              f"{res['success_count']}/{len(res['results'])} ({res['success_rate']:.0f}%)  "
              f"{res['total_time']:.1f}s          "
              f"{res['avg_time']:.2f}s")

    # Análise por notícia
    print("\n" + "="*80)
    print("COMPARAÇÃO POR NOTÍCIA (Primeiras 3)")
    print("="*80 + "\n")

    for i in range(min(3, len(resultados[0]['results']))):
        print(f"--- NOTÍCIA {i+1} ---")

        # Título
        title = resultados[0]['results'][i]['title']
        print(f"Título: {title[:80]}...")

        for res in resultados:
            noticia = res['results'][i]
            print(f"\n{res['nome']}:")
            print(f"  Tema: {noticia['most_specific_theme_label'] or '[FALHOU]'}")
            summary = noticia['summary'] or '[FALHOU]'
            print(f"  Resumo: {summary[:100] if len(str(summary)) > 100 else summary}...")

        print()


def main():
    """Executa benchmark completo."""
    print("\n" + "="*80)
    print("BENCHMARK: COGFY vs BEDROCK | HAIKU vs SONNET")
    print("="*80)
    print("\nComparando 4 abordagens:")
    print("1. Prompt Cogfy + Haiku")
    print("2. Prompt Cogfy + Sonnet")
    print("3. Prompt Bedrock (atual) + Haiku")
    print("4. Prompt Bedrock (atual) + Sonnet")
    print("\nUsando mesmas 10 notícias + taxonomia balizadora")

    # 1. Carregar taxonomia
    taxonomia_texto = carregar_taxonomia_yaml()

    # 2. Filtrar notícias
    sample = filtrar_noticias_recentes(n=10)

    # 3. Testar todas as abordagens
    resultados = []

    # Cogfy + Haiku
    client1 = LLMClientCogfy(
        model_id="anthropic.claude-3-haiku-20240307-v1:0",
        region="us-east-1",
        taxonomia_texto=taxonomia_texto
    )
    res1 = testar_abordagem("Cogfy + Haiku", client1, sample)
    resultados.append(res1)

    time.sleep(5)  # Delay entre testes

    # Cogfy + Sonnet
    client2 = LLMClientCogfy(
        model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
        region="us-east-1",
        taxonomia_texto=taxonomia_texto
    )
    res2 = testar_abordagem("Cogfy + Sonnet", client2, sample)
    resultados.append(res2)

    time.sleep(5)

    # Bedrock + Haiku
    client3 = LLMClientBedrock(
        model_id="anthropic.claude-3-haiku-20240307-v1:0",
        region="us-east-1",
        taxonomia_texto=taxonomia_texto
    )
    res3 = testar_abordagem("Bedrock + Haiku", client3, sample)
    resultados.append(res3)

    time.sleep(5)

    # Bedrock + Sonnet
    client4 = LLMClientBedrock(
        model_id="anthropic.claude-3-5-sonnet-20240620-v1:0",
        region="us-east-1",
        taxonomia_texto=taxonomia_texto
    )
    res4 = testar_abordagem("Bedrock + Sonnet", client4, sample)
    resultados.append(res4)

    # 4. Comparar resultados
    comparar_resultados(resultados)

    # 5. Salvar resultados
    print("\n" + "="*80)
    print("SALVANDO RESULTADOS")
    print("="*80 + "\n")

    # Combinar todos os resultados
    all_results = []
    for res in resultados:
        for r in res['results']:
            r['abordagem'] = res['nome']
            all_results.append(r)

    # Salvar parquet
    df_final = pl.DataFrame(all_results)
    output_path = "./data/benchmark_prompts_completo.parquet"
    df_final.write_parquet(output_path)
    print(f"✓ Parquet salvo: {output_path}")

    # Salvar CSV comparativo
    df_pandas = df_final.to_pandas()

    # Selecionar colunas relevantes
    cols_compare = [
        'unique_id', 'title', 'abordagem',
        'theme_1_level_1_label', 'theme_1_level_2_label', 'theme_1_level_3_label',
        'most_specific_theme_label', 'summary'
    ]

    csv_path = "./data/benchmark_prompts_comparativo.csv"
    df_pandas[cols_compare].to_csv(csv_path, index=False)
    print(f"✓ CSV salvo: {csv_path}")

    # Salvar metadados
    metadata = {
        'timestamp': datetime.now().isoformat(),
        'n_noticias': len(sample),
        'abordagens': [
            {
                'nome': res['nome'],
                'total_time': res['total_time'],
                'success_rate': res['success_rate']
            }
            for res in resultados
        ]
    }

    with open("./data/benchmark_prompts_metadata.json", "w") as f:
        json.dump(metadata, f, indent=2)
    print(f"✓ Metadados salvos: ./data/benchmark_prompts_metadata.json")

    print("\n" + "="*80)
    print("BENCHMARK CONCLUÍDO!")
    print("="*80 + "\n")


if __name__ == "__main__":
    main()
