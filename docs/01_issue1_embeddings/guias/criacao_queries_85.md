# Guia para Criação de 85 Queries

**Data:** 26/03/2026

## 📊 Distribuição

**Total: 85 queries**
- 35 queries gerais (linguagem natural, público leigo)
- 35 queries jargão BR (termos técnicos, profissionais)
- 15 queries docs longos (complexas, múltiplos conceitos)

---

## 📏 Tamanho das Queries: Fundamentação

### **Por que queries curtas?**

Baseado em estudos de comportamento de busca e Information Retrieval:

#### **Pesquisas Acadêmicas:**
- **Jansen et al. (2000)**: Análise de 51.473 queries do Excite.com
  - Média: **2.35 palavras por query**
  - Mediana: 2 palavras
  - Ref: *"Real life, real users, and real needs: a study and analysis of user queries on the web"*

- **Spink et al. (2001)**: Estudo com 1 milhão de queries do Excite
  - Média: **2.6 palavras**
  - Distribuição: 1 palavra (20%), 2 palavras (32%), 3 palavras (26%)
  - Ref: *"Searching the Web: The public and their queries"*

- **Estudos recentes (2015-2020)**: Google/Bing
  - Média cresceu para **3-4 palavras** (influência de mobile e busca por voz)
  - Queries técnicas tendem a ser mais longas (3-5 palavras)

#### **Nosso Critério:**

| Tipo de Query | Palavras | Justificativa |
|---------------|----------|---------------|
| **Geral** | 2-3 | Simula usuário leigo/curioso buscando informação geral |
| **Jargão BR** | 3-4 | Profissionais usam siglas + contexto técnico |
| **Doc Longo** | 4-5 | Tópicos complexos exigem múltiplos conceitos |

**Média esperada: ~3 palavras** (alinhado com estudos atuais)

#### **Exemplos:**

```
✅ Queries Gerais (2-3 palavras):
- "vacinação infantil"
- "microcrédito pescadores"
- "nota enem medicina"

✅ Queries Jargão BR (3-4 palavras):
- "PRONAF crédito rural agricultura"
- "ANVISA registro medicamento genérico"
- "SUS atenção básica UBS"

✅ Queries Docs Longos (4-5 palavras):
- "reforma tributária impacto pequenas empresas"
- "política ambiental desmatamento Amazônia preservação"
```

---

## 🎯 Como Usar Este Template

Para cada query, você tem **3 opções**:

### Opção 1: Usar a query recomendada (MAIS RÁPIDO)
```json
"recommended_query": "peixamento açude piscicultura alevinos"
"query_text": "peixamento açude piscicultura alevinos"  ← Copiar
```

### Opção 2: Escolher uma das variantes
```json
"variants": [
  {"text": "dnocs realiza peixamento açude", "type": "from_title"},
  {"text": "dnocs piscicultura alevinos", "type": "with_jargon"},
  {"text": "piscicultura município alevinos", "type": "without_jargon"}
]
"query_text": "piscicultura município alevinos"  ← Escolher variante
```

### Opção 3: Criar sua própria (SE NECESSÁRIO)
```json
"query_text": "sua query customizada aqui"
```

## 💡 Dicas

✅ **Para queries GERAIS:** Prefira variantes `without_jargon`
✅ **Para queries JARGÃO BR:** Prefira variantes `with_jargon`
✅ **Para queries LONGAS:** Use mais palavras, múltiplos conceitos

---

## 📄 Queries por Categoria

### Agricultura (9 queries)

#### q001 - jargao_br

**Doc:** doc_01_08 - DNOCS realiza peixamento no Açude Ema em Iracema/CE...

**Recomendada:** `dnocs realiza peixamento`

**Variantes:**
- 🔧 `dnocs realiza peixamento` (from_title)
- 🔧 `dnocs sus dnocs piscicultura` (with_jargon)
- 💬 `piscicultura município alevinos` (without_jargon)

---

#### q002 - geral

**Doc:** doc_01_15 - Microcrédito e equipamentos chegam a pescadores de Calçoene (AP)...

**Recomendada:** `microcrédito equipamentos chegam`

**Variantes:**
- 💬 `microcrédito equipamentos chegam` (from_title)
- 🔧 `ministério calçoene mutirão` (with_jargon)
- 💬 `calçoene mutirão microcrédito` (without_jargon)

---

#### q003 - geral

**Doc:** doc_01_21 - Já está valendo: selo garante origem aos pescados da pesca artesanal...

**Recomendada:** `valendo: selo garante`

**Variantes:**
- 💬 `valendo: selo garante` (from_title)
- 🔧 `ministério portaria selo pesca` (with_jargon)
- 💬 `selo pesca artesanal` (without_jargon)

---

#### q004 - jargao_br

**Doc:** doc_01_03 - Portaria interministerial amplia prazo para adesão ao PREPS; confira...

**Recomendada:** `portaria interministerial amplia`

**Variantes:**
- 🔧 `portaria interministerial amplia` (from_title)
- 🔧 `secretaria ministério embarcações prazo` (with_jargon)
- 💬 `embarcações prazo preps` (without_jargon)

