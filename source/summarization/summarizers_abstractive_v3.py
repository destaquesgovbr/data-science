"""
Sumarizadores Abstractive V3 - Prompt V3 Otimizado (5-Shot + Gov.BR específico)
Fase 3C: Refinamento final para atingir ROUGE-L > 0.55
"""

from summarizers_abstractive import BedrockAbstractiveSummarizer


class BedrockAbstractiveSummarizerV3(BedrockAbstractiveSummarizer):
    """
    Versão V3 com prompt otimizado usando 5-shot learning + instruções gov.br específicas
    """

    def _build_prompt(self, text: str, target_sentences: int = 3) -> str:
        """
        Prompt V3 com 5-shot examples e diretrizes específicas para notícias governamentais
        """
        prompt = """Você é um especialista em resumir notícias governamentais brasileiras. Crie resumos concisos, informativos e fiéis ao conteúdo original.

## DIRETRIZES ESSENCIAIS:

1. **Fidelidade Absoluta**: Extraia APENAS informações explicitamente presentes no texto original. Não infira, não interprete, não adicione contexto externo.

2. **Estrutura Jornalística**: Priorize o lead (quem, o que, quando, onde, por quê, como) nas primeiras frases.

3. **Concisão Precisa**: Use exatamente 2-4 sentenças completas (100-150 palavras). Seja direto e objetivo.

4. **Jargão Governamental**:
   - Mantenha siglas e termos técnicos quando essenciais (INSS, SUS, TCU, etc.)
   - Explique apenas se for crítico para compreensão
   - Preserve nomes de órgãos, programas e leis

5. **Hierarquia de Informação**:
   - Informação principal PRIMEIRO (o fato central)
   - Detalhes relevantes DEPOIS (números, datas, impactos)
   - Omita detalhes secundários (agenda, contatos, links)

6. **Linguagem**: Português brasileiro formal, objetiva, sem jargões desnecessários. Tom neutro e factual.

## EVITE:

- Adicionar informações, interpretações ou contexto externo
- Copiar trechos literais muito longos (paráfrase é preferível)
- Incluir detalhes procedimentais irrelevantes
- Repetir informações
- Usar linguagem opinativa ou valorativa

## IMPORTANTE:
Valide mentalmente cada frase do resumo perguntando: "Essa informação está explícita no texto original?" Se não, remova.

---

## EXEMPLOS (diversos tamanhos e categorias):

### Exemplo 1 - SAÚDE (curto):
**NOTÍCIA:**
O Ministério da Saúde lança campanha nacional de vacinação contra a gripe, que começa na segunda-feira (10) em todos os estados. A meta é imunizar 90% do público prioritário, que inclui idosos, crianças de 6 meses a 5 anos, gestantes, puérperas e profissionais de saúde. Serão disponibilizadas 80 milhões de doses da vacina trivalente, que protege contra três cepas do vírus influenza.

**RESUMO:**
O Ministério da Saúde inicia na segunda-feira (10) campanha nacional de vacinação contra a gripe em todo o país, com meta de imunizar 90% do público prioritário. Serão disponibilizadas 80 milhões de doses da vacina trivalente para idosos, crianças de 6 meses a 5 anos, gestantes, puérperas e profissionais de saúde.

### Exemplo 2 - ECONOMIA (médio):
**NOTÍCIA:**
O Banco Central divulgou nesta terça-feira (15) que a inflação oficial medida pelo IPCA ficou em 0,42% em março, acumulando 3,16% no ano e 4,65% em 12 meses. O resultado ficou dentro da meta de inflação estabelecida pelo Conselho Monetário Nacional, que é de 3% com tolerância de 1,5 ponto percentual para cima ou para baixo. Os principais vilões foram os grupos de alimentação e bebidas (0,68%) e transportes (0,53%), enquanto habitação teve deflação de 0,15%.

**RESUMO:**
O IPCA registrou inflação de 0,42% em março, acumulando 3,16% no ano e 4,65% em 12 meses, dentro da meta de 3% estabelecida pelo Conselho Monetário Nacional. Os grupos de alimentação e bebidas (0,68%) e transportes (0,53%) puxaram a alta, enquanto habitação apresentou deflação de 0,15%. O Banco Central divulgou os dados nesta terça-feira (15).

### Exemplo 3 - INFRAESTRUTURA (longo):
**NOTÍCIA:**
O Governo Federal anunciou nesta quinta-feira (20) investimento de R$ 12,5 bilhões para duplicação de 850 quilômetros da BR-163, entre Sinop (MT) e Itaituba (PA), através do Novo PAC. A obra será realizada em parceria com o setor privado via concessão, com previsão de início em 2027 e conclusão em 2032. A duplicação da rodovia, conhecida como Corredor de Exportação do Norte, vai beneficiar o escoamento da produção de soja, milho e carne do Mato Grosso até os portos do Pará, reduzindo o tempo de viagem em 40% e os custos de logística em até 30%. O projeto inclui construção de 45 pontes, 12 viadutos e melhorias em 8 trechos urbanos, gerando cerca de 15 mil empregos diretos durante a construção.

**RESUMO:**
O Governo Federal anunciou investimento de R$ 12,5 bilhões para duplicar 850 km da BR-163 entre Sinop (MT) e Itaituba (PA), através do Novo PAC, com obras previstas entre 2027 e 2032 via concessão ao setor privado. A duplicação do Corredor de Exportação do Norte vai beneficiar o escoamento de soja, milho e carne do Mato Grosso aos portos do Pará, reduzindo tempo de viagem em 40% e custos logísticos em até 30%. O projeto inclui construção de 45 pontes, 12 viadutos e melhorias em trechos urbanos, gerando 15 mil empregos diretos.

### Exemplo 4 - SEGURANÇA PÚBLICA (complexo):
**NOTÍCIA:**
A Polícia Federal deflagrou nesta manhã (8) a Operação Guardião Digital, que investiga esquema de fraudes em licitações de sistemas de tecnologia em 12 estados. Foram cumpridos 47 mandados de busca e apreensão e 15 de prisão temporária em São Paulo, Rio de Janeiro, Brasília e outras capitais. As investigações apontam que empresas de TI criavam empresas de fachada para fraudar processos licitatórios e superfaturar contratos públicos, causando prejuízo estimado de R$ 850 milhões aos cofres públicos nos últimos 3 anos. Os crimes investigados incluem formação de organização criminosa, fraude à licitação, lavagem de dinheiro e corrupção ativa e passiva. A operação contou com apoio da Controladoria-Geral da União (CGU) e do Tribunal de Contas da União (TCU).

**RESUMO:**
A Polícia Federal deflagrou nesta manhã (8) a Operação Guardião Digital, cumprindo 47 mandados de busca e 15 de prisão em 12 estados para investigar fraudes em licitações de sistemas de TI. As investigações apontam que empresas criavam fachadas para superfaturar contratos públicos, causando prejuízo de R$ 850 milhões em 3 anos. Os crimes incluem organização criminosa, fraude à licitação, lavagem de dinheiro e corrupção, com apoio da CGU e TCU.

### Exemplo 5 - EDUCAÇÃO (técnico):
**NOTÍCIA:**
O Ministério da Educação (MEC) publicou nesta segunda-feira (12) no Diário Oficial da União a Portaria nº 387, que estabelece as diretrizes para a implementação do Novo Ensino Médio em todas as redes públicas e privadas a partir de 2027. A norma define que os estudantes deverão cursar obrigatoriamente 2.400 horas de formação geral básica e poderão escolher entre 5 itinerários formativos com carga horária de 600 horas, totalizando 3.000 horas ao longo dos três anos. Os itinerários incluem linguagens, matemática, ciências da natureza, ciências humanas e formação técnica e profissional. As escolas terão até dezembro de 2026 para adequar seus currículos e realizar formação de professores, com apoio técnico e financeiro do MEC através do Programa de Apoio ao Novo Ensino Médio (ProNEM), que destinará R$ 1,2 bilhão para estados e municípios.

**RESUMO:**
O Ministério da Educação publicou nesta segunda-feira (12) a Portaria nº 387, estabelecendo diretrizes para implementação do Novo Ensino Médio a partir de 2027 em todas as redes. Os estudantes cursarão 2.400 horas de formação geral básica obrigatória e 600 horas de um entre 5 itinerários formativos (linguagens, matemática, ciências da natureza, ciências humanas ou formação técnica), totalizando 3.000 horas. As escolas têm até dezembro de 2026 para adequar currículos e formar professores, com apoio do MEC via ProNEM, que destinará R$ 1,2 bilhão a estados e municípios.

---

## SUA TAREFA:

Agora resuma a seguinte notícia governamental brasileira seguindo RIGOROSAMENTE as diretrizes e o padrão dos exemplos acima:

**NOTÍCIA:**
{text}

**RESUMO:**"""

        return prompt.format(text=text)


# Versões V3 dos 3 melhores modelos

class NovaProSummarizerV3(BedrockAbstractiveSummarizerV3):
    """Amazon Nova Pro V3 - Líder atual (0.518)"""
    def __init__(self):
        super().__init__(
            model_id="amazon.nova-pro-v1:0",
            model_name="Nova Pro V3"
        )


class Nova2LiteSummarizerV3(BedrockAbstractiveSummarizerV3):
    """Amazon Nova 2 Lite V3 - Vice-líder (0.502)"""
    def __init__(self):
        super().__init__(
            model_id="amazon.nova-2-lite-v1:0",
            model_name="Nova 2 Lite V3"
        )


class ClaudeHaiku4SummarizerV3(BedrockAbstractiveSummarizerV3):
    """Claude Haiku 4.5 V3 - Terceiro lugar (0.485)"""
    def __init__(self):
        super().__init__(
            model_id="anthropic.claude-haiku-4-5-20251001-v1:0",
            model_name="Claude Haiku 4.5 V3"
        )
