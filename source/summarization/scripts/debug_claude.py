#!/usr/bin/env python3
"""
Debug da resposta do Claude
"""

import boto3
import json

def test_claude():
    client = boto3.client('bedrock-runtime', region_name='us-east-1')

    prompt = """Resuma esta notícia governamental brasileira em 3 sentenças concisas e informativas.

REQUISITOS:
- Capture os pontos principais e informações essenciais
- Use linguagem clara e objetiva
- Mantenha fidelidade aos fatos do texto original
- Não adicione informações externas
- Escreva em português brasileiro

NOTÍCIA:
O Ministério da Educação (MEC) está com inscrições abertas até o dia 13 de março para estados e municípios aderirem ao Compromisso Nacional Toda Matemática. O programa oferece apoio técnico e financeiro para fortalecer o ensino de matemática na educação básica. A adesão é voluntária e ocorre em duas etapas, sendo a primeira pela internet e a segunda presencialmente.

RESUMO:"""

    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 300,
        "temperature": 0.3,
        "messages": [
            {
                "role": "user",
                "content": prompt
            }
        ]
    }

    print("Enviando requisição para Claude Sonnet 4.6...")
    print(f"Model ID: us.anthropic.claude-sonnet-4-6")

    try:
        response = client.invoke_model(
            modelId="us.anthropic.claude-sonnet-4-6",
            body=json.dumps(body)
        )

        response_body = json.loads(response['body'].read())

        print("\n✅ Resposta recebida!")
        print(f"\nResponse completo:")
        print(json.dumps(response_body, indent=2, ensure_ascii=False))

        if 'content' in response_body and len(response_body['content']) > 0:
            summary = response_body['content'][0]['text']
            print(f"\n📝 Resumo extraído:")
            print(summary)
        else:
            print("\n⚠️  Nenhum conteúdo encontrado na resposta!")

    except Exception as e:
        print(f"\n❌ Erro: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_claude()