---

#### q005 - geral

**Doc:** doc_01_06 - Acordo põe fim a conflito agrário histórico no oeste do Paraná...

**Recomendada:** `acordo conflito agrário`

**Variantes:**
- 💬 `acordo conflito agrário` (from_title)
- 🔧 `ministério resolução região acordo` (with_jargon)
- 💬 `região acordo conciliação` (without_jargon)

---

#### q006 - geral

**Doc:** doc_01_10 - Microcrédito movimenta R$ 69 milhões em mais de 5 mil novos contratos em janeiro...

**Recomendada:** `microcrédito movimenta milhões`

**Variantes:**
- 💬 `microcrédito movimenta milhões` (from_title)
- 🔧 `ministério pronaf milhões midr` (with_jargon)
- 💬 `milhões midr desde` (without_jargon)

---

#### q007 - geral

**Doc:** doc_01_12 - Dias destaca papel da agricultura familiar e avanços na luta contra a fome em se...

**Recomendada:** `dias destaca papel`

**Variantes:**
- 💬 `dias destaca papel` (from_title)
- 🔧 `mapa sus políticas fome` (with_jargon)
- 💬 `políticas fome familiar` (without_jargon)

---

#### q008 - geral

**Doc:** doc_01_13 - Receita Federal esclarece processamento das solicitações ao Simples Nacional e a...

**Recomendada:** `receita federal esclarece`

**Variantes:**
- 💬 `receita federal esclarece` (from_title)
- 💬 `solicitações simples nacional` (without_jargon)

---

#### q009 - doc_longo

**Doc:** doc_01_02 - Brasil atinge novo recorde na safra de grãos, com 346,1 milhões de toneladas em ...

**Recomendada:** `brasil atinge novo`

**Variantes:**
- 💬 `brasil atinge novo` (from_title)
- 🔧 `embrapa sus milhões toneladas` (with_jargon)
- 💬 `milhões toneladas produção` (without_jargon)
- 💬 `milhões toneladas produção milhões toneladas` (long_doc)

---

### Assistência Social (9 queries)

#### q010 - geral

**Doc:** doc_03_02 - Em documento, governo sintetiza políticas, equipamentos e serviços públicos de p...

**Recomendada:** `documento, sintetiza políticas,`

**Variantes:**
- 💬 `documento, sintetiza políticas,` (from_title)
- 🔧 `ministério funai social documento` (with_jargon)
- 💬 `social documento yanomami` (without_jargon)

---

#### q011 - geral

**Doc:** doc_03_04 - Sudene e MDS vão lançar projetos de proteção social nos estados do Nordeste...

**Recomendada:** `sudene lançar projetos`

**Variantes:**
- 💬 `sudene lançar projetos` (from_title)
- 🔧 `ministério sus sudene rede` (with_jargon)
- 💬 `sudene rede social` (without_jargon)

---

#### q012 - geral

**Doc:** doc_03_16 - Iniciativas de reintegração social de mulheres no Espírito Santo recebem visita ...

**Recomendada:** `iniciativas reintegração social`

**Variantes:**
- 💬 `iniciativas reintegração social` (from_title)
- 🔧 `secretaria ministério parcerias social` (with_jargon)
- 💬 `parcerias social foto` (without_jargon)

---

#### q013 - geral

**Doc:** doc_03_00 - Programa Abdias Nascimento: CAPES publica edital de renovação de projetos para 2...

**Recomendada:** `programa abdias nascimento:`

**Variantes:**
- 💬 `programa abdias nascimento:` (from_title)
- 🔧 `secretaria ministério capes educação` (with_jargon)
- 💬 `educação programa imagem` (without_jargon)

---

#### q014 - geral

**Doc:** doc_03_06 - MDHC fortalece diálogo sobre envelhecimento da população LGBTQIA+ com o Fonges-L...

**Recomendada:** `mdhc fortalece diálogo`

**Variantes:**
- 💬 `mdhc fortalece diálogo` (from_title)
- 🔧 `secretaria ministério lgbtqia envelhecimento` (with_jargon)
- 💬 `lgbtqia envelhecimento população` (without_jargon)

---

#### q015 - geral

**Doc:** doc_03_07 - Tesouro Nacional recebe certificado do Pnud e lança estratégia de igualdade de g...

**Recomendada:** `tesouro nacional recebe`

**Variantes:**
- 💬 `tesouro nacional recebe` (from_title)
- 🔧 `ubs tesouro selo` (with_jargon)
- 💬 `tesouro selo igualdade` (without_jargon)

---

#### q016 - geral

**Doc:** doc_03_08 - Programa Computadores para Inclusão beneficia organizações sociais na Paraíba...

**Recomendada:** `programa computadores inclusão`

**Variantes:**
- 💬 `programa computadores inclusão` (from_title)
- 🔧 `ministério sus inclusão mdhc` (with_jargon)
- 💬 `inclusão mdhc computadores` (without_jargon)

---

#### q017 - jargao_br

**Doc:** doc_03_09 - Ministério do Turismo lança pesquisa inédita para conhecer o perfil de turistas ...

