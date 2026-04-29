"""Debug script to check agreement calculation."""

import sys
from pathlib import Path
import pandas as pd

BASE_DIR = Path(__file__).parent.parent
sys.path.insert(0, str(BASE_DIR.parent))

from embeddings.classifiers.bedrock_classifier_json import BedrockClassifierJSON

# Load sample
data_path = BASE_DIR / "data" / "classification" / "news_classification_test_annotated.csv"
df = pd.read_csv(data_path)

# Test first 3 news
for i in range(3):
    row = df.iloc[i]
    text = row['content']
    gt = row['category']

    print(f"\n{'='*80}")
    print(f"NOTÍCIA {i+1}")
    print(f"{'='*80}")
    print(f"Ground Truth: {gt}")
    print(f"Text: {text[:150]}...")
    print()

    # Classify
    classifier = BedrockClassifierJSON(
        model_id='anthropic.claude-3-sonnet-20240229-v1:0',
        model_name='Claude Sonnet',
        provider='anthropic',
        region='us-east-1'
    )

    result = classifier.classify(text)

    print(f"Prediction: {result['category']}")
    print(f"Success: {result['success']}")
    print()

    # Extract codes for comparison
    pred = result['category']

    # Extract L1, L2, L3 codes
    if ' - ' in pred:
        pred_code = pred.split(' - ')[0]
    else:
        pred_code = pred

    if ' - ' in gt:
        gt_code = gt.split(' - ')[0]
    else:
        gt_code = gt

    print(f"Predicted code: {pred_code}")
    print(f"GT code: {gt_code}")
    print()

    if '.' in pred_code:
        pred_l1 = pred_code.split('.')[0]
        pred_l2 = '.'.join(pred_code.split('.')[:2])
        pred_l3 = pred_code
    else:
        pred_l1 = pred_code
        pred_l2 = ''
        pred_l3 = ''

    if '.' in gt_code:
        gt_l1 = gt_code.split('.')[0]
        gt_l2 = '.'.join(gt_code.split('.')[:2])
        gt_l3 = gt_code
    else:
        gt_l1 = gt_code
        gt_l2 = ''
        gt_l3 = ''

    print(f"Predicted: L1={pred_l1}, L2={pred_l2}, L3={pred_l3}")
    print(f"GT:        L1={gt_l1}, L2={gt_l2}, L3={gt_l3}")
    print()
    print(f"L1 Match: {pred_l1 == gt_l1}")
    print(f"L2 Match: {pred_l2 == gt_l2}")
    print(f"L3 Match: {pred_l3 == gt_l3}")
