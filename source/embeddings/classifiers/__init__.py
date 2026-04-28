"""
Classificadores LLM para Issue #3.

Suporta múltiplos modelos via AWS Bedrock.
"""

from .base import BaseClassifier
from .bedrock_classifier import BedrockClassifier

__all__ = ['BaseClassifier', 'BedrockClassifier']