**Recomendada:** `ministério turismo lança`

**Variantes:**
- 🔧 `ministério turismo lança` (from_title)
- 🔧 `ministério agência turismo acessibilidade` (with_jargon)
- 💬 `turismo acessibilidade acessível` (without_jargon)

---

#### q018 - doc_longo

**Doc:** doc_03_20 - Estudo mostra que 90% dos cuidadores informais no Brasil são mulheres...

**Recomendada:** `estudo mostra cuidadores`

**Variantes:**
- 💬 `estudo mostra cuidadores` (from_title)
- 🔧 `agência agu mulheres trabalho` (with_jargon)
- 💬 `mulheres trabalho cuidado` (without_jargon)
- 💬 `mulheres trabalho cuidado mulheres trabalho` (long_doc)

---

### Ciência e Tecnologia (9 queries)

#### q019 - geral

**Doc:** doc_05_03 - Inovação normativa da Conitec: entenda o que mudou...

**Recomendada:** `inovação normativa conitec:`

**Variantes:**
- 💬 `inovação normativa conitec:` (from_title)
- 🔧 `secretaria portaria conitec cartilha` (with_jargon)
- 💬 `conitec cartilha inovação` (without_jargon)

---

#### q020 - geral

**Doc:** doc_05_10 - CBPF abre inscrições abertas para a I Escola Teórica de Campos e Partículas do R...

**Recomendada:** `cbpf abre inscrições`

**Variantes:**
- 💬 `cbpf abre inscrições` (from_title)
- 💬 `2026 cbpf escola` (without_jargon)

---

#### q021 - geral

**Doc:** doc_05_11 - ABIN firma parceria estratégica com Laboratório de Inovação da Enap...

**Recomendada:** `abin firma parceria`

**Variantes:**
- 💬 `abin firma parceria` (from_title)
- 💬 `inteligência inovação artificial` (without_jargon)

---

#### q022 - geral

**Doc:** doc_05_00 - Ministra Luciana Santos destaca projeto do Reator Multipropósito Brasileiro, em ...

**Recomendada:** `ministra luciana santos`

**Variantes:**
- 💬 `ministra luciana santos` (from_title)
- 🔧 `ministério sus nacional ciência` (with_jargon)
- 💬 `nacional ciência projeto` (without_jargon)

---

#### q023 - geral

**Doc:** doc_05_01 - Brasil aprofunda debate sobre responsabilidade civil nuclear em workshop co-orga...

**Recomendada:** `brasil aprofunda debate`

**Variantes:**
- 💬 `brasil aprofunda debate` (from_title)
- 🔧 `ministério agência nuclear ansn` (with_jargon)
- 💬 `nuclear ansn nucleares` (without_jargon)

---

#### q024 - geral

**Doc:** doc_05_02 - Deputado Júlio Lopes propõe transformação da ANSN em Agência Reguladora Nuclear...

**Recomendada:** `deputado júlio lopes`

**Variantes:**
- 💬 `deputado júlio lopes` (from_title)
- 🔧 `ministério agência nuclear ansn` (with_jargon)
- 💬 `nuclear ansn deputado` (without_jargon)

---

#### q025 - geral

**Doc:** doc_05_05 - Seminário do CENTENA divulga resultados e pesquisas desenvolvidas em 2025...

**Recomendada:** `seminário centena divulga`

**Variantes:**
- 💬 `seminário centena divulga` (from_title)
- 🔧 `ministério ibama centena projeto` (with_jargon)
- 💬 `centena projeto foto` (without_jargon)

---

#### q026 - geral

**Doc:** doc_05_06 - Embraer faz primeiro voo de aeronave elétrica de decolagem e pouso vertical...

**Recomendada:** `embraer primeiro aeronave`

**Variantes:**
- 💬 `embraer primeiro aeronave` (from_title)
- 🔧 `secretaria ministério aviação testes` (with_jargon)
- 💬 `aviação testes aeronave` (without_jargon)

---

#### q027 - doc_longo

**Doc:** doc_05_13 - Diretor-Geral do CENSIPAM realiza visita técnica ao Centro Tecnológico da Marinh...

**Recomendada:** `diretor-geral censipam realiza`

**Variantes:**
- 💬 `diretor-geral censipam realiza` (from_title)
- 🔧 `ministério marinha censipam` (with_jargon)
- 💬 `marinha censipam diretor` (without_jargon)
- 💬 `marinha censipam diretor marinha censipam` (long_doc)

---

### Cultura (9 queries)

#### q028 - geral

**Doc:** doc_07_06 - Mais de 800 obras disputam as premiações do 3º Concurso de Fotos e Vídeos da Ana...

**Recomendada:** `obras disputam premiações`

**Variantes:**
- 💬 `obras disputam premiações` (from_title)
- 🔧 `ubs fotos vídeos` (with_jargon)
- 💬 `fotos vídeos anatel` (without_jargon)

---

#### q029 - geral

**Doc:** doc_07_08 - Mostra vai premiar trabalhos fotográficos e audiovisuais das favelas brasileiras...

**Recomendada:** `mostra premiar trabalhos`

