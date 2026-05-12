"""
Sumarizadores Abstractive V2 - Com Prompt Otimizado (Few-Shot)
Fase 3B: Prompt Engineering para melhorar qualidade
"""

from summarizers_abstractive import BedrockAbstractiveSummarizer


class BedrockAbstractiveSummarizerV2(BedrockAbstractiveSummarizer):
    """
    Versão V2 com prompt otimizado usando few-shot learning
    """

    def _build_prompt(self, text: str, target_sentences: int = 3) -> str:
        """
        Prompt V2 com few-shot examples e diretrizes detalhadas
        """
        prompt = """Você é um especialista em resumir notícias governamentais brasileiras. Sua tarefa é criar resumos concisos, informativos e fiéis ao conteúdo original.

## DIRETRIZES:

1. **Fidelidade**: Extraia APENAS informações presentes no texto original
2. **Completude**: Inclua os pontos principais e informações essenciais
3. **Concisão**: Use 2-4 sentenças completas (100-150 palavras)
4. **Clareza**: Linguagem objetiva, direta e acessível
5. **Estrutura**: Priorize ordem lógica (quem, o que, onde, quando, por quê, como)

## EVITE:

- Adicionar informações externas ou interpretações
- Copiar trechos literais longos
- Usar jargões técnicos sem explicação
- Incluir detalhes secundários
- Repetir informações

## IMPORTANTE: Mantenha alta fidelidade ao conteúdo original. Verifique mentalmente se todas as informações do resumo estão na notícia.

## EXEMPLOS:

### Exemplo 1:
**NOTÍCIA:**
Parceria garante novas edições do concurso até 2028 e aproxima pesquisa, setor produtivo e políticas públicas para o desenvolvimento florestal sustentável. O Serviço Florestal Brasileiro (SFB) e a Confederação Nacional da Indústria (CNI) renovaram acordo de cooperação técnica para realizar o Prêmio em Estudos de Economia e Mercado Florestal.

**RESUMO:**
O Serviço Florestal Brasileiro (SFB) e a Confederação Nacional da Indústria (CNI) renovam laços para o Prêmio em Estudos de Economia e Mercado Florestal, garantindo novas edições do concurso até 2028. Essa parceria visa o desenvolvimento florestal sustentável no Brasil.

### Exemplo 2:
**NOTÍCIA:**
O MinC reforça a recomendação para que todos os candidatos consultem antecipadamente sua regularidade jurídica, fiscal e tributária. Estar em débito com a União impede o recebimento de recursos públicos. É fundamental resolver eventuais pendências nos seguintes sistemas: Cadastro Informativo de Créditos Não Quitados do Setor Público Federal (Cadin); Certidão Negativa de Débitos Relativos a Créditos Tributários Federais e à Dívida Ativa da União (CND); Certificado de Regularidade do FGTS; Sistema Integrado de Administração Financeira (Siafi) através do Constransf; Sistema de Apoio às Leis de Incentivo à Cultura (Salic); Cadastro de Entidades Privadas sem Fins Lucrativos Impedidas (Cepim); Cadastro Nacional de Empresas Inidôneas e Suspensas (Ceis); e Sistema de Cadastramento Unificado de Fornecedores (Sicaf).

**RESUMO:**
O Ministério da Cultura (MinC) do Brasil recomenda que todos os candidatos a receber recursos públicos verifiquem antecipadamente sua regularidade jurídica, fiscal e tributária. Estar em débito com a União impede o recebimento desses recursos. É essencial que os candidatos resolvam eventuais pendências em diversos sistemas governamentais de regularização fiscal e tributária.

### Exemplo 3:
**NOTÍCIA:**
Advocacia-Geral da União confirma no TRF2 a legalidade da fiscalização ambiental e do auto de infração de mais de R$ 4 milhões contra empresa de serviços geofísicos. A Advocacia-Geral da União (AGU) obteve decisão favorável no Tribunal Regional Federal da 2ª Região (TRF2) que mantém a legalidade da multa ambiental de R$ 4,07 milhões aplicada pelo Instituto Brasileiro do Meio Ambiente e dos Recursos Naturais Renováveis (Ibama) à empresa Spectrum Geo do Brasil Serviços Geofísicos Ltda. A empresa foi autuada por realizar pesquisa sísmica marítima sem licença ambiental. O TRF2 rejeitou o recurso da empresa e reconheceu a regularidade do procedimento administrativo e da penalidade aplicada. A decisão destaca que há depósito judicial superior a R$ 7 milhões, valor suficiente para garantir o crédito em discussão.

**RESUMO:**
A Advocacia-Geral da União (AGU) confirmou a legalidade da multa ambiental de R$ 4,07 milhões aplicada pelo Ibama à empresa Spectrum Geo do Brasil Serviços Geofísicos Ltda. por realizar pesquisa sísmica marítima sem licença ambiental. O Tribunal Regional Federal da 2ª Região (TRF2) rejeitou o recurso da empresa e reconheceu a regularidade do procedimento administrativo e da penalidade.

---

Agora resuma a seguinte notícia seguindo as diretrizes e o padrão dos exemplos acima:

**NOTÍCIA:**
{text}

**RESUMO:**"""

        return prompt.format(text=text)


# Versões V2 dos 3 modelos selecionados

class Nova2LiteSummarizerV2(BedrockAbstractiveSummarizerV2):
    """Amazon Nova 2 Lite V2 - Com prompt otimizado"""
    def __init__(self):
        super().__init__(
            model_id="us.amazon.nova-2-lite-v1:0",
            model_name="Nova 2 Lite V2"
        )


class ClaudeHaiku4SummarizerV2(BedrockAbstractiveSummarizerV2):
    """Claude Haiku 4.5 V2 - Com prompt otimizado"""
    def __init__(self):
        super().__init__(
            model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
            model_name="Claude Haiku 4.5 V2"
        )


class Llama33SummarizerV2(BedrockAbstractiveSummarizerV2):
    """Llama 3.3 70B V2 - Com prompt otimizado"""
    def __init__(self):
        super().__init__(
            model_id="us.meta.llama3-3-70b-instruct-v1:0",
            model_name="Llama 3.3 70B V2"
        )
