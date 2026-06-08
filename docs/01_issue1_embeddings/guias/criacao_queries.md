# Guia para Criação de Queries

## 📋 Instruções

Este documento lista os **60 documentos âncora** selecionados para criação de queries.

Para cada documento, você deve:

1. ✅ **Ler o documento completo** (disponível em `source/embeddings/data/corpus/`)
2. ✅ **Entender o tema principal**
3. ✅ **Escrever uma query** como um usuário real buscaria
4. ✅ **Usar as sugestões** de keywords/jargões (mas não copiar literalmente!)
5. ✅ **Editar o arquivo** `query_template.json` preenchendo o campo `"query_text"`

---

## 🎯 Critérios para Boas Queries

### ✅ Faça:
- Usar 3-6 palavras
- Linguagem natural/coloquial (queries gerais)
- Incluir siglas/jargões (queries técnicas)
- Variar níveis de especificidade

### ❌ Evite:
- Copiar título do documento
- Usar apenas 1 palavra
- Queries muito genéricas (>100 docs relevantes)
- Queries muito específicas (apenas 1 doc relevante)

---

## 📊 Distribuição de Tipos

- **Geral:** 50 queries (linguagem natural, sem jargões)
- **Jargão BR:** 0 queries (siglas, termos técnicos)
- **Doc Longo:** 10 queries (complexas, múltiplos conceitos)

---

## 📄 Documentos Âncora por Categoria

### Agricultura

#### q001 - doc_01_08

**Título:** DNOCS realiza peixamento no Açude Ema em Iracema/CE

**Tipo Sugerido:** `geral`

**Tamanho:** Curta (2469 chars)

**Órgão:** dnocs

**Keywords Sugeridas:** dnocs, piscicultura, município, alevinos, tilápia, estação, ação, peixamento

**Jargões Encontrados:** sus