**Variantes:**
- 💬 `mostra premiar trabalhos` (from_title)
- 🔧 `secretaria ministério mostra periferias` (with_jargon)
- 💬 `mostra periferias selecionadas` (without_jargon)

---

#### q030 - geral

**Doc:** doc_07_10 - Cerimônia do Chá e “Harmonias brasileiras” na programação da Casa Pacheco Leão...

**Recomendada:** `cerimônia “harmonias brasileiras”`

**Variantes:**
- 💬 `cerimônia “harmonias brasileiras”` (from_title)
- 💬 `flautas casa cerimônia` (without_jargon)

---

#### q031 - geral

**Doc:** doc_07_00 - Heróis da Pátria são reconhecidos durante 7a edição do Rede Capoeira em Cachoeir...

**Recomendada:** `heróis pátria reconhecidos`

**Variantes:**
- 💬 `heróis pátria reconhecidos` (from_title)
- 🔧 `ministério cultura capoeira` (with_jargon)
- 💬 `cultura capoeira mestres` (without_jargon)

---

#### q032 - geral

**Doc:** doc_07_02 - Rumo à 6ª Teia Nacional, Mato Grosso do Sul realiza encontro estadual da rede do...

**Recomendada:** `rumo teia nacional,`

**Variantes:**
- 💬 `rumo teia nacional,` (from_title)
- 🔧 `secretaria ministério cultura estado` (with_jargon)
- 💬 `cultura estado cultural` (without_jargon)

---

#### q033 - geral

**Doc:** doc_07_05 - Seleção TV Brasil anuncia projetos selecionados no maior investimento da históri...

**Recomendada:** `seleção brasil anuncia`

**Variantes:**
- 💬 `seleção brasil anuncia` (from_title)
- 🔧 `ministério agência linha brasil` (with_jargon)
- 💬 `linha brasil pública` (without_jargon)

---

#### q034 - geral

**Doc:** doc_07_12 - MinC convoca candidaturas suplentes do Edital Sérgio Mamberti para assumir vagas...

**Recomendada:** `minc convoca candidaturas`

**Variantes:**
- 💬 `minc convoca candidaturas` (from_title)
- 🔧 `secretaria ministério prêmio cultura` (with_jargon)
- 💬 `prêmio cultura edital` (without_jargon)

---

#### q035 - geral

**Doc:** doc_07_13 - Oficinas de arte rupestre impulsionam conexão de estudantes de Monte Alegre com ...

**Recomendada:** `oficinas arte rupestre`

**Variantes:**
- 💬 `oficinas arte rupestre` (from_title)
- 🔧 `agência ldo monte alegre` (with_jargon)
- 💬 `monte alegre comunidade` (without_jargon)

---

#### q036 - doc_longo

**Doc:** doc_07_03 - Campanha nacional articula cultura, direitos humanos e combate ao racismo no Car...

**Recomendada:** `campanha nacional articula`

**Variantes:**
- 💬 `campanha nacional articula` (from_title)
- 🔧 `ministério carnaval campanha` (with_jargon)
- 💬 `carnaval campanha racismo` (without_jargon)
- 💬 `carnaval campanha racismo carnaval campanha` (long_doc)

---

### Economia (9 queries)

#### q037 - geral

**Doc:** doc_09_02 - Cade seleciona consultor para apoiar elaboração do Guia de Abuso de Poder Econôm...

**Recomendada:** `cade seleciona consultor`

**Variantes:**
- 💬 `cade seleciona consultor` (from_title)
- 💬 `cade abuso podem` (without_jargon)

---

#### q038 - geral

**Doc:** doc_09_03 - Investimento, indústria e empregos: novas locomotivas impulsionam a ferrovia bra...

**Recomendada:** `investimento, indústria empregos:`

**Variantes:**
- 💬 `investimento, indústria empregos:` (from_title)
- 🔧 `antt sus milhões entrega` (with_jargon)
- 💬 `milhões entrega novas` (without_jargon)

---

#### q039 - geral

**Doc:** doc_09_05 - CVM e ANBIMA divulgam resultados do Acordo de Cooperação Técnica entre as instit...

**Recomendada:** `anbima divulgam resultados`

**Variantes:**
- 💬 `anbima divulgam resultados` (from_title)
- 🔧 `cvm anbima termos` (with_jargon)
- 💬 `anbima termos compromisso` (without_jargon)

---

#### q040 - geral

**Doc:** doc_09_00 - União honra R$ 11,08 bilhões em dívidas garantidas de entes subnacionais em 2025...

**Recomendada:** `união honra 11,08`

**Variantes:**
- 💬 `união honra 11,08` (from_title)
- 🔧 `secretaria sus milhões total` (with_jargon)
- 💬 `milhões total bilhões` (without_jargon)

---

#### q041 - geral

**Doc:** doc_09_01 - Ano de 2025 encerra com número recorde de regulados pela CVM...

**Recomendada:** `encerra número recorde`

**Variantes:**
- 💬 `encerra número recorde` (from_title)
- 🔧 `mapa cvm 2025 mercado` (with_jargon)
- 💬 `2025 mercado bilhões` (without_jargon)

