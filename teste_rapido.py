"""Teste rápido do NewsClassifier"""
from news_enrichment import NewsClassifier
import json

# Inicializar classificador (usa AWS Bedrock)
classifier = NewsClassifier(
    model_id="anthropic.claude-3-haiku-20240307-v1:0",
    region="us-east-1"
)

# Notícia de teste
news = {
    "title": "Governo anuncia reforma tributária para simplificar impostos",
    "content": "O Ministério da Fazenda apresentou hoje uma proposta de reforma tributária que visa simplificar o sistema de impostos brasileiro, unificando tributos federais, estaduais e municipais."
}

# Classificar
print("Classificando notícia...")
result = classifier.classify_single(news)

# Mostrar resultado
print("\n" + "="*60)
print("RESULTADO:")
print("="*60)
print(result)
