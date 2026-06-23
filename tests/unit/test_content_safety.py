"""
Testes unitários para Content Safety Guardrails.

Testa as funções de moderação de conteúdo implementadas em llm_client.py.
"""

import json
from unittest.mock import Mock, patch

import pytest

from news_enrichment.llm_client import (
    check_content_safety_regex,
    check_summary_safety,
    verify_with_llm,
)


class TestCheckContentSafetyRegex:
    """Testes para verificação de segurança com regex."""

    def test_clean_summary_passes(self):
        """Resumo limpo deve passar."""
        summary = "Ministério da Saúde anuncia novo programa de vacinação para idosos."
        is_safe, reason = check_content_safety_regex(summary)
        assert is_safe is True
        assert reason is None

    def test_cpf_pattern_blocked(self):
        """CPF deve ser bloqueado."""
        summary = "Contato: 123.456.789-00"
        is_safe, reason = check_content_safety_regex(summary)
        assert is_safe is False
        assert "CPF" in reason

    def test_phone_pattern_blocked(self):
        """Telefone deve ser bloqueado."""
        summary = "Ligue para (11) 98765-4321"
        is_safe, reason = check_content_safety_regex(summary)
        assert is_safe is False
        assert "Telefone" in reason

    def test_phone_without_formatting_blocked(self):
        """Telefone sem formatação também deve ser bloqueado."""
        summary = "Contato: (11)987654321"
        is_safe, reason = check_content_safety_regex(summary)
        assert is_safe is False
        assert "Telefone" in reason

    def test_email_blocked(self):
        """Email deve ser bloqueado."""
        summary = "Entre em contato: joao.silva@exemplo.com.br"
        is_safe, reason = check_content_safety_regex(summary)
        assert is_safe is False
        assert "Email" in reason

    def test_rg_pattern_blocked(self):
        """RG deve ser bloqueado."""
        summary = "RG: 12.345.678-9"
        is_safe, reason = check_content_safety_regex(summary)
        assert is_safe is False
        assert "RG" in reason

    def test_offensive_word_blocked(self):
        """Palavras ofensivas devem ser bloqueadas."""
        summary = "Esse político é um idiota incompetente."
        is_safe, reason = check_content_safety_regex(summary)
        assert is_safe is False
        assert "ofensiva" in reason.lower()

    def test_offensive_word_case_insensitive(self):
        """Palavras ofensivas devem ser detectadas independente de case."""
        summary = "Esse político é um IDIOTA incompetente."
        is_safe, reason = check_content_safety_regex(summary)
        assert is_safe is False
        assert "ofensiva" in reason.lower()

    def test_word_boundary_prevents_false_positive(self):
        """Substring em palavra legítima não deve ser bloqueada."""
        # "estudo" contém "estúpido" como substring, mas não deve bloquear
        summary = "Novo estudo sobre educação será publicado."
        is_safe, reason = check_content_safety_regex(summary)
        # Este teste pode falhar se o regex não usar word boundaries
        # Se falhar, é indicação de que precisa melhorar o regex
        assert is_safe is True


class TestVerifyWithLLM:
    """Testes para verificação com LLM."""

    @patch("news_enrichment.llm_client.time.sleep")
    def test_safe_content_passes(self, mock_sleep):
        """Conteúdo seguro deve passar na verificação LLM."""
        mock_bedrock = Mock()
        mock_bedrock.invoke_model.return_value = {
            "body": Mock(
                read=lambda: json.dumps({
                    "content": [{"text": "SAFE"}]
                }).encode()
            )
        }

        is_safe, reason = verify_with_llm(
            "Ministério anuncia programa social.",
            mock_bedrock,
            model_id="test-model"
        )

        assert is_safe is True
        assert reason is None
        mock_bedrock.invoke_model.assert_called_once()

    @patch("news_enrichment.llm_client.time.sleep")
    def test_unsafe_content_blocked(self, mock_sleep):
        """Conteúdo inseguro deve ser bloqueado."""
        mock_bedrock = Mock()
        mock_bedrock.invoke_model.return_value = {
            "body": Mock(
                read=lambda: json.dumps({
                    "content": [{"text": "UNSAFE: Discurso de ódio detectado"}]
                }).encode()
            )
        }

        is_safe, reason = verify_with_llm(
            "Texto com discurso de ódio...",
            mock_bedrock,
            model_id="test-model"
        )

        assert is_safe is False
        assert "Discurso de ódio" in reason

    @patch("news_enrichment.llm_client.time.sleep")
    def test_llm_error_fails_safe(self, mock_sleep):
        """Erro no LLM deve bloquear por segurança (fail-safe)."""
        from botocore.exceptions import ClientError

        mock_bedrock = Mock()
        mock_bedrock.invoke_model.side_effect = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate limit"}},
            "InvokeModel"
        )

        is_safe, reason = verify_with_llm(
            "Algum texto...",
            mock_bedrock,
            model_id="test-model",
            max_retries=2
        )

        assert is_safe is False
        assert "Erro na verificação" in reason
        # Verifica que tentou 2 vezes antes de desistir
        assert mock_bedrock.invoke_model.call_count == 2