---

#### q042 - geral

**Doc:** doc_09_04 - Cade divulga Anuário 2025 com balanço da atuação em defesa da concorrência...

**Recomendada:** `cade divulga anuário`

**Variantes:**
- 💬 `cade divulga anuário` (from_title)
- 🔧 `agência cade 2025` (with_jargon)
- 💬 `cade 2025 defesa` (without_jargon)

---

#### q043 - jargao_br

**Doc:** doc_09_06 - Aplicativo do Gás do Povo é o mais baixado do Brasil e consolida adesão recorde ...

**Recomendada:** `loa programa revendas`

**Variantes:**
- 💬 `aplicativo povo baixado` (from_title)
- 🔧 `loa programa revendas` (with_jargon)
- 💬 `programa revendas povo` (without_jargon)

---

#### q044 - jargao_br

**Doc:** doc_09_07 - MME abre consulta pública para modernizar a formação de preços de energia elétri...

**Recomendada:** `ministério sus sistema modelo`

**Variantes:**
- 💬 `abre consulta pública` (from_title)
- 🔧 `ministério sus sistema modelo` (with_jargon)
- 💬 `sistema modelo operação` (without_jargon)

---

#### q045 - doc_longo

**Doc:** doc_09_09 - MIDR iniciará escuta ativa de demandas da população do Vale do Jequitinhonha...

**Recomendada:** `midr iniciará escuta`

**Variantes:**
- 💬 `midr iniciará escuta` (from_title)
- 🔧 `secretaria ministério desenvolvimento jogo` (with_jargon)
- 💬 `desenvolvimento jogo regional` (without_jargon)
- 💬 `desenvolvimento jogo regional desenvolvimento jogo` (long_doc)

---

### Educação (9 queries)

#### q046 - jargao_br

**Doc:** doc_11_02 - Vem ser CDTN: seleção aberta para os cursos de Mestrado e Doutorado...

**Recomendada:** `capes mec 2026 processo`

**Variantes:**
- 💬 `cdtn: seleção aberta` (from_title)
- 🔧 `capes mec 2026 processo` (with_jargon)
- 💬 `2026 processo seletivo` (without_jargon)

---

#### q047 - jargao_br

**Doc:** doc_11_04 - Anvisa conclui curso de formação para novos especialistas em regulação...

**Recomendada:** `anvisa conclui curso`

**Variantes:**
- 🔧 `anvisa conclui curso` (from_title)
- 🔧 `agência anvisa encerramento curso` (with_jargon)
- 💬 `encerramento curso formação` (without_jargon)

---

#### q048 - jargao_br

**Doc:** doc_11_10 - Salvador recebe Oficina de Classificação de Documentos Arquivísticos...

**Recomendada:** `ministério documentos gestão`

**Variantes:**
- 💬 `salvador recebe oficina` (from_title)
- 🔧 `ministério documentos gestão` (with_jargon)
- 💬 `documentos gestão oficina` (without_jargon)

---

#### q049 - jargao_br

**Doc:** doc_11_08 - Programa de Pós-Graduação do CDTN alcança nota 6 na Capes...

**Recomendada:** `secretaria ministério cdtn programa`

**Variantes:**
- 💬 `programa pós-graduação cdtn` (from_title)
- 🔧 `secretaria ministério cdtn programa` (with_jargon)
- 💬 `cdtn programa avaliação` (without_jargon)

---

#### q050 - jargao_br

**Doc:** doc_11_11 - ANA convoca aprovados em seu concurso público para quinta chamada da segunda tur...

**Recomendada:** `agência agu curso formação`

**Variantes:**
- 💬 `convoca aprovados concurso` (from_title)
- 🔧 `agência agu curso formação` (with_jargon)
- 💬 `curso formação saneamento` (without_jargon)

---

#### q051 - jargao_br

**Doc:** doc_11_12 - Programa Jovem Cientista da Pesca Artesanal: CNPq e Ministério da Pesca oferecem...

**Recomendada:** `ministério cnpq pesca artesanal`

**Variantes:**
- 💬 `programa jovem cientista` (from_title)
- 🔧 `ministério cnpq pesca artesanal` (with_jargon)
- 💬 `pesca artesanal comunidades` (without_jargon)

---

#### q052 - jargao_br

**Doc:** doc_11_13 - Olimpíadas Nucleares da América Latina abrem inscrições para a edição 2026...

**Recomendada:** `sus 2026 competição`

**Variantes:**
- 💬 `olimpíadas nucleares américa` (from_title)
- 🔧 `sus 2026 competição` (with_jargon)
- 💬 `2026 competição nuclear` (without_jargon)

---

#### q053 - jargao_br

**Doc:** doc_11_14 - Doutorado em Ciências de Florestas Tropicais do Inpa recebe inscrições em fluxo ...

**Recomendada:** `capes inpa seleção`

**Variantes:**
- 💬 `doutorado florestas tropicais` (from_title)
- 🔧 `capes inpa seleção` (with_jargon)
- 💬 `inpa seleção curso` (without_jargon)

---