**Preview:**
> Foram distribuídos 200 mil alevinos de tilápia, fortalecendo a piscicultura e a geração de renda no município
![](https://www.gov.br/dnocs/pt-br/assuntos/noticias/dnocs-realiza-peixamento-no-acude-ema-em-iracema-ce/copy5_of_1.jpg/@@images/1efcc5b6-d103-4e72-b324-459313ea6112.jpeg)

.

![](https://ww...

**Query a criar:** _(preencher no JSON)_

---

#### q002 - doc_01_15

**Título:** Microcrédito e equipamentos chegam a pescadores de Calçoene (AP)

**Tipo Sugerido:** `geral`

**Tamanho:** Curta (1306 chars)

**Órgão:** mdr

**Keywords Sugeridas:** calçoene, mutirão, microcrédito, midr, sábado, ação, neste, presença

**Jargões Encontrados:** ministério

**Preview:**
> Mutirão do microcrédito e entregas do MIDR marcam ação neste sábado (7), com presença de autoridades federais, estaduais e municipais
![Aviso-de-pauta2.png](https://www.gov.br/mdr/pt-br/noticias/microcredito-e-equipamentos-chegam-a-pescadores-de-calcoene-ap/aviso-de-pauta2.png/@@images/6e3c90e1-788d...

**Query a criar:** _(preencher no JSON)_

---

#### q003 - doc_01_03

**Título:** Portaria interministerial amplia prazo para adesão ao PREPS; confira

**Tipo Sugerido:** `geral`

**Tamanho:** Média (3050 chars)

**Órgão:** mpa

**Keywords Sugeridas:** embarcações, prazo, preps, pesca, monitoramento, novo, transição, partir

**Jargões Encontrados:** ministério, secretaria, portaria

**Preview:**
> O novo prazo estabelece uma transição gradual a partir de 2027
![Portaria interministerial amplia prazo para adesão ao PREPS; confira](https://www.gov.br/mpa/pt-br/assuntos/noticias/portaria-amplia-prazo-adesao-preps/embarcacao.jpeg/@@images/68463d19-f237-4f2c-8ca8-ba576bfe8e44.jpeg)

Após escutar r...

**Query a criar:** _(preencher no JSON)_

---

#### q004 - doc_01_06

**Título:** Acordo põe fim a conflito agrário histórico no oeste do Paraná

**Tipo Sugerido:** `geral`

**Tamanho:** Média (4679 chars)

**Órgão:** agu

**Keywords Sugeridas:** região, acordo, conciliação, famílias, união, federal, regional, paraná

**Jargões Encontrados:** ministério, resolução

**Preview:**
> Conciliação celebrada entre AGU e proprietários de terras vai beneficiar mais de 3 mil famílias de agricultores
![thiarles frança2.jpg](https://www.gov.br/agu/pt-br/comunicacao/noticias/acordo-poe-fim-a-conflito-agrario-historico-no-oeste-do-parana/thiarles-franca2.jpg/@@images/e1620559-8822-40bc-92...

**Query a criar:** _(preencher no JSON)_

---

#### q005 - doc_01_10

**Título:** Microcrédito movimenta R$ 69 milhões em mais de 5 mil novos contratos em janeiro

**Tipo Sugerido:** `geral`

**Tamanho:** Média (3572 chars)

**Órgão:** mdr

**Keywords Sugeridas:** milhões, midr, desde, programa, microcrédito, contratações, 2026, financiamento

**Jargões Encontrados:** ministério, pronaf

**Preview:**
> O número de contratações registrado no primeiro mês de 2026 é o maior desde o lançamento do programa de financiamento em parceria com a Caixa
![Agricultor Freepik (1).jpg](https://www.gov.br/mdr/pt-br/noticias/microcredito-movimenta-r-69-milhoes-em-mais-de-5-mil-novos-contratos-em-janeiro/agricultor...

**Query a criar:** _(preencher no JSON)_

---

#### q006 - doc_01_02

**Título:** Brasil atinge novo recorde na safra de grãos, com 346,1 milhões de toneladas em 2025

**Tipo Sugerido:** `doc_longo`

**Tamanho:** Longa (6426 chars)

**Órgão:** secom

**Keywords Sugeridas:** milhões, toneladas, produção, 2025, grãos, safra, área, anos

**Jargões Encontrados:** sus, embrapa

**Preview:**
> Nos últimos três anos, entre 2023 e 2025, produção de cereais, leguminosas e oleaginosas chegou a 955,23 milhões de toneladas, superando em 199,95 milhões de toneladas o que foi produzido no país entre 2019 e 2022. Dados foram divulgados nesta quinta-feira (15/1), pelo IBGE
![15012026 FOTO SAFRA DE ...

**Query a criar:** _(preencher no JSON)_

---

### Assistência Social

#### q007 - doc_03_02

**Título:** Em documento, governo sintetiza políticas, equipamentos e serviços públicos de proteção social voltados ao povo yanomami

**Tipo Sugerido:** `geral`

**Tamanho:** Curta (2982 chars)

**Órgão:** casacivil

**Keywords Sugeridas:** social, documento, yanomami, direitos, políticas, assistência, humanos, serviços

**Jargões Encontrados:** ministério

**Preview:**
> Políticas de assistência social, de direitos humanos e indigenistas são o foco do documento que pode ser acessado na página da Casa de Governo Yanomami
![Em documento, governo sintetiza políticas, equipamentos e serviços públicos de proteção social voltados ao povo yanomami](https://www.gov.br/casac...

**Query a criar:** _(preencher no JSON)_

---

#### q008 - doc_03_04

**Título:** Sudene e MDS vão lançar projetos de proteção social nos estados do Nordeste

**Tipo Sugerido:** `geral`

**Tamanho:** Curta (2748 chars)

**Órgão:** sudene

**Keywords Sugeridas:** sudene, rede, social, universidades, programa, aprimora, projetos, proteção

**Jargões Encontrados:** ministério, sus

**Preview:**
> Ação faz parte do Programa “Aprimora Rede+”, que será realizado em parceria com universidades federais
![Sudene e MDS vão lançar projetos de proteção social nos estados do Nordeste](https://www.gov.br/sudene/pt-br/assuntos/noticias/sudene-e-mds-vao-lancar-projetos-de-protecao-social-nos-estados-do-n...

**Query a criar:** _(preencher no JSON)_

---

#### q009 - doc_03_00

**Título:** Programa Abdias Nascimento: CAPES publica edital de renovação de projetos para 2026

**Tipo Sugerido:** `geral`

**Tamanho:** Média (3265 chars)

**Órgão:** capes

**Keywords Sugeridas:** capes, educação, programa, imagem, diversidade, abdias, nascimento, deficiência

**Jargões Encontrados:** ministério, secretaria, mec, capes

**Preview:**
> Documento seleciona estudos que abordam diversidade e direitos sociais no contexto nacional

[![Imagem: Imagem ilustrativa (Freepik/design)](https://www.gov.br/capes/pt-br/media/imagem_dentro/MATERIARESULTADORENOVACAOABDIASNASCIMENTO.jpg/@@images/8464c57d-7bd2-4bb3-9b7a-4fc83b3cc53d.jpeg)](/capes/pt...

**Query a criar:** _(preencher no JSON)_

---

#### q010 - doc_03_06

**Título:** MDHC fortalece diálogo sobre envelhecimento da população LGBTQIA+ com o Fonges-LGBT

**Tipo Sugerido:** `geral`

**Tamanho:** Média (3516 chars)

**Órgão:** mdh

**Keywords Sugeridas:** lgbtqia, envelhecimento, população, políticas, públicas, idosa, reunião, direitos

**Jargões Encontrados:** ministério, secretaria

**Preview:**
> Reunião debateu políticas públicas afirmativas, com foco no enfrentamento à discriminação e na inclusão de pessoas idosas LGBTQIA+
![MDHC fortalece diálogo sobre envelhecimento da população LGBTQIA+ com o Fonges-LGBT](https://www.gov.br/mdh/pt-br/assuntos/noticias/2026/fevereiro/mdhc-fortalece-dialo...

**Query a criar:** _(preencher no JSON)_

---

#### q011 - doc_03_07

**Título:** Tesouro Nacional recebe certificado do Pnud e lança estratégia de igualdade de gênero

**Tipo Sugerido:** `geral`

**Tamanho:** Média (4544 chars)

**Órgão:** fazenda

**Keywords Sugeridas:** tesouro, selo, igualdade, gênero, nacional, plano, públicas, ação

**Jargões Encontrados:** ubs

**Preview:**
> Pioneiro órgão do Governo Federal a aderir ao Selo de Igualdade de Gênero para Instituições Públicas apresenta plano de ação estratégico

O Tesouro Nacional recebeu, na quarta-feira (5/2), o certificado de reconhecimento do Programa das Nações Unidas para o Desenvolvimento (Pnud) pelo compromisso pú...

**Query a criar:** _(preencher no JSON)_

---

#### q012 - doc_03_20

**Título:** Estudo mostra que 90% dos cuidadores informais no Brasil são mulheres

**Tipo Sugerido:** `doc_longo`

**Tamanho:** Longa (6638 chars)

**Órgão:** agencia_brasil

**Keywords Sugeridas:** mulheres, trabalho, cuidado, cuidar, porque, tempo, horas, marido

**Jargões Encontrados:** agência

**Preview:**
> As mulheres dedicam, em média, 9,6 horas semanais a mais do que os homens em tarefas domésticas e cuidados, o que representa mais de mil horas dedicadas com o outro - filho, marido, pais - mas não remunerado e invisível socialmente, segundo a Pesquisa Nacional por Amostra de Domicílios de 2022, do I...

**Query a criar:** _(preencher no JSON)_

---

### Ciência e Tecnologia

#### q013 - doc_05_03

**Título:** Inovação normativa da Conitec: entenda o que mudou

**Tipo Sugerido:** `geral`

**Tamanho:** Curta (1255 chars)

**Órgão:** conitec

**Keywords Sugeridas:** conitec, cartilha, inovação, mudanças, decreto, 2025, portaria, material

**Jargões Encontrados:** secretaria, portaria, decreto

**Preview:**
> ![Imagem Cartilha de inovação](https://www.gov.br/conitec/pt-br/assuntos/noticias/2025/dezembro/inovacao-normativa-da-conitec-entenda-o-que-mudou/inovacao-normativa-da-conitec-entenda-o-que-mudou_banner-conitec.png/@@images/944e9f1a-da5b-409e-8467-8dbb76bd88a8.png)

A Secretaria-Executiva da Conitec...

**Query a criar:** _(preencher no JSON)_

---

#### q014 - doc_05_10

**Título:** CBPF abre inscrições abertas para a I Escola Teórica de Campos e Partículas do Rio de Janeiro

**Tipo Sugerido:** `geral`

**Tamanho:** Curta (1413 chars)

**Órgão:** cbpf

**Keywords Sugeridas:** 2026, cbpf, escola, janeiro, fevereiro, teórica, campos, partículas

**Preview:**
> O Centro Brasileiro de Pesquisas Físicas (CBPF) será palco da I Escola Teórica de Campos e Partículas do Rio de Janeiro (EsCamPa 2026-CBPF), que tem como objetivo principal contribuir para a formação de recursos humanos na área.

De 23 de fevereiro a 6 de março, cursos básicos e avançados, além de s...

**Query a criar:** _(preencher no JSON)_

---

#### q015 - doc_05_00

**Título:** Ministra Luciana Santos destaca projeto do Reator Multipropósito Brasileiro, em reunião do CCT

**Tipo Sugerido:** `geral`

**Tamanho:** Média (3469 chars)

**Órgão:** ien

**Keywords Sugeridas:** nacional, ciência, projeto, luciana, santos, tecnologia, encti, cnen

**Jargões Encontrados:** ministério, sus

**Preview:**
> ![Ministra Luciana Santos durante reunião do CCT, em Brasília](https://www.gov.br/ien/pt-br/assuntos/noticias/ministra-luciana-santos-destaca-projeto-do-reator-multiproposito-brasileiro-em-reuniao-do-cct/ministra-luciana-santos-em-reuniao-do-cct.jpeg/@@images/deeccf2c-4677-43ea-9c7f-dae8aae58648.jpe...

**Query a criar:** _(preencher no JSON)_

---

#### q016 - doc_05_01

**Título:** Brasil aprofunda debate sobre responsabilidade civil nuclear em workshop co-organizado pela ANSN e AIEA

**Tipo Sugerido:** `geral`

**Tamanho:** Média (4756 chars)

**Órgão:** ird

**Keywords Sugeridas:** nuclear, ansn, nucleares, nacional, internacional, workshop, regime, responsabilidade

**Jargões Encontrados:** ministério, agência

**Preview:**
> ![workshop_aeia.jpeg](https://www.gov.br/ird/pt-br/assuntos/noticias/noticias-2025/brasil-aprofunda-debate-sobre-responsabilidade-civil-nuclear-em-workshop-co-organizado-pela-ansn-e-aiea/workshop_aeia.jpeg/@@images/7b5bf0b3-a59a-42cd-8a24-5b58edeba4ee.jpeg)

A Autoridade Nacional de Segurança Nuclea...

**Query a criar:** _(preencher no JSON)_

---

#### q017 - doc_05_02

**Título:** Deputado Júlio Lopes propõe transformação da ANSN em Agência Reguladora Nuclear

**Tipo Sugerido:** `geral`

**Tamanho:** Média (4057 chars)

**Órgão:** ird

**Keywords Sugeridas:** nuclear, ansn, agência, deputado, requerimento, segurança, autonomia, técnica

**Jargões Encontrados:** ministério, agência, anvisa

**Preview:**
> ![julio_camara.jpeg](https://www.gov.br/ird/pt-br/assuntos/noticias/noticias-2025/deputado-julio-lopes-propoe-transformacao-da-ansn-em-agencia-reguladora-nuclear/julio_camara.jpeg/@@images/b2dead18-6c7c-43b9-8a64-6eb14fd12459.jpeg)

O deputado federal Júlio Lopes (PP-RJ) apresentou na quarta-feira, ...

**Query a criar:** _(preencher no JSON)_

---

#### q018 - doc_05_13

**Título:** Diretor-Geral do CENSIPAM realiza visita técnica ao Centro Tecnológico da Marinha e ao Instituto de Pesquisa da Marinha no Rio de Janeiro

**Tipo Sugerido:** `doc_longo`

**Tamanho:** Longa (6660 chars)

**Órgão:** censipam

**Keywords Sugeridas:** marinha, censipam, diretor, centro, pesquisa, tecnológicas, cooperação, monitoramento

**Jargões Encontrados:** ministério

**Preview:**
> ![Diretor-Geral do CENSIPAM realiza visita técnica ao Centro Tecnológico da Marinha e ao Instituto de Pesquisa da Marinha no Rio de Janeiro](https://www.gov.br/censipam/pt-br/central-de-conteudos/noticias/diretor-geral-do-censipam-realiza-visita-tecnica-ao-centro-tecnologico-da-marinha-e-ao-institut...

**Query a criar:** _(preencher no JSON)_

---

### Cultura

#### q019 - doc_07_06

**Título:** Mais de 800 obras disputam as premiações do 3º Concurso de Fotos e Vídeos da Anatel

**Tipo Sugerido:** `geral`

**Tamanho:** Curta (2484 chars)

**Órgão:** anatel

**Keywords Sugeridas:** fotos, vídeos, anatel, comissão, julgadora, concurso, categoria, votação

**Jargões Encontrados:** ubs

**Preview:**
> Comissão Julgadora seleciona trabalhos que irão à votação popular entre 3 e 8 de março
![Foto vencedora de 2025, de Josué Castilho dos Santos](https://www.gov.br/anatel/pt-br/assuntos/noticias/mais-de-800-obras-disputam-as-premiacoes-do-3o-concurso-de-fotos-e-videos-da-anatel/02a29f91-125d-468f-8551...

**Query a criar:** _(preencher no JSON)_

---

#### q020 - doc_07_08

**Título:** Mostra vai premiar trabalhos fotográficos e audiovisuais das favelas brasileiras

**Tipo Sugerido:** `geral`

**Tamanho:** Curta (2454 chars)

**Órgão:** cidades

**Keywords Sugeridas:** mostra, periferias, selecionadas, inscrições, audiovisual, fotografias, nacional, ministério

**Jargões Encontrados:** ministério, secretaria

**Preview:**
> Secretaria Nacional de Periferias, do Ministério das Cidades, abre inscrições para a “Mostra Nós
![Na imagem mulher com câmera fotográfica, ao fundo comunidade do Rio de Janeiro](https://www.gov.br/cidades/pt-br/assuntos/noticias-1/noticia-mcid-n-1963/whatsapp-image-2026-02-19-at-18-12-59.jpeg/@@ima...

**Query a criar:** _(preencher no JSON)_

---

#### q021 - doc_07_00

**Título:** Heróis da Pátria são reconhecidos durante 7a edição do Rede Capoeira em Cachoeira (BA)

**Tipo Sugerido:** `geral`

**Tamanho:** Média (5246 chars)

**Órgão:** cultura

**Keywords Sugeridas:** cultura, capoeira, mestres, cachoeira, brasil, evento, popular, rede

**Jargões Encontrados:** ministério

**Preview:**
> Com presença de Margareth Menezes, evento celebrou mestres e mestras da cultura popular com entrega do Troféu Sankofa e programação voltada à transmissão de saberes ancestrais
![Cópia de carrossel (64) (1).png](https://www.gov.br/cultura/pt-br/assuntos/noticias/herois-da-patria-sao-reconhecidos-dura...

**Query a criar:** _(preencher no JSON)_

---

#### q022 - doc_07_02

**Título:** Rumo à 6ª Teia Nacional, Mato Grosso do Sul realiza encontro estadual da rede dos pontos de cultura

**Tipo Sugerido:** `geral`

**Tamanho:** Média (5310 chars)

**Órgão:** culturaviva

**Keywords Sugeridas:** cultura, estado, cultural, mato, evento, grosso, nacional, pontos

**Jargões Encontrados:** ministério, secretaria, sus

**Preview:**
> Estado define delegados e propostas para evento nacional, marcado para maço em Aracruz (ES)
![Cópia de carrossel - 2026-02-03T131203.030 (1).png](https://www.gov.br/culturaviva/pt-br/acesso-a-informacao/noticias/rumo-a-6a-teia-nacional-mato-grosso-do-sul-realiza-encontro-estadual-da-rede-dos-pontos-...

**Query a criar:** _(preencher no JSON)_

---

#### q023 - doc_07_05

**Título:** Seleção TV Brasil anuncia projetos selecionados no maior investimento da história da TV pública no Brasil

**Tipo Sugerido:** `geral`

**Tamanho:** Média (4176 chars)

**Órgão:** cultura

**Keywords Sugeridas:** linha, brasil, pública, edital, processo, projetos, selecionados, programação

**Jargões Encontrados:** ministério, agência, sus

**Preview:**
> ![Seleção TV Brasil anuncia projetos selecionados no maior investimento da história da TV pública no Brasil](https://www.gov.br/cultura/pt-br/assuntos/noticias/selecao-tv-brasil-anuncia-projetos-selecionados-no-maior-investimento-da-historia-da-tv-publica-no-brasil/copia-de-carrossel.jpg/@@images/7f...

**Query a criar:** _(preencher no JSON)_

---

#### q024 - doc_07_03

**Título:** Campanha nacional articula cultura, direitos humanos e combate ao racismo no Carnaval de BH

**Tipo Sugerido:** `doc_longo`

**Tamanho:** Longa (5622 chars)

**Órgão:** mdh

**Keywords Sugeridas:** carnaval, campanha, racismo, mdhc, direitos, blocos, cultura, lançamento

**Jargões Encontrados:** ministério

**Preview:**
> Lançamento da campanha na capital mineira contou com a participação das ministras Macaé Evaristo e Anielle Franco, reforçando o compromisso do Governo do Brasil com um Carnaval democrático, inclusivo e livre de discriminação
![Campanha nacional articula cultura, direitos humanos e combate ao racismo...

**Query a criar:** _(preencher no JSON)_

---

### Economia

#### q025 - doc_09_02

**Título:** Cade seleciona consultor para apoiar elaboração do Guia de Abuso de Poder Econômico

**Tipo Sugerido:** `geral`

**Tamanho:** Curta (2018 chars)

**Órgão:** cade

**Keywords Sugeridas:** cade, abuso, podem, fevereiro, defesa, consultoria, técnica, guia

**Preview:**
> Inscrições podem ser feitas até o dia 17 de fevereiro
![SITE 2026 (6).png](https://www.gov.br/cade/pt-br/assuntos/noticias/cade-seleciona-consultor-para-apoiar-elaboracao-do-guia-de-abuso-de-poder-economico/site-2026-6.png/@@images/6804af79-ad25-46fe-8543-8575d06966e2.png)

O Conselho Administrativo...

**Query a criar:** _(preencher no JSON)_

---

#### q026 - doc_09_03

**Título:** Investimento, indústria e empregos: novas locomotivas impulsionam a ferrovia brasileira

**Tipo Sugerido:** `geral`

**Tamanho:** Curta (2045 chars)

**Órgão:** antt

**Keywords Sugeridas:** milhões, entrega, novas, locomotivas, investimento, minas, gerais, logística

**Jargões Encontrados:** sus, ubs, antt

**Preview:**
> Entrega em Minas Gerais marca aporte de R$ 700 milhões, fortalece a logística nacional e gera impactos diretos na economia e no emprego
![Imagem com IDV padrão da ANTT escrito Aviso de Pauta](https://www.gov.br/antt/pt-br/assuntos/ultimas-noticias/investimento-industria-e-empregos-novas-locomotivas-...

**Query a criar:** _(preencher no JSON)_

---

#### q027 - doc_09_00

**Título:** União honra R$ 11,08 bilhões em dívidas garantidas de entes subnacionais em 2025

**Tipo Sugerido:** `geral`

**Tamanho:** Média (3276 chars)

**Órgão:** tesouronacional

**Keywords Sugeridas:** milhões, total, bilhões, grande, estados, união, estado, garantias

**Jargões Encontrados:** secretaria, sus

**Preview:**
> Rio de Janeiro (R$ 4,69 bilhões, ou 42,35% do total), Minas Gerais (R$ 3,55 bilhões, ou 32,05% do total), Rio Grande do Sul (R$ 1,59 bilhão, ou 14,37% do total) e Goiás (R$ 888,06 milhões, ou 8,01% do total) foram os Estados que tiveram os maiores valores honrados no ano

Em 2025, a União honrou R$ ...

**Query a criar:** _(preencher no JSON)_

---

#### q028 - doc_09_01

**Título:** Ano de 2025 encerra com número recorde de regulados pela CVM

**Tipo Sugerido:** `geral`

**Tamanho:** Média (4070 chars)

**Órgão:** cvm

**Keywords Sugeridas:** 2025, mercado, bilhões, valores, mobiliários, boletim, relação, 2024

**Jargões Encontrados:** ubs, cvm

**Preview:**
> Conjunto de participantes aumentou 3,4% em relação ao final de 2024, totalizando 92.818. Destaque para crescimento de consultores de valores mobiliários

**Número recorde de regulados pela Comissão de Valores Mobiliários (CVM)!** Foi assim que o ano de 2025 terminou, com um **aumento de 3,4%** no co...

**Query a criar:** _(preencher no JSON)_

---

#### q029 - doc_09_04

**Título:** Cade divulga Anuário 2025 com balanço da atuação em defesa da concorrência

**Tipo Sugerido:** `geral`

**Tamanho:** Média (3288 chars)

**Órgão:** cade

**Keywords Sugeridas:** cade, 2025, defesa, publicação, concorrência, autarquia, compromisso, operações

**Jargões Encontrados:** agência

**Preview:**
> Documento consolida resultados, avanços regulatórios e ações estratégicas do Cade no último ano
![2025.png](https://www.gov.br/cade/pt-br/assuntos/noticias/cade-divulga-anuario-2025-com-balanco-da-atuacao-em-defesa-da-concorrencia/2025.png/@@images/f97746a9-8730-4a52-919c-6ff42702b509.png)

O Consel...

**Query a criar:** _(preencher no JSON)_

---

#### q030 - doc_09_09

**Título:** MIDR iniciará escuta ativa de demandas da população do Vale do Jequitinhonha

**Tipo Sugerido:** `doc_longo`

**Tamanho:** Longa (5853 chars)

**Órgão:** mdr

**Keywords Sugeridas:** desenvolvimento, jogo, regional, midr, políticas, nacional, política, além

**Jargões Encontrados:** ministério, secretaria, sus

**Preview:**
> Além disso, serão apresentadas oficinas “Perspectivas para o Desenvolvimento Regional” e “Desenvolvimento em Jogo”
![ValeMG.jpg](https://www.gov.br/mdr/pt-br/noticias/midr-iniciara-escuta-ativa-de-demandas-da-populacao-do-vale-do-jequitinhonha/valemg.jpg/@@images/0ada6388-6edc-4e85-967e-87c3f2e52772...

**Query a criar:** _(preencher no JSON)_

---

### Educação

#### q031 - doc_11_02

**Título:** Vem ser CDTN: seleção aberta para os cursos de Mestrado e Doutorado

**Tipo Sugerido:** `geral`

**Tamanho:** Curta (2629 chars)

**Órgão:** cdtn

**Keywords Sugeridas:** 2026, processo, seletivo, mestrado, doutorado, cdtn, inscrições, vagas

**Jargões Encontrados:** mec, capes

**Preview:**
> Inscrições abertas até o dia 16 de janeiro de 2026 para 65 vagas
![Processo seletivo 2026.1 (Foto Deivid Oliveira)](https://www.gov.br/cdtn/pt-br/centrais-de-conteudo/noticias/vem-ser-cdtn-selecao-aberta-para-os-cursos-de-mestrado-e-doutorado/processo-seletivo-2026-1-foto-deivid-oliveira.jpg/@@image...

**Query a criar:** _(preencher no JSON)_

---

#### q032 - doc_11_04

**Título:** Anvisa conclui curso de formação para novos especialistas em regulação

**Tipo Sugerido:** `geral`

**Tamanho:** Curta (1470 chars)

**Órgão:** anvisa

**Keywords Sugeridas:** encerramento, curso, formação, anvisa, prova, final, regulação, vigilância

**Jargões Encontrados:** agência, anvisa

**Preview:**
> Prova final será aplicada neste domingo (21/12).
![Encerramento do curso de formação](https://www.gov.br/anvisa/pt-br/assuntos/noticias-anvisa/2025/anvisa-conclui-curso-de-formacao-para-novos-especialistas-em-regulacao/54993958229_c611615aa0_c.jpg/@@images/d9a37ecf-f268-4189-8509-39e302c9069d.jpeg)
...

**Query a criar:** _(preencher no JSON)_

---

#### q033 - doc_11_08

**Título:** Programa de Pós-Graduação do CDTN alcança nota 6 na Capes

**Tipo Sugerido:** `geral`

**Tamanho:** Média (3282 chars)

**Órgão:** cdtn

**Keywords Sugeridas:** cdtn, programa, avaliação, nuclear, quadrienal, tecnologia, conceito, graduação

**Jargões Encontrados:** ministério, secretaria, capes

**Preview:**
> O conceito do Programa foi elevado pela segunda vez consecutiva e se refere à Avaliação Quadrienal 2021-2024
![2025-09-10_Escola de Governo_Pós_DeividOliveira (7) v2.JPG](https://www.gov.br/cdtn/pt-br/centrais-de-conteudo/noticias/programa-de-pos-graduacao-do-cdtn-alcanca-nota-6-na-capes/2025-09-10_...

**Query a criar:** _(preencher no JSON)_

---

#### q034 - doc_11_11

**Título:** ANA convoca aprovados em seu concurso público para quinta chamada da segunda turma do curso de formação

**Tipo Sugerido:** `geral`

**Tamanho:** Média (4640 chars)

**Órgão:** ana

**Keywords Sugeridas:** curso, formação, saneamento, básico, matrícula, águas, candidatos, fevereiro

**Jargões Encontrados:** agência

**Preview:**
> ![IMG_7358 (3) (1) (1)_Easy-Resize.com.jpg](https://www.gov.br/ana/pt-br/assuntos/noticias-e-eventos/noticias/ana-convoca-aprovados-em-seu-concurso-publico-para-quinta-chamada-da-segunda-turma-do-curso-de-formacao/img_7358-3-1-1-_easy-resize-com.jpg/@@images/03318582-a841-427b-b0b1-fecf37b35361.jpeg...

**Query a criar:** _(preencher no JSON)_

---

#### q035 - doc_11_12

**Título:** Programa Jovem Cientista da Pesca Artesanal: CNPq e Ministério da Pesca oferecem 700 bolsas para jovens de comunidades pesqueiras

**Tipo Sugerido:** `geral`

**Tamanho:** Média (3680 chars)

**Órgão:** cnpq

**Keywords Sugeridas:** pesca, artesanal, comunidades, artesanais, instituições, pesqueiras, científica, serão

**Jargões Encontrados:** ministério, sus, cnpq

**Preview:**
> Iniciativa visa selecionar instituições para receber bolsas de Iniciação Científica Júnior (ICJ), com financiamento do MPA de R$ 2,5 milhões, serão concedidas por período de 12 meses, a partir de maio de 2026.
![Banner Noticias 780x580 (96).png](https://www.gov.br/cnpq/pt-br/assuntos/noticias/cnpq-e...

**Query a criar:** _(preencher no JSON)_

---

#### q036 - doc_11_00

**Título:** “Governo do Brasil na Rua”: veja os atendimentos e serviços gratuitos que serão levados ao Sol Nascente (DF) neste sábado (13)

**Tipo Sugerido:** `doc_longo`

**Tamanho:** Longa (5577 chars)

**Órgão:** secretariageral

**Keywords Sugeridas:** governo, brasil, serviços, digital, saúde, será, orientações, atendimento

**Jargões Encontrados:** secretaria

**Preview:**
> Saúde, educação, emprego, cultura, direitos, empreendedorismo e cuidado com pets estarão disponíveis para toda a comunidade.
![Governo na Rua - News.jpg](https://www.gov.br/secretariageral/pt-br/noticias/2025/dezembro/201cgoverno-do-brasil-na-rua201d-veja-os-atendimentos-e-servicos-gratuitos-que-ser...

**Query a criar:** _(preencher no JSON)_

---

### Infraestrutura

#### q037 - doc_13_02

**Título:** Implantação de segmento na BR-020/BA chega a 76% de execução

**Tipo Sugerido:** `geral`

**Tamanho:** Curta (2324 chars)

**Órgão:** dnit

**Keywords Sugeridas:** quilômetros, região, piauí, rodovia, metros, importante, estados, bahia

**Jargões Encontrados:** dnit

**Preview:**
> Pavimentação de 11,8 quilômetros beneficia importante ligação entre os estados da Bahia e do Piauí
![Implantação BR-020BA_BR-020 BA - 76 por cento-01.jpg](https://www.gov.br/dnit/pt-br/assuntos/noticias/implantacao-de-segmento-na-br-020-ba-chega-a-76-de-execucao/implantacao-br-020ba_br-020-ba-76-por...

**Query a criar:** _(preencher no JSON)_

---

#### q038 - doc_13_03

**Título:** DNIT executa reconstrução de bueiro hidráulico na BR-174/RR

**Tipo Sugerido:** `geral`

**Tamanho:** Curta (1733 chars)

**Órgão:** dnit

**Keywords Sugeridas:** rodovia, ação, próximo, município, pacaraima, reconstrução, bueiro, hidráulico

**Jargões Encontrados:** dnit

**Preview:**
> A ação é realizada no km 713 da rodovia, próximo ao município de Pacaraima
![Reconstrução de bueiro hidráulico na BR-174/RR](https://www.gov.br/dnit/pt-br/assuntos/noticias/dnit-executa-reconstrucao-de-bueiro-hidraulico-na-br-174-rr/dji_fly_20260129_135552_768_1769709871851_photo-jpg-2.jpeg/@@images...

**Query a criar:** _(preencher no JSON)_

---

#### q039 - doc_13_00

**Título:** Simone Tebet participa da apresentação do contrato de concessão da Rota da Celulose

**Tipo Sugerido:** `geral`

**Tamanho:** Média (3203 chars)

**Órgão:** planejamento

**Keywords Sugeridas:** estado, celulose, mato, grosso, rota, projeto, ministra, ainda

**Preview:**
> Fundamental para a logística da indústria de celulose, projeto amplia a integração regional e melhora as condições de um dos principais corredores rodoviários de Mato Grosso do Sul

[![.](https://www.gov.br/planejamento/pt-br/assuntos/noticias/2026/imagens/WhatsAppImage20260202at15.31.52.jpeg/@@imag...

**Query a criar:** _(preencher no JSON)_

---

#### q040 - doc_13_01

**Título:** As Rotas de Integração Sul-Americana são agora um Programa formal do MPO

**Tipo Sugerido:** `geral`

**Tamanho:** Média (5076 chars)

**Órgão:** planejamento

**Keywords Sugeridas:** rotas, programa, integração, países, articulação, lula, 2023, seai

**Jargões Encontrados:** ministério, secretaria, portaria

**Preview:**
> Portaria assinada pela ministra Simone Tebet formaliza o Programa, criado pelo MPO em 2023 e instituído desde então pelo governo federal

O Programa Rotas de Integração Sul-Americana é formalizado hoje (3/2), [por meio de portaria assinada pela ministra do Planejamento e Orçamento, Simone Tebet, e p...

**Query a criar:** _(preencher no JSON)_

---

#### q041 - doc_13_04

**Título:** AVISO DE PAUTA: Prêmio ANTAQ 2025 acontecerá na próxima terça-feira (10)

**Tipo Sugerido:** `geral`

**Tamanho:** Média (3510 chars)

**Órgão:** antaq

**Keywords Sugeridas:** antaq, categoria, prêmio, aquaviário, serão, empresas, conexão, hidroviária

**Jargões Encontrados:** agência, sus, antaq

**Preview:**
> Este ano, a principal novidade é a criação da categoria Conexão Hidroviária
![Banner - Prêmio ANTAQ 25 - Faltam 5 dias.png](https://www.gov.br/antaq/pt-br/noticias/2026/aviso-de-pauta-premio-antaq-2025-acontecera-na-proxima-terca-feira-10/banner-premio-antaq-25-faltam-5-dias.png/@@images/82c6444e-a4...

**Query a criar:** _(preencher no JSON)_

---

#### q042 - doc_13_05

**Título:** Setor aquaviário brasileiro movimentou, em 2025, 1,4 bi de toneladas

**Tipo Sugerido:** `doc_longo`

**Tamanho:** Longa (8737 chars)

**Órgão:** antaq

**Keywords Sugeridas:** toneladas, milhões, movimentação, antaq, 2025, crescimento, 2024, agência

**Jargões Encontrados:** agência, antaq

**Preview:**
> Dados do ano passado estão consolidados no Painel Estatístico da ANTAQ
![WhatsApp Image 2026-02-10 at 12.39.33.jpeg](https://www.gov.br/antaq/pt-br/noticias/setor-aquaviario-brasileiro-movimentou-em-2025-1-4-bi-de-toneladas/whatsapp-image-2026-02-10-at-12-39-33.jpeg/@@images/c8062dd9-de3f-4041-9227-...

**Query a criar:** _(preencher no JSON)_

---

### Meio Ambiente

#### q043 - doc_15_05

**Título:** Justiça mantém multa aplicada pelo Ibama por pesquisa sísmica sem licença

**Tipo Sugerido:** `geral`

**Tamanho:** Curta (2343 chars)

**Órgão:** agu

**Keywords Sugeridas:** ambiental, infração, empresa, ibama, trf2, milhões, multa, federal

**Jargões Encontrados:** ibama

**Preview:**
> Advocacia-Geral da União confirma no TRF2 a legalidade da fiscalização ambiental e do auto de infração de mais de R$ 4 milhões contra empresa de serviços geofísicos
![sismica1.jpg](https://www.gov.br/agu/pt-br/comunicacao/noticias/justica-mantem-multa-aplicada-pelo-ibama-por-pesquisa-sismica-sem-lic...

**Query a criar:** _(preencher no JSON)_

---

#### q044 - doc_15_11

**Título:** Construção de barragem avança no Rio Grande do Sul

**Tipo Sugerido:** `geral`

**Tamanho:** Curta (2146 chars)

**Órgão:** mdr

**Keywords Sugeridas:** barragem, hídrica, midr, água, arvorezinha, abastecimento, segurança, busca

**Jargões Encontrados:** ministério, secretaria

**Preview:**
> A Barragem de Arvorezinha busca garantir o abastecimento regular de água para mais de cem mil pessoas
![WhatsApp Image 2026-02-02 at 18.58.21.jpeg](https://www.gov.br/mdr/pt-br/noticias/construcao-de-barragem-avanca-no-rio-grande-do-sul/whatsapp-image-2026-02-02-at-18-58-21.jpeg/@@images/7aefe9b7-08...

**Query a criar:** _(preencher no JSON)_

---

#### q045 - doc_15_02

**Título:** Em Belém (PA), Iphan apresenta estudo sobre dinâmicas econômicas associadas ao Círio de Nazaré

**Tipo Sugerido:** `geral`

**Tamanho:** Média (3035 chars)

**Órgão:** iphan

**Keywords Sugeridas:** patrimônio, cultural, pesquisa, economia, sustentabilidade, resultados, cidades, oficinas

**Jargões Encontrados:** sus, ubs

**Preview:**
> Equipe da pesquisa percorre seis cidades para discutir os resultados da Pesquisa Patrimônio Cultural, Economia e Sustentabilidade e oferecer oficinas formativas
![175235e3-3a6c-40f5-96dc-600746ebc8b9.png](https://www.gov.br/iphan/pt-br/assuntos/noticias/em-belem-pa-iphan-apresenta-estudo-sobre-dinam...

**Query a criar:** _(preencher no JSON)_

---

#### q046 - doc_15_03

**Título:** SFB e CNI fortalecem cooperação para Prêmio em Estudos de Economia e Mercado Florestal

**Tipo Sugerido:** `geral`

**Tamanho:** Média (3342 chars)

**Órgão:** florestal

**Keywords Sugeridas:** florestal, setor, brasileiro, prêmio, desenvolvimento, serviço, acordo, diretor

**Jargões Encontrados:** sus, ubs, cnpq

**Preview:**
> Parceria garante novas edições do concurso até 2028 e aproxima pesquisa, setor produtivo e políticas públicas para o desenvolvimento florestal sustentável
![CNI ACT.png](https://www.gov.br/florestal/pt-br/assuntos/noticias/2025/dezembro/sfb-e-cni-fortalecem-cooperacao-para-premio-em-estudos-de-econo...

**Query a criar:** _(preencher no JSON)_

---

#### q047 - doc_15_06

**Título:** Iniciativa do Inpa transforma resíduos de bambu em decoração natalina sustentável

**Tipo Sugerido:** `geral`

**Tamanho:** Média (4782 chars)

**Órgão:** inpa

**Keywords Sugeridas:** bambu, inpa, pesquisadora, materiais, pesquisas, científica, natalina, marilene

**Jargões Encontrados:** sus, mec

**Preview:**
> ![Decoração natalina_bambu_Foto Kaylane Golvin_Ascom Inpa.JPG](https://www.gov.br/inpa/pt-br/assuntos/noticias/2025/iniciativa-do-inpa-transforma-residuos-de-bambu-em-decoracao-natalina-sustentavel/decoracao-natalina_bambu_foto-kaylane-golvin_ascom-inpa.jpg/@@images/65fcceac-900f-45ba-9ad4-90c80820d...

**Query a criar:** _(preencher no JSON)_

---

#### q048 - doc_15_00

**Título:** SFB premia estudos que apontam novos rumos para a recuperação florestal no Brasil

**Tipo Sugerido:** `doc_longo`

**Tamanho:** Longa (6987 chars)

**Órgão:** florestal

**Keywords Sugeridas:** florestal, desenvolvimento, restauração, universidade, brasileiro, manejo, sustentável, lugar

**Jargões Encontrados:** ministério, sus, ubs, icmbio, cnpq

**Preview:**
> Cinco pesquisas inéditas voltadas à restauração dos biomas brasileiros foram reconhecidas na IX edição do Prêmio Serviço Florestal Brasileiro
![Prêmio .PNG](https://www.gov.br/florestal/pt-br/assuntos/noticias/2025/dezembro/sfb-premia-estudos-que-apontam-novos-rumos-para-a-recuperacao-florestal/pre...

**Query a criar:** _(preencher no JSON)_

---

### Saúde

#### q049 - doc_17_02

**Título:** Prorrogado o prazo para envio de textos para a composição do dossiê “Participação e controle social na execução penal”

**Tipo Sugerido:** `geral`

**Tamanho:** Curta (1941 chars)

**Órgão:** senappen

**Keywords Sugeridas:** execução, penal, experiência, conhecimento, interessados, fevereiro, 2026, manuscritos

**Jargões Encontrados:** secretaria

**Preview:**
> Interessados têm até dia 27 de fevereiro de 2026 para encaminhar seus manuscritos
![RBPE_chamamento_1920x1277px_SRBPE_chamamento_1080x1350px_controle_social_prorrogado.png](https://www.gov.br/senappen/pt-br/assuntos/noticias/prorrogado-o-prazo-para-envio-de-textos-para-a-composicao-do-dossie-201cpar...

**Query a criar:** _(preencher no JSON)_

---

#### q050 - doc_17_04

**Título:** CGU e PF apuram irregularidades na área da saúde em Alagoas

**Tipo Sugerido:** `geral`

**Tamanho:** Curta (2663 chars)

**Órgão:** cgu

**Keywords Sugeridas:** ação, alagoas, federal, mandados, irregularidades, saúde, operação, serviços

**Jargões Encontrados:** secretaria, sus, polícia federal

**Preview:**
> Ação também conta com o bloqueio e o sequestro de bens e valores e o afastamento de servidores públicos. Mandados são cumpridos em Alagoas, Pernambuco e no Distrito Federal
![CGU e PF apuram irregularidades na área da saúde em Alagoas](https://www.gov.br/cgu/pt-br/assuntos/noticias/2025/12/cgu-e-pf-...

**Query a criar:** _(preencher no JSON)_

---

#### q051 - doc_17_00

**Título:** Conselho Nacional de Previdência Social: em última reunião do ano, ministro Wolney Queiroz destaca ressarcimento a 4 milhões de aposentados

**Tipo Sugerido:** `geral`

**Tamanho:** Média (3496 chars)

**Órgão:** previdencia

**Keywords Sugeridas:** social, previdência, ministro, queiroz, destacou, peritos, fotos, edson

**Jargões Encontrados:** ministério, polícia federal

**Preview:**
> A contratação de 500 novos peritos médicos federais também foi destacada como grande entrega do Ministério da Previdência Social em 2025
![54977295417_c7bff3c72a_6k.jpg](https://www.gov.br/previdencia/pt-br/noticias/2025/dezembro/conselho-nacional-de-previdencia-social-em-ultima-reuniao-do-ano-minis...

**Query a criar:** _(preencher no JSON)_

---

#### q052 - doc_17_06

**Título:** Projeto promove testagem para ISTs, cuidados com a tuberculose e educação em saúde para comunidade ribeirinha de Rondônia

**Tipo Sugerido:** `geral`

**Tamanho:** Média (3465 chars)

**Órgão:** aids

**Keywords Sugeridas:** saúde, tuberculose, ministério, projetos, ações, organização, opas, visita

**Jargões Encontrados:** ministério, sus

**Preview:**
> Iniciativa realizada por organização da sociedade civil foi selecionada em edital com financiamento do Ministério da Saúde e da Organização Pan-Americana da Saúde (Opas/OMS)

O Ministério da Saúde, em parceria com a Organização Pan-Americana da Saúde (Opas/OMS), realizou a primeira visita de monitor...

**Query a criar:** _(preencher no JSON)_

---

#### q053 - doc_17_07

**Título:** SST Fácil aproxima a ISO 45001 do dia a dia do trabalho

**Tipo Sugerido:** `geral`

**Tamanho:** Média (4209 chars)

**Órgão:** fundacentro

**Keywords Sugeridas:** saúde, segurança, gestão, fácil, 45001, conteúdo, aplicativo, ocupacional

**Preview:**
> Novo conteúdo no aplicativo transforma a norma internacional de saúde e segurança em aprendizado prático, acessível e gratuito
![Card SST Fácil Portal (2).png](https://www.gov.br/fundacentro/pt-br/comunicacao/noticias/noticias/2025/dezembro/sst-facil-aproxima-a-iso-45001-do-dia-a-dia-do-trabalho/car...

**Query a criar:** _(preencher no JSON)_

---

#### q054 - doc_17_08

**Título:** Novo Acordo do Rio Doce promove avanços na reparação aos atingidos

**Tipo Sugerido:** `doc_longo`

**Tamanho:** Longa (8536 chars)

**Órgão:** casacivil

**Keywords Sugeridas:** acordo, milhões, saúde, social, 2025, doce, reparação, bilhões

**Jargões Encontrados:** ministério, secretaria, sus, ubs

**Preview:**
> Com R$ 1,6 bilhão já aplicados na Bacia do Rio Doce, o Acordo avança em ações estruturantes nas áreas de saúde, assistência social e meio ambiente, reforçando o protagonismo das comunidades atingidas
![9b4ca7dd-4bf3-4999-832e-01bba982876b.jpeg](https://www.gov.br/casacivil/pt-br/assuntos/noticias/20...

**Query a criar:** _(preencher no JSON)_

---

### Segurança Pública

#### q055 - doc_19_17

**Título:** Susep orienta população após fortes chuvas em Minas Gerais

**Tipo Sugerido:** `geral`

**Tamanho:** Curta (2614 chars)

**Órgão:** susep

**Keywords Sugeridas:** seguros, autarquia, susep, consumidor, atendimento, representantes, setor, canais

**Jargões Encontrados:** ministério, sus

**Preview:**
> Autarquia reúne representantes do setor, que reforça canais de informação para segurados
![imagem (23).jpg](https://www.gov.br/susep/pt-br/central-de-conteudos/noticias/2026/marco/susep-orienta-populacao-apos-fortes-chuvas-em-minas-gerais/imagem-23.jpg/@@images/e460b2cf-5126-434b-a3ac-0ad962be1fc3.j...

**Query a criar:** _(preencher no JSON)_

---

#### q056 - doc_19_24

**Título:** Cade condena representado em processo de cartel em licitações de aeroportos

**Tipo Sugerido:** `geral`

**Tamanho:** Curta (2761 chars)

**Órgão:** cade

**Keywords Sugeridas:** cade, federal, públicas, tribunal, administrativo, processo, representado, multa

**Jargões Encontrados:** ministério

**Preview:**
> Além de multa, o administrador está proibido de participar de concorrências públicas pelo prazo de 5 anos
![banner-site.png](https://www.gov.br/cade/pt-br/assuntos/noticias/cade-condena-representado-em-processo-de-cartel-em-licitacoes-de-aeroportos/banner-site.png/@@images/3c265c3b-6637-4d8b-b766-7e...

**Query a criar:** _(preencher no JSON)_

---

#### q057 - doc_19_00

**Título:** Megaoperação: Anatel e Receita Federal apreendem quase meio milhão de produtos irregulares no Porto de Imbituba (SC)

**Tipo Sugerido:** `geral`

**Tamanho:** Média (3811 chars)

**Órgão:** anatel

**Keywords Sugeridas:** produtos, ação, anatel, consumidor, federal, órgãos, irregulares, fiscalização

**Jargões Encontrados:** agência

**Preview:**
> Ação conjunta resultou na maior apreensão de produtos não homologados já registrada em parceria entre os órgãos; equipamentos irregulares representam risco ao consumidor
![rês homens com camisetas pretas da "FISCALIZAÇÃO FEDERAL" e logotipo da Anatel observam um armazém repleto de pilhas de caixas g...

**Query a criar:** _(preencher no JSON)_

---

#### q058 - doc_19_04

**Título:** Justiça condena empresa a ressarcir pensão por morte ao INSS

**Tipo Sugerido:** `geral`

**Tamanho:** Média (3305 chars)

**Órgão:** agu

**Keywords Sugeridas:** federal, trabalho, inss, civil, caso, acidente, construção, campo

**Jargões Encontrados:** decreto, mec

**Preview:**
> AGU garantiu vitória à autarquia em caso de acidente de trabalho com fatalidade na construção civil em Campo Grande (MS)
![Construção civil-Freepik.jpg](https://www.gov.br/agu/pt-br/comunicacao/noticias/justica-condena-empresa-a-ressarcir-pensao-por-morte-ao-inss/construcao-civil-freepik.jpg/@@ima...

**Query a criar:** _(preencher no JSON)_

---

#### q059 - doc_19_05

**Título:** Regiões Nordeste e Sul são monitoradas pelo MIDR após previsão de chuvas intensas

**Tipo Sugerido:** `geral`

**Tamanho:** Média (4088 chars)

**Órgão:** mdr

**Keywords Sugeridas:** defesa, civil, alerta, alertas, áreas, risco, midr, nacional

**Jargões Encontrados:** ministério, secretaria, mec

**Preview:**
> Departamento de Preparação e Socorro elevou o nível operacional para laranja (alerta)
![adege-rain-shower-8107685_1280.jpg](https://www.gov.br/mdr/pt-br/noticias/regioes-nordeste-e-sul-sao-monitoradas-pelo-midr-apos-previsao-de-chuvas-intensas/adege-rain-shower-8107685_1280.jpg/@@images/d2f14b19-0aa...

**Query a criar:** _(preencher no JSON)_

---

#### q060 - doc_19_01

**Título:** Wellington César Lima e Silva toma posse no MJSP e defende atuação integrada de combate ao crime organizado

**Tipo Sugerido:** `doc_longo`

**Tamanho:** Longa (6210 chars)

**Órgão:** mj

**Keywords Sugeridas:** ministro, pública, silva, segurança, estado, ministério, lima, justiça

**Jargões Encontrados:** ministério, secretaria, mec

**Preview:**
> Jurista com trajetória no Ministério Público, na Presidência da República e na Petrobras passa a comandar a Pasta após a saída do ministro Ricardo Lewandowski
![WhatsApp Image 2026-01-15 at 18.52.33.jpeg](https://www.gov.br/mj/pt-br/assuntos/noticias/wellington-cesar-lima-e-silva-toma-posse-no-mjsp-...

**Query a criar:** _(preencher no JSON)_

---


## 💡 Exemplos de Boas Queries

### Queries Gerais (linguagem natural):
```
✅ "vacinação infantil obrigatória"
✅ "atendimento hospital público fila"
✅ "nota enem para medicina universidade"
✅ "inflação preços supermercado"
```

### Queries com Jargão BR (termos técnicos):
```
✅ "ANVISA registro medicamento genérico"
✅ "SUS atenção básica UBS cobertura"
✅ "ENEM SISU FIES Prouni inscrição"
✅ "IPCA SELIC COPOM taxa juros"
✅ "PRONAF crédito rural agricultura familiar"
```

### Queries para Docs Longos (complexas):
```
✅ "impacto reforma tributária desenvolvimento regional"
✅ "política ambiental desmatamento Amazônia preservação"
✅ "investimento infraestrutura portos aeroportos concessões"
```

---

## 🚀 Próximos Passos

1. **Edite `query_template.json`** e preencha o campo `"query_text"` para cada query
2. **Execute o script de validação** (será criado) para verificar queries
3. **Anote relevâncias** - marcar quais dos 250 docs são relevantes para cada query

---

**Data de Criação:** 24/03/2026