class TestCheckSummarySafety:
    """Testes para pipeline completo de verificação."""

    def test_clean_summary_passes_pipeline(self):
        """Resumo limpo deve passar por todo o pipeline."""
        mock_bedrock = Mock()
        summary = "Governo anuncia investimento em infraestrutura."

        is_safe, reason = check_summary_safety(summary, mock_bedrock)

        assert is_safe is True
        assert reason is None
        # Não deve chamar LLM para resumo limpo sem keywords suspeitas
        mock_bedrock.invoke_model.assert_not_called()

    def test_pii_blocked_by_regex(self):
        """PII deve ser bloqueado na fase de regex."""
        mock_bedrock = Mock()
        summary = "Contato do responsável: (11) 98765-4321"

        is_safe, reason = check_summary_safety(summary, mock_bedrock)

        assert is_safe is False
        assert reason.startswith("regex:")
        assert "Telefone" in reason
        # Não deve chamar LLM se regex já bloqueou
        mock_bedrock.invoke_model.assert_not_called()

    @patch("news_enrichment.llm_client.verify_with_llm")
    def test_suspicious_content_triggers_llm(self, mock_verify):
        """Conteúdo com keywords suspeitas deve acionar verificação LLM."""
        mock_bedrock = Mock()
        mock_verify.return_value = (True, None)

        summary = "Ministro envolve em polêmica sobre corrupção."

        is_safe, reason = check_summary_safety(summary, mock_bedrock)

        # Deve ter chamado LLM por causa de "polêmica" e "corrupção"
        mock_verify.assert_called_once()
        assert is_safe is True

    @patch("news_enrichment.llm_client.verify_with_llm")
    def test_suspicious_blocked_by_llm(self, mock_verify):
        """Conteúdo suspeito deve ser bloqueado pelo LLM."""
        mock_bedrock = Mock()
        mock_verify.return_value = (False, "Discurso de ódio detectado")

        summary = "Presidente acusado de criar polêmica racista."

        is_safe, reason = check_summary_safety(summary, mock_bedrock)

        assert is_safe is False
        assert reason.startswith("llm:")
        assert "Discurso de ódio" in reason

    def test_multiple_pii_types(self):
        """Deve detectar primeiro tipo de PII encontrado."""
        mock_bedrock = Mock()
        summary = "CPF 123.456.789-00 e telefone (11) 98765-4321"

        is_safe, reason = check_summary_safety(summary, mock_bedrock)

        assert is_safe is False
        # Deve bloquear pelo primeiro padrão encontrado (CPF)
        assert "regex:" in reason


class TestSuspiciousKeywords:
    """Testes para detecção de keywords suspeitas."""

    @pytest.mark.parametrize("keyword", [
        "polêmica", "polemica", "conflito", "disputa", "confronto",
        "acusação", "acusacao", "denúncia", "denuncia",
        "escândalo", "escandalo", "corrupção", "corrupcao",
        "investigação", "investigacao", "operação", "operacao",
        "prisão", "prisao", "detenção", "detencao"
    ])
    @patch("news_enrichment.llm_client.verify_with_llm")
    def test_keyword_triggers_llm_verification(self, mock_verify, keyword):
        """Cada keyword suspeita deve acionar verificação LLM."""
        mock_verify.return_value = (True, None)
        mock_bedrock = Mock()

        summary = f"Ministro envolvido em {keyword} recente."

        check_summary_safety(summary, mock_bedrock)

        # Deve ter chamado LLM por causa da keyword
        mock_verify.assert_called_once()