#### q054 - doc_longo

**Doc:** doc_11_00 - “Governo do Brasil na Rua”: veja os atendimentos e serviços gratuitos que serão ...

**Recomendada:** `“governo brasil rua”:`

**Variantes:**
- 💬 `“governo brasil rua”:` (from_title)
- 🔧 `secretaria inss brasil serviços` (with_jargon)
- 💬 `brasil serviços digital` (without_jargon)
- 💬 `brasil serviços digital brasil serviços` (long_doc)

---

### Infraestrutura (8 queries)

#### q055 - jargao_br

**Doc:** doc_13_02 - Implantação de segmento na BR-020/BA chega a 76% de execução...

**Recomendada:** `dnit quilômetros região`

**Variantes:**
- 💬 `implantação segmento br-020/ba` (from_title)
- 🔧 `dnit quilômetros região` (with_jargon)
- 💬 `quilômetros região piauí` (without_jargon)

---

#### q056 - jargao_br

**Doc:** doc_13_03 - DNIT executa reconstrução de bueiro hidráulico na BR-174/RR...

**Recomendada:** `dnit executa reconstrução`

**Variantes:**
- 🔧 `dnit executa reconstrução` (from_title)
- 🔧 `dnit rodovia ação` (with_jargon)
- 💬 `rodovia ação próximo` (without_jargon)

---

#### q057 - jargao_br

**Doc:** doc_13_07 - Justiça suspende decisão do TCE-MG e garante teto nacional dos exames da CNH do ...

**Recomendada:** `justiça suspende decisão`

**Variantes:**
- 🔧 `justiça suspende decisão` (from_title)
- 🔧 `secretaria ministério carteira decisão` (with_jargon)
- 💬 `carteira decisão valor` (without_jargon)

---

#### q058 - jargao_br

**Doc:** doc_13_00 - Simone Tebet participa da apresentação do contrato de concessão da Rota da Celul...

**Recomendada:** `agu ldo estado celulose`

**Variantes:**
- 💬 `simone tebet participa` (from_title)
- 🔧 `agu ldo estado celulose` (with_jargon)
- 💬 `estado celulose mato` (without_jargon)

---

#### q059 - jargao_br

**Doc:** doc_13_01 - As Rotas de Integração Sul-Americana são agora um Programa formal do MPO...

**Recomendada:** `secretaria ministério rotas programa`

**Variantes:**
- 💬 `rotas integração sul-americana` (from_title)
- 🔧 `secretaria ministério rotas programa` (with_jargon)
- 💬 `rotas programa integração` (without_jargon)

---

#### q060 - jargao_br

**Doc:** doc_13_04 - AVISO DE PAUTA: Prêmio ANTAQ 2025 acontecerá na próxima terça-feira (10)...

**Recomendada:** `agência antaq antaq categoria`

**Variantes:**
- 💬 `aviso pauta: prêmio` (from_title)
- 🔧 `agência antaq antaq categoria` (with_jargon)
- 💬 `categoria prêmio aquaviário` (without_jargon)

---

#### q061 - jargao_br

**Doc:** doc_13_13 - Governos do Brasil e de Minas Gerais dão partida ao projeto de concessão de sane...

**Recomendada:** `secretaria ministério municípios minas`

**Variantes:**
- 💬 `governos brasil minas` (from_title)
- 🔧 `secretaria ministério municípios minas` (with_jargon)
- 💬 `municípios minas gerais` (without_jargon)

---

#### q062 - jargao_br

**Doc:** doc_13_14 - Jader Filho: governo estuda novo modelo para reduzir tarifas e ampliar acesso ao...

**Recomendada:** `ubs modelo transporte`

**Variantes:**
- 💬 `jader filho: estuda` (from_title)
- 🔧 `ubs modelo transporte` (with_jargon)
- 💬 `modelo transporte ministro` (without_jargon)

---

### Meio Ambiente (8 queries)

#### q063 - jargao_br

**Doc:** doc_15_05 - Justiça mantém multa aplicada pelo Ibama por pesquisa sísmica sem licença...

**Recomendada:** `ibama agu ambiental infração`

**Variantes:**
- 💬 `justiça mantém multa` (from_title)
- 🔧 `ibama agu ambiental infração` (with_jargon)
- 💬 `ambiental infração empresa` (without_jargon)

---

#### q064 - jargao_br

**Doc:** doc_15_11 - Construção de barragem avança no Rio Grande do Sul...

**Recomendada:** `secretaria ministério barragem hídrica`

**Variantes:**
- 💬 `construção barragem avança` (from_title)
- 🔧 `secretaria ministério barragem hídrica` (with_jargon)
- 💬 `barragem hídrica midr` (without_jargon)

---

#### q065 - jargao_br

**Doc:** doc_15_15 - Projeto AdaptAÇÃO desembarca no Pará para discutir mudanças climáticas e planeja...

**Recomendada:** `secretaria ministério adaptação projeto`

**Variantes:**
- 💬 `projeto adaptação desembarca` (from_title)
- 🔧 `secretaria ministério adaptação projeto` (with_jargon)
- 💬 `adaptação projeto urbano` (without_jargon)

