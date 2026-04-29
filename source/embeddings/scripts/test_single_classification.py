"""Quick test to debug classification issues."""

import sys
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR.parent))

from embeddings.classifiers.bedrock_classifier_json import BedrockClassifierJSON

# Load one news article
data_path = BASE_DIR / "data" / "classification" / "news_classification_test_annotated.csv"
df = pd.read_csv(data_path)

text = df.iloc[0]['content']
gt = df.iloc[0]['category']

print("Testing Claude Sonnet...")
print(f"Ground truth: {gt}")
print(f"Text (first 200 chars): {text[:200]}")
print()

# Test classifier
classifier = BedrockClassifierJSON(
    model_id='anthropic.claude-3-5-sonnet-20240620-v1:0',
    model_name='Claude Sonnet Test',
    provider='anthropic',
    region='us-east-1'
)

result = classifier.classify(text)

print("Result:")
print(f"  Success: {result['success']}")
print(f"  Category: {result['category']}")
print(f"  Latency: {result['latency']:.2f}s")
print(f"  Input tokens: {result['input_tokens']}")
print(f"  Output tokens: {result['output_tokens']}")

if not result['success']:
    print(f"\n❌ ERROR:")
    print(f"  Raw response: {result['raw_response']}")

if result['json_parsed']:
    print(f"\n✅ JSON parsed successfully:")
    import json
    print(json.dumps(result['json_parsed'], indent=2, ensure_ascii=False))
