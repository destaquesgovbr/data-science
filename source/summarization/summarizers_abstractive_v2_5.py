"""
Sumarizadores Abstractive V2.5 - Prompt Refinado (3-shot + instruções otimizadas)
Refinamento intermediário: melhora instruções sem aumentar exemplos
"""

from summarizers_abstractive import BedrockAbstractiveSummarizer


class BedrockAbstractiveSummarizerV25(BedrockAbstractiveSummarizer):
    """
    Versão V2.5 com instruções refinadas mantendo 3-shot
    """

    def _build_prompt(self, text: str, target_sentences: int = 3) -> str:
        """
        Prompt V2.5 com instruções otimizadas e 3 exemplos
        """
        prompt = """Você é um especialista em resumir notícias governamentais brasileiras. Crie resumos concisos, informativos e fiéis.

## INSTRUÇÕES ESSENCIAIS:

**1. FIDELIDADE ABSOLUTA**
- Use APENAS informações explícitas no texto original
- Não adicione contexto, interpretações ou conhecimento externo
- Toda frase do resumo deve ser verificável no original

**2. ESTRUTURA (lead jornalístico)**
- 1ª frase: O FATO PRINCIPAL (quem fez o quê, quando)
- 2ª-3ª frases: DETALHES RELEVANTES (números, impactos, contexto necessário)
- Omita: agendas, contatos, links, detalhes procedimentais

**3. FORMATO**
- Exatamente 2-3 sentenças completas
- 100-150 palavras
- Português brasileiro formal e objetivo

**4. JARGÃO GOVERNAMENTAL**
- Mantenha siglas essenciais (INSS, SUS, MEC, TCU)
- Preserve nomes oficiais de órgãos, programas e leis
- Simplifique apenas se não perder precisão

**5. O QUE EVITAR**
- Copiar trechos literais longos (paráfrase é melhor)
- Repetir informações
- Incluir detalhes irrelevantes para compreensão do fato principal

---

## EXEMPLOS:

### Exemplo 1 - PARCERIA INSTITUCIONAL:
**NOTÍCIA:**
Parceria garante novas edições do concurso até 2028 e aproxima pesquisa, setor produtivo e políticas públicas para o desenvolvimento florestal sustentável. O Serviço Florestal Brasileiro (SFB) e a Confederação Nacional da Indústria (CNI) renovaram acordo de cooperação técnica para realizar o Prêmio em Estudos de Economia e Mercado Florestal.

**RESUMO:**
O Serviço Florestal Brasileiro (SFB) e a Confederação Nacional da Indústria (CNI) renovaram acordo de cooperação técnica para o Prêmio em Estudos de Economia e Mercado Florestal, garantindo novas edições até 2028. A parceria visa aproximar pesquisa, setor produtivo e políticas públicas para o desenvolvimento florestal sustentável no Brasil.

### Exemplo 2 - ORIENTAÇÃO TÉCNICA:
**NOTÍCIA:**
O MinC reforça a recomendação para que todos os candidatos consultem antecipadamente sua regularidade jurídica, fiscal e tributária. Estar em débito com a União impede o recebimento de recursos públicos. É fundamental resolver eventuais pendências nos seguintes sistemas: Cadastro Informativo de Créditos Não Quitados do Setor Público Federal (Cadin); Certidão Negativa de Débitos Relativos a Créditos Tributários Federais e à Dívida Ativa da União (CND); Certificado de Regularidade do FGTS; Sistema Integrado de Administração Financeira (Siafi) através do Constransf; Sistema de Apoio às Leis de Incentivo à Cultura (Salic); Cadastro de Entidades Privadas sem Fins Lucrativos Impedidas (Cepim); Cadastro Nacional de Empresas Inidôneas e Suspensas (Ceis); e Sistema de Cadastramento Unificado de Fornecedores (Sicaf).

**RESUMO:**
O Ministério da Cultura (MinC) recomenda que candidatos a recursos públicos verifiquem antecipadamente sua regularidade jurídica, fiscal e tributária, pois débitos com a União impedem o recebimento de recursos. É essencial resolver pendências em sistemas governamentais como Cadin, CND, FGTS, Siafi, Salic, Cepim, Ceis e Sicaf.

### Exemplo 3 - DECISÃO JUDICIAL:
**NOTÍCIA:**
Advocacia-Geral da União confirma no TRF2 a legalidade da fiscalização ambiental e do auto de infração de mais de R$ 4 milhões contra empresa de serviços geofísicos. A Advocacia-Geral da União (AGU) obteve decisão favorável no Tribunal Regional Federal da 2ª Região (TRF2) que mantém a legalidade da multa ambiental de R$ 4,07 milhões aplicada pelo Instituto Brasileiro do Meio Ambiente e dos Recursos Naturais Renováveis (Ibama) à empresa Spectrum Geo do Brasil Serviços Geofísicos Ltda. A empresa foi autuada por realizar pesquisa sísmica marítima sem licença ambiental. O TRF2 rejeitou o recurso da empresa e reconheceu a regularidade do procedimento administrativo e da penalidade aplicada. A decisão destaca que há depósito judicial superior a R$ 7 milhões, valor suficiente para garantir o crédito em discussão.

**RESUMO:**
A Advocacia-Geral da União (AGU) obteve decisão favorável no Tribunal Regional Federal da 2ª Região (TRF2) que mantém a legalidade da multa ambiental de R$ 4,07 milhões aplicada pelo Ibama à empresa Spectrum Geo do Brasil por realizar pesquisa sísmica marítima sem licença ambiental. O TRF2 rejeitou o recurso e reconheceu a regularidade do procedimento administrativo e da penalidade.

---

Agora resuma a seguinte notícia seguindo RIGOROSAMENTE as instruções e o padrão dos exemplos:

**NOTÍCIA:**
{text}

**RESUMO:**"""

        return prompt.format(text=text)


# Versões V2.5 dos 3 melhores modelos

class NovaProSummarizerV25(BedrockAbstractiveSummarizerV25):
    """Amazon Nova Pro V2.5 - Líder V2 (0.518)"""
    def __init__(self):
        super().__init__(
            model_id="amazon.nova-pro-v1:0",
            model_name="Nova Pro V2.5"
        )


class Nova2LiteSummarizerV25(BedrockAbstractiveSummarizerV25):
    """Amazon Nova 2 Lite V2.5 - Vice-líder (0.502)"""
    def __init__(self):
        super().__init__(
            model_id="amazon.nova-2-lite-v1:0",
            model_name="Nova 2 Lite V2.5"
        )


class ClaudeHaiku4SummarizerV25(BedrockAbstractiveSummarizerV25):
    """Claude Haiku 4.5 V2.5 - Terceiro (0.485)"""
    def __init__(self):
        super().__init__(
            model_id="anthropic.claude-haiku-4-5-20251001-v1:0",
            model_name="Claude Haiku 4.5 V2.5"
        )