---

#### q066 - jargao_br

**Doc:** doc_15_02 - Em Belém (PA), Iphan apresenta estudo sobre dinâmicas econômicas associadas ao C...

**Recomendada:** `sus agu patrimônio cultural`

**Variantes:**
- 💬 `belém iphan apresenta` (from_title)
- 🔧 `sus agu patrimônio cultural` (with_jargon)
- 💬 `patrimônio cultural pesquisa` (without_jargon)

---

#### q067 - jargao_br

**Doc:** doc_15_03 - SFB e CNI fortalecem cooperação para Prêmio em Estudos de Economia e Mercado Flo...

**Recomendada:** `cnpq sus florestal setor`

**Variantes:**
- 💬 `fortalecem cooperação prêmio` (from_title)
- 🔧 `cnpq sus florestal setor` (with_jargon)
- 💬 `florestal setor brasileiro` (without_jargon)

---

#### q068 - jargao_br

**Doc:** doc_15_06 - Iniciativa do Inpa transforma resíduos de bambu em decoração natalina sustentáve...

**Recomendada:** `sus mec bambu inpa`

**Variantes:**
- 💬 `iniciativa inpa transforma` (from_title)
- 🔧 `sus mec bambu inpa` (with_jargon)
- 💬 `bambu inpa pesquisadora` (without_jargon)

---

#### q069 - jargao_br

**Doc:** doc_15_07 - ICMBio e órgãos estaduais de meio ambiente realizam a 1ª Oficina de Integração c...

**Recomendada:** `icmbio órgãos estaduais`

**Variantes:**
- 🔧 `icmbio órgãos estaduais` (from_title)
- 🔧 `icmbio agu ações insetos` (with_jargon)
- 💬 `ações insetos polinizadores` (without_jargon)

---

#### q070 - jargao_br

**Doc:** doc_15_16 - Governo do Brasil abre inscrições para o Comitê Nacional de Enfrentamento ao Rac...

**Recomendada:** `ministério portaria comitê povos`

**Variantes:**
- 💬 `brasil abre inscrições` (from_title)
- 🔧 `ministério portaria comitê povos` (with_jargon)
- 💬 `comitê povos enfrentamento` (without_jargon)

---

### Saúde (8 queries)

#### q071 - jargao_br

**Doc:** doc_17_02 - Prorrogado o prazo para envio de textos para a composição do dossiê “Participaçã...

**Recomendada:** `secretaria execução penal`

**Variantes:**
- 💬 `prorrogado prazo envio` (from_title)
- 🔧 `secretaria execução penal` (with_jargon)
- 💬 `execução penal experiência` (without_jargon)

---

#### q072 - jargao_br

**Doc:** doc_17_04 - CGU e PF apuram irregularidades na área da saúde em Alagoas...

**Recomendada:** `polícia federal secretaria ação alagoas`

**Variantes:**
- 💬 `apuram irregularidades área` (from_title)
- 🔧 `polícia federal secretaria ação alagoas` (with_jargon)
- 💬 `ação alagoas federal` (without_jargon)

---

#### q073 - geral

**Doc:** doc_17_10 - Receita Federal em Foz do Iguaçu encontra medicamentos emagrecedores em condiçõe...

**Recomendada:** `receita federal iguaçu`

**Variantes:**
- 💬 `receita federal iguaçu` (from_title)
- 💬 `medicamentos federal emagrecedores` (without_jargon)

---

#### q074 - jargao_br

**Doc:** doc_17_00 - Conselho Nacional de Previdência Social: em última reunião do ano, ministro Woln...

**Recomendada:** `polícia federal ministério social previdência`

**Variantes:**
- 💬 `conselho nacional previdência` (from_title)
- 🔧 `polícia federal ministério social previdência` (with_jargon)
- 💬 `social previdência ministro` (without_jargon)

---

#### q075 - jargao_br

**Doc:** doc_17_06 - Projeto promove testagem para ISTs, cuidados com a tuberculose e educação em saú...

**Recomendada:** `ministério sus saúde tuberculose`

**Variantes:**
- 💬 `projeto promove testagem` (from_title)
- 🔧 `ministério sus saúde tuberculose` (with_jargon)
- 💬 `saúde tuberculose projetos` (without_jargon)

---

#### q076 - geral

**Doc:** doc_17_07 - SST Fácil aproxima a ISO 45001 do dia a dia do trabalho...

**Recomendada:** `fácil aproxima trabalho`

**Variantes:**
- 💬 `fácil aproxima trabalho` (from_title)
- 💬 `saúde segurança gestão` (without_jargon)

---

#### q077 - jargao_br

**Doc:** doc_17_13 - Em paralelo com atenção básica, entregas do Novo PAC Saúde levam média e alta co...

**Recomendada:** `ministério ubs saúde bahia`

**Variantes:**
- 💬 `paralelo atenção básica,` (from_title)
- 🔧 `ministério ubs saúde bahia` (with_jargon)
- 💬 `saúde bahia ministro` (without_jargon)

---

#### q078 - jargao_br

**Doc:** doc_17_14 - Alckmin e Padilha aplicam primeiras doses da vacina contra a dengue fabricada no...

**Recomendada:** `sus ldo saúde presidente`

**Variantes:**
- 💬 `alckmin padilha aplicam` (from_title)
- 🔧 `sus ldo saúde presidente` (with_jargon)
- 💬 `saúde presidente indústria` (without_jargon)

---

### Segurança Pública (7 queries)

#### q079 - jargao_br

**Doc:** doc_19_17 - Susep orienta população após fortes chuvas em Minas Gerais...

**Recomendada:** `susep orienta população`

**Variantes:**
- 🔧 `susep orienta população` (from_title)
- 🔧 `ministério sus seguros autarquia` (with_jargon)
- 💬 `seguros autarquia susep` (without_jargon)

---

#### q080 - geral

**Doc:** doc_19_24 - Cade condena representado em processo de cartel em licitações de aeroportos...

**Recomendada:** `cade condena representado`

**Variantes:**
- 💬 `cade condena representado` (from_title)
- 🔧 `ministério cade federal` (with_jargon)
- 💬 `cade federal públicas` (without_jargon)

---

#### q081 - geral

**Doc:** doc_19_27 - Estupro coletivo no Rio de Janeiro reforça urgência do debate sobre consentiment...

**Recomendada:** `estupro coletivo janeiro`

**Variantes:**
- 💬 `estupro coletivo janeiro` (from_title)
- 🔧 `ministério mulheres direitos` (with_jargon)
- 💬 `mulheres direitos meninas` (without_jargon)

---

#### q082 - geral

**Doc:** doc_19_00 - Megaoperação: Anatel e Receita Federal apreendem quase meio milhão de produtos i...

**Recomendada:** `megaoperação: anatel receita`

**Variantes:**
- 💬 `megaoperação: anatel receita` (from_title)
- 🔧 `agência agu produtos ação` (with_jargon)
- 💬 `produtos ação anatel` (without_jargon)

---

#### q083 - geral

**Doc:** doc_19_04 - Justiça condena empresa a ressarcir pensão por morte ao INSS...

**Recomendada:** `justiça condena empresa`

**Variantes:**
- 💬 `justiça condena empresa` (from_title)
- 🔧 `decreto inss federal trabalho` (with_jargon)
- 💬 `federal trabalho civil` (without_jargon)

---

#### q084 - geral

**Doc:** doc_19_05 - Regiões Nordeste e Sul são monitoradas pelo MIDR após previsão de chuvas intensa...

**Recomendada:** `regiões nordeste monitoradas`

**Variantes:**
- 💬 `regiões nordeste monitoradas` (from_title)
- 🔧 `secretaria ministério defesa civil` (with_jargon)
- 💬 `defesa civil alerta` (without_jargon)

---

#### q085 - geral

**Doc:** doc_19_08 - “Todo apoio será dado”: Alckmin faz balanço das ações do Governo do Brasil na Zo...

**Recomendada:** `“todo apoio será`

**Variantes:**
- 💬 `“todo apoio será` (from_title)
- 🔧 `bolsa família ministério presidente exercício` (with_jargon)
- 💬 `presidente exercício defesa` (without_jargon)

---


---

## 📚 Referências

### Estudos sobre Tamanho de Queries

1. **Jansen, B. J., Spink, A., & Saracevic, T. (2000)**
   *"Real life, real users, and real needs: a study and analysis of user queries on the web"*
   Information Processing & Management, 36(2), 207-227.
   **Principais achados:** Média de 2.35 palavras por query em 51.473 queries analisadas.

2. **Spink, A., Wolfram, D., Jansen, M. B., & Saracevic, T. (2001)**
   *"Searching the Web: The public and their queries"*
   Journal of the American Society for Information Science and Technology, 52(3), 226-234.
   **Principais achados:** Média de 2.6 palavras; distribuição: 1 palavra (20%), 2 palavras (32%), 3 palavras (26%).

3. **Google Search Research (2015-2020)**
   Tendências atuais mostram aumento para 3-4 palavras em média, impulsionado por:
   - Busca móvel (queries mais conversacionais)
   - Busca por voz (frases mais naturais)
   - Maior familiaridade com motores de busca

### Justificativa do Design

Nosso design de queries reflete **dois perfis de usuários reais**:

1. **Público Geral (~40%)**: Queries curtas (2-3 palavras), linguagem natural
   - Ex: cidadãos buscando informações sobre serviços públicos

2. **Profissionais/Especialistas (~40%)**: Queries técnicas (3-4 palavras), com jargões
   - Ex: servidores públicos, jornalistas, gestores buscando informações específicas

3. **Pesquisas Complexas (~20%)**: Queries longas (4-5 palavras), múltiplos conceitos
   - Ex: pesquisadores, analistas buscando contexto detalhado

Esta distribuição permite avaliar a capacidade dos embeddings em **ambos os cenários de uso real**.

---

**Gerado por:** `generate_query_variants.py`
**Projeto:** Estudo Comparativo de Embeddings - Issue #1
**Repositório:** [data-science/embeddings](../../)
