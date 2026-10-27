# LOT e NeOn como base metodológica do AKME

Relatório de pesquisa produzido pelo agente `pesquisador-lot-neon`. Serve de insumo direto para o `SKILL.md` e o `manifest.yml` do akme-template. A skill não deve conter etapas que não estejam descritas aqui.

## Nota sobre o artigo primário

O DOI 10.1177/22104968261465514 resolve para o artigo "Large Language Models for Ontology Engineering: A Systematic Literature Review", de Jiayi Li, Daniel Garijo e María Poveda-Villalón, Semantic Web 17(4), 2026 (cópia CC BY-NC em `docs/research/sources/neon-lot.pdf`, texto extraído em `docs/research/sources/neon-lot.txt`). Não é um artigo que proponha uma combinação de NeOn com LOT como metodologia nova. É uma revisão sistemática de 36 artigos (49 estudos em nível de tarefa) sobre uso de LLMs em engenharia de ontologias. A combinação NeOn + LOT aparece na seção 2.1 ("Ontology Development Tasks") como arcabouço de classificação: o fluxo do LOT dá as fases e o glossário da NeOn supre as atividades que o LOT não detalha. Ao longo deste relatório, "artigo primário" refere-se a esse texto. As fases e artefatos do LOT vêm do paper do LOT de 2022 e do site lot.linkeddata.es. Os cenários e o glossário da NeOn vêm do paper de 2009 de Gómez-Pérez e Suárez-Figueroa, do paper LREC 2008 e das fichas da NeOn arquivadas pela Open University.

Convenção: quando uma afirmação não vem de uma fonte efetivamente lida, ela está marcada com `needs_validation`.

## 1. Como o artigo combina NeOn e LOT

### 1.1 O que o artigo faz com cada metodologia

O artigo primário, seção 2.1, explica a escolha assim:

- Metodologias tradicionais (METHONTOLOGY, On-To-Knowledge, DILIGENT, Ontology Development 101) seguem fluxos passo a passo que não cobrem bem reuso, colaboração e interoperabilidade. A NeOn trouxe uma abordagem "mais dinâmica e flexível", voltada a redes de ontologias, com mecanismos de importação, versionamento, mapeamento e modularização (artigo primário, seção 2.1).
- Para ter "um grupo básico de atividades" o artigo segue o fluxo geral do LOT, porque o LOT inclui as fases de publicação e manutenção (artigo primário, seção 2.1).
- Atividades que aparecem nos trabalhos revisados mas não são definidas em detalhe no LOT são tomadas do NeOn Glossary of Activities (Suárez-Figueroa e Gómez-Pérez, 2008). Dois casos explícitos: "CQ reverse engineering", alinhada à "Ontological Resource Reverse Re-engineering" da NeOn, e "Matching", cuja definição é citada literalmente do glossário NeOn (artigo primário, seção 2.1).
- O artigo avisa que tanto LOT quanto NeOn definem mais atividades do que as listadas; só entram na seção 2.1 as encontradas nos papers revisados (artigo primário, seção 2.1).

Resumo da divisão de trabalho que o artigo faz:

| Metodologia | O que fornece ao artigo | O que a outra não cobre |
|---|---|---|
| LOT | As quatro fases (especificação de requisitos, implementação, publicação, manutenção) e a ordem delas | NeOn não tem fase de publicação na Web nem de manutenção como fase do fluxo base |
| NeOn | Glossário com definições precisas de atividades (matching, reverse engineering, etc.) e os 9 cenários de reuso | LOT não detalha matching, re-engenharia, localização, modularização |

### 1.2 Como o próprio LOT se posiciona frente à NeOn

O paper do LOT (2022) confirma a relação de dependência, agora do lado do LOT:

- "A metodologia LOT constrói sobre as atividades de engenharia ontológica definidas na metodologia NeOn quando disponíveis" (paper do LOT, seção 3).
- O template de ORSD do LOT "é uma adaptação do ORSD proposto na metodologia NeOn", com campos tornados opcionais, por exemplo "usuários finais" e o pré-glossário de termos com frequências (paper do LOT, seção 3.1.6).
- As definições de "ontology requirements specification", "ontology implementation", "ontology reuse" e "ontology evaluation" no LOT citam Suárez-Figueroa et al. 2015, isto é, a NeOn (paper do LOT, seções 3.1, 3.2, 3.2.3, 3.2.4).
- Críticas do LOT à NeOn: gera documentação demais, o que faz com que na prática não seja seguida como está; propostas datadas; o NeOn Toolkit foi descontinuado (paper do LOT, seção 2).
- O que o LOT acrescenta: publicação segundo boas práticas da Web Semântica e princípios FAIR; alinhamento com sprints e integração contínua; três formas de escrever requisitos (CQs, frases em linguagem natural, tabelas no estilo METHONTOLOGY) em vez de uma só; template de requisitos com rastreabilidade; recomendações de ferramentas por atividade (paper do LOT, seções 2 e 3).

### 1.3 Onde há evidência de uso de LLM (artigo primário, seções 4 e 5)

Distribuição dos 49 estudos em nível de tarefa (artigo primário, seção 4.1.5 e Tabela 1):

| Fase (LOT) | Atividade (seção 2.1 do artigo) | Origem da definição | Estudos |
|---|---|---|---|
| Especificação de requisitos | Functional requirement writing | LOT/NeOn | 2 |
| Especificação de requisitos | CQ reverse engineering | NeOn (reverse re-engineering) | 7 |
| Especificação de requisitos | Requirement formalization | LOT (formalização opcional em testes) | 3 |
| Implementação | Conceptualization | LOT/NeOn | 11 |
| Implementação | Encoding | LOT | 11 |
| Implementação | Matching | NeOn (citação literal do glossário) | 5 |
| Implementação | Evaluation | LOT/NeOn | 4 |
| Publicação | Documentation | LOT | 5 |
| Manutenção | Bug detection | LOT | 1 |

Conclusões da seção 5.1 do artigo primário que importam para o desenho da skill:

- Implementação (conceitualização e codificação) concentra a pesquisa; avaliação, documentação e manutenção são pouco exploradas.
- Avaliação "exige verificação estrita de consistência lógica, que excede a capacidade intrínseca de raciocínio dos LLMs sem mecanismos externos de validação como verificadores de regras ou revisão por especialistas" (artigo primário, seção 5.1).
- Manutenção depende de integração dinâmica de conhecimento; LLMs são estáticos (artigo primário, seção 5.1).
- Recomendação: fluxos híbridos que integrem conteúdo gerado por LLM com motores de raciocínio formal, RAG para manter conhecimento atual, e fluxos centrados no humano em que o LLM assiste especialistas em validação e refinamento (artigo primário, seções 5.1 e 5.2).
- Só 6 dos 49 estudos envolvem humanos explicitamente (artigo primário, seção 4.2.5 e Tabela 2). O artigo chama isso de lacuna e pede frameworks sistemáticos para integrar validação humana (seção 5.2).

## 2. Fases e atividades

### 2.1 LOT: fluxo base

O LOT define iterações sobre um fluxo de quatro atividades: (1) especificação de requisitos ontológicos, (2) implementação, (3) publicação, (4) manutenção (paper do LOT, seção 3, Figura 1). Papéis: desenvolvedor de ontologia, especialista de domínio, usuário da ontologia (inclui desenvolvedores de software que a consomem) (paper do LOT, seção 3).

| Fase | Entrada | Saída | Atores |
|---|---|---|---|
| Especificação de requisitos | Documentação e dados de especialistas e usuários | ORSD | Desenvolvedores, usuários, especialistas |
| Implementação | ORSD, documentação de dados e exemplos | Ontologia (nova versão por iteração) | Desenvolvedores, usuários, especialistas |
| Publicação | Ontologia avaliada | Ontologia online (arquivo e documentação HTML) | Desenvolvedores (e especialistas na documentação) |
| Manutenção | Ontologia online, ORSD, documentação | Issues, bugs, novos requisitos | Desenvolvedores, usuários, especialistas |

Fonte: paper do LOT, Figuras 1, 2, 8, 10 e 11; site lot.linkeddata.es.

### 2.2 LOT: subatividades da especificação de requisitos

Fonte: paper do LOT, seção 3.1 e Figura 2.

| Subatividade | Entrada | Saída | Quem | Observações |
|---|---|---|---|---|
| Use case specification | Reuniões com especialistas e usuários | Lista de casos de uso (nome, descrição, atores, fluxo) | Dev, usuários, especialistas | Recomendada em todo projeto; pelo menos esta ou a seguinte deve ser feita |
| Data exchange identification | Datasets, normas, padrões, formatos, APIs, esquemas de BD | Conjunto de documentos e recursos do domínio | Usuários (devs de software) entregam ao time | 12 dos 18 projetos do LOT partiram de fontes de dados, esquemas ou APIs (seção 5.1) |
| Purpose and scope identification | Casos de uso e documentação | Documento de propósito e escopo, podendo incluir requisitos não funcionais (idioma, multilinguismo, linguagem ou perfil OWL) | Dev com usuários e especialistas | |
| Functional ontological requirements proposal | Propósito, escopo, casos de uso, dados | Requisitos funcionais em uma ou mais formas: CQs, frases em linguagem natural, tabelas (conceitos, relações, atributos) | Principalmente dev, apoiado por usuários e especialistas | Ver seção 4.1 deste relatório |
| Functional ontological requirements completion | Requisitos propostos | Requisitos verificados e priorizados | Especialistas e usuários com o time | Critérios de Grüninger e Fox: correto, completo, consistente, verificável, compreensível, não ambíguo, conciso |
| ORSD formalization | Propósito e escopo, requisitos verificados | ORSD (template docx e tex no GitHub do LOT) | Dev | Adaptação do ORSD da NeOn |
| Functional ontology requirements formalisation (opcional) | Requisitos verificados | Test suite: id do requisito, descrição com link ao ORSD, SPARQL extraído da CQ e resultado esperado, ou expressões de teste em RDF segundo a ontologia VTC | Dev | Executada depois, na avaliação; dá rastreabilidade |

### 2.3 LOT: subatividades da implementação

Fonte: paper do LOT, seção 3.2 e Figura 8. A implementação ocorre em sprints; cada iteração implementa um subconjunto priorizado de requisitos e produz uma nova versão da ontologia. Requisitos podem ser modificados ou adicionados durante o desenvolvimento.

| Subatividade | Entrada | Saída | Quem | Observações |
|---|---|---|---|---|
| Ontology conceptualization | ORSD, documentação de dados e exemplos | Modelo da ontologia (diagramas, notação Chowlk, UML_Ont ou ER) | Dev, usuários, especialistas | Elementos identificados incrementalmente: classes, hierarquias de classes, relações (atenção a part-of e n-árias), atributos, hierarquias de propriedades, axiomas adicionais. Só o desenvolvedor adiciona termos |
| Ontology reuse | Modelo conceitual, ORSD | Termos e ontologias reutilizadas (hard ou soft reuse) | Dev | Atravessa conceitualização, codificação e avaliação; ver seção 4.2 |
| Ontology encoding | Modelo conceitual, ontologias reutilizadas | Código da ontologia (OWL/RDF(S)) com metadados: creator, title, publisher, license, version, e metadados por termo | Dev | Pode ser semi-automático (hierarquia em OWL, tesauro em SKOS). Definir convenção de versionamento (semver) para todos os artefatos |
| Ontology evaluation | Código da ontologia, ORSD, test suite | Ontologia avaliada | Dev, usuários, especialistas | Validação (significado versus modelo pretendido) e verificação (ontologia versus ORSD e CQs). Resultado pode devolver o time à conceitualização ou à codificação |

### 2.4 LOT: subatividades da publicação

Fonte: paper do LOT, seção 3.3 e Figura 10.

| Subatividade | Entrada | Saída | Quem | Observações |
|---|---|---|---|---|
| Propose release candidate | Ontologia avaliada | Release candidate ou pré-release | Dev | Decisão de publicar na Web, compartilhar com parceiros ou documentar por outra razão |
| Ontology documentation | Código da ontologia, requisitos, testes, exemplos, diagramas | Documentação HTML: descrição de classes e propriedades, metadados (licença, título, criador, publisher, datas, versão), propósito e escopo, diagramas, exemplos de uso, lista de requisitos e de casos de teste | Dev com especialistas | Descrições de termos normalmente vão como anotações no OWL. Gerar exemplos depois da avaliação |
| Online publication | Documentação e arquivo | Ontologia online na URI, com negociação de conteúdo | Dev | Pode ser omitida se a ontologia não for pública; as duas anteriores continuam recomendadas |

### 2.5 LOT: manutenção

Fonte: paper do LOT, seção 3.4 e Figura 11. As caixas internas são situações a que o time reage, não atividades que executa.

| Situação | Entrada | Saída | Quem |
|---|---|---|---|
| Bug detection (inclui sugestões e melhorias) | Ontologia online, documentação, relatos de quem detectou | Issue registrada; correção agendada em sprint ou nova revisão | Dev, usuários, especialistas, comunidade |
| New requirements | Idem | Issue registrada; novo requisito entra no ORSD e numa iteração | Idem |

Recomendação explícita: rastrear requisitos, bugs e sugestões em issue tracker, de preferência aberto (paper do LOT, seção 3.4 e 4.4).

### 2.6 NeOn: cenário 1 e atividades centrais

Fonte: paper dos cenários (2009), seção 4; ficha ORSD da NeOn (D5.4.1).

| Atividade | Entrada | Saída | Quem | Quando |
|---|---|---|---|---|
| Knowledge acquisition | Fontes do domínio | Conhecimento para as demais atividades | Time | Durante todo o desenvolvimento |
| Ontology requirements specification | Conjunto de necessidades ontológicas | ORSD: propósito, escopo, linguagem de implementação, usuários finais, usos pretendidos, requisitos não funcionais, requisitos funcionais em grupos de CQs com respostas, pré-glossário de termos com frequências e objetos | Time de desenvolvimento com usuários e especialistas | Início do projeto, em paralelo com aquisição de conhecimento |
| Quick search for knowledge resources | Termos do ORSD | Conhecimento dos recursos disponíveis para reuso | Time | Logo após o ORSD |
| Scheduling | ORSD e resultado da busca | Plano do projeto | Time | Antes da conceitualização |
| Conceptualization, formalization, implementation | ORSD, plano | Ontologia | Time | Seguindo METHONTOLOGY ou On-To-Knowledge |

Tarefas da especificação de requisitos na NeOn (ficha D5.4.1): (1) identificar propósito, escopo e linguagem; (2) identificar usuários finais; (3) identificar usos pretendidos; (4) identificar requisitos, divididos em não funcionais e funcionais; (5) agrupar requisitos; (6) validar o conjunto (volta à tarefa 4 se inválido); (7) priorizar; (8) extrair terminologia e frequência. O ORSD serve para três coisas: dizer que conhecimento representar, focar a busca por recursos reutilizáveis e permitir a verificação da ontologia contra os requisitos.

### 2.7 NeOn: glossário de atividades

O glossário NeOn foi construído por consenso entre 25 pessoas de 9 instituições, em três rodadas, com um template por atividade contendo: nome, definição, tipo segundo a classificação IEEE (gestão, pré-desenvolvimento, desenvolvimento, pós-desenvolvimento, suporte), entradas, saídas, referências, comentários (paper LREC 2008, seção 2). A versão de 2008 tinha 53 atividades; a ficha posterior da NeOn fala em 59 definições, com notas sobre atividades semelhantes e sinônimos. Lista das 53 atividades (paper LREC 2008, Tabela 2), com "O." significando "Ontology":

O. Aligning; O. Annotation; O. Assessment; O. Comparison; O. Conceptualization; O. Configuration Management; Control; O. Customization; O. Diagnosis; O. Documentation; O. Elicitation; O. Enrichment; O. Environment Study; O. Evaluation; O. Evolution; O. Extension; O. Feasibility Study; O. Formalization; O. Forward Engineering; O. Implementation; O. Integration; Knowledge Acquisition for Ontologies; O. Learning; O. Localization; O. Mapping; O. Matching; O. Merging; O. Modification; O. Modularization; O. Module Extraction; O. Partitioning; O. Population; O. Pruning; O. Quality Assurance; Non Ontological Resource Reengineering; O. Reengineering; O. Restructuring; O. Repair; Non Ontological Resource Reuse; O. Reuse; O. Reverse Engineering; Scheduling; O. Search; O. Selection; O. Specialization; O. Specification; O. Summarization; O. Translation; O. Update; O. Upgrade; O. Validation; O. Verification; O. Versioning.

Definições efetivamente lidas (as demais não foram lidas; o PDF do glossário em neon-project.org está fora do ar e a cópia do Wayback não retornou o arquivo):

- Ontology Matching: "a atividade de encontrar ou descobrir relações ou correspondências entre entidades de ontologias ou módulos de ontologias diferentes" (citada no artigo primário, seção 2.1).
- Ontology Modularization: identificar um ou mais módulos em uma ontologia para apoiar reuso ou manutenção; distingue-se Module Extraction de Partitioning (ficha NeOn do glossário).
- Ontology Module Reuse: usar módulos de ontologias na solução de problemas diferentes (ficha NeOn do glossário).
- Non-ontological Resource Reuse: tomar recursos não ontológicos (bases de dados, vocabulários controlados, etc.) disponíveis para o desenvolvimento de ontologias (ficha NeOn do glossário).
- Ontological resource re-engineering: composta de reverse engineering, restructuring e forward engineering, em quatro níveis possíveis (especificação, conceitualização, formalização, implementação) (paper dos cenários 2009, cenário 4).
- Ontology Reuse, Ontology Evaluation, Ontology Implementation, Ontology Requirements Specification: definições reproduzidas no paper do LOT, seções 3.1, 3.2, 3.2.3, 3.2.4, citando NeOn 2015.

## 3. Os 9 cenários da NeOn

Fonte: paper dos cenários (Gómez-Pérez e Suárez-Figueroa, 2009), seções 4 e 5, e ficha "Scenarios for Building Ontology Networks" da NeOn. Os cenários podem ser combinados; toda combinação inclui o cenário 1, que contém as atividades centrais. Há guias prescritivos para os cenários 1 (especificação e scheduling), 2, 3, 7, 8 (modularização) e 9, além de avaliação e evolução.

| Cenário | Quando se aplica | Exemplo |
|---|---|---|
| 1. From specification to implementation | Construção do zero, sem reuso. Aquisição de conhecimento durante todo o processo, ORSD, busca rápida por recursos, scheduling, depois conceitualização, formalização e implementação | Ontologia de faturamento farmacêutico da NeOn (base dos demais cenários do caso); ontologia SEEMP (fonte: paper 2009, seção 5) |
| 2. Reusing and re-engineering non-ontological resources (NORs) | Existem glossários, tesauros, esquemas de classificação, bases de dados ou padrões no domínio; decide-se pelo ORSD quais reutilizar e re-engenheirá-los em ontologias | Faturamento: UBL, EDIFACT, xCBL. SEEMP: NACE, ISCO-88, ISO 3166 e classificações dos serviços de emprego (paper 2009, seção 5) |
| 3. Reusing ontological resources | Existem ontologias que podem ser reutilizadas como um todo, por módulo ou por sentença (triple); termos do ORSD guiam a busca | Faturamento: conceitos gerais de SUMO, DOLCE e W3C Time (paper 2009, seção 5) |
| 4. Reusing and re-engineering ontological resources | A ontologia reutilizada precisa ser transformada antes da integração, por exemplo mudar de linguagem de implementação; reverse engineering, restructuring, forward engineering | SEEMP: ontologia de tempo DAML re-engenheirada (paper 2009, seção 5) |
| 5. Reusing and merging ontological resources | Várias ontologias do mesmo domínio foram selecionadas e quer-se criar uma nova a partir delas, ou apenas estabelecer alinhamentos para formar a rede | SEEMP: alinhamentos entre cada ontologia local e a ontologia de referência (paper 2009, seção 5) |
| 6. Reusing, merging and re-engineering ontological resources | Como o 5, mas o resultado da fusão é re-engenheirado antes de integrar ao cenário 1 | Exemplo construído pelo autor deste relatório, não vem da fonte: fundir duas ontologias de sensores e reescrever o resultado no perfil OWL exigido pelo projeto |
| 7. Reusing ontology design patterns (ODPs) | Para reduzir dificuldade de modelagem, acelerar ou checar decisões de modelagem, consultando repositórios de ODPs (ontologydesignpatterns.org) | Exemplo construído pelo autor deste relatório: usar o padrão de n-ary relation para modelar uma observação com valor, unidade e instante |
| 8. Restructuring ontological resources | Modularizar, podar ramos desnecessários, estender em largura ou especializar ramos com mais granularidade | Faturamento: ontologia geral de fatura especializada para cada laboratório (paper 2009, seção 5) |
| 9. Localizing ontological resources | Adaptar a ontologia a outras línguas e culturas, traduzindo todos os rótulos; produz ontologia multilíngue | Faturamento: usuários em regiões da Espanha com línguas diferentes (paper 2009, seção 5) |

Relevância para o artigo primário: entre os 9 cenários, o único com evidência direta de LLM na revisão é o que envolve matching e alinhamento (cenários 3, 5 e 6, via a atividade "Matching", 5 estudos) e o reuso apoiado por LLM na extração de características de ontologias existentes (Kholmska et al. 2024, passos 4 e 6, artigo primário, seção 4.2.4). Não há estudo revisado sobre localização (9), modularização (8), ODPs (7) ou re-engenharia de NORs (2) (artigo primário, Tabela 1).

## 4. Como o LOT trata cada tema

### 4.1 Requisitos: ORSD e competency questions

Fonte: paper do LOT, seção 3.1; site lot.linkeddata.es.

- O LOT não impõe CQs. Três técnicas, combináveis: CQs (com respostas ou resultados esperados), frases afirmativas ou negativas em linguagem natural, e tabelas no estilo METHONTOLOGY (conceitos, relações, atributos) (seção 3.1.4).
- Recomendações explícitas: evitar CQs quando os especialistas não conhecem geração e consulta de dados ontológicos; usar tabelas quando há dados estruturados ou APIs, ou colaboração próxima com desenvolvedores de software (seção 3.1.4, Tip).
- O corpus CORAL dá um dicionário de padrões léxico-sintáticos e 834 requisitos reais anotados; expressões ambíguas (por exemplo o verbo "ter", que pode virar datatype property ou object property) devem ser evitadas porque dificultam a formalização (seção 3.1.4).
- Se os requisitos estão em CQs ou frases, podem ser armazenados em tabela com: identificador único, domínio, texto, resposta, status (Proposed, Accepted, Rejected, Pending, Deprecated, Superseded), identificador do requisito que o substitui, comentários, proveniência, prioridade (High, Medium, Low) (seção 3.1.4).
- Validação pelos critérios de Grüninger e Fox (seção 3.1.5), feita por especialistas e usuários com o time. Priorização permite planejar sprints.
- ORSD: armazena requisitos funcionais e não funcionais; template docx e tex em github.com/oeg-upm/LOT-resources; "usuários" e pré-glossário com frequências são opcionais no LOT; se há tabelas, o pré-glossário não é necessário (seção 3.1.6).
- Formalização opcional em test cases (id do requisito, descrição com link ao ORSD, SPARQL com resultado esperado, ou expressões de teste em RDF segundo a ontologia Verification Test Case, w3id.org/def/vtc). Os testes rodam na avaliação e dão rastreabilidade (seção 3.1.7).
- Ferramentas: planilhas colaborativas, wikis e Confluence para elicitação; o ORSD deve ir para o repositório git da ontologia (seção 4.1).

### 4.2 Reuso

Fonte: paper do LOT, seção 3.2.3 e 4.2.

- Reuso favorece interoperabilidade e consultas federadas.
- Hard reuse: `owl:imports`, ontologia inteira, transitivo; mudanças na ontologia importada se refletem (se usada a IRI da ontologia e não de versão); se ela sair do ar, perdem-se as sentenças.
- Soft reuse: referência às URIs de elementos, com quatro variantes: referência direta; generalização ou especialização de elemento referenciado; reprodução de subparte; replicar o elemento no próprio namespace e ligar com `owl:equivalentClass` ou similar, mantendo proveniência. Partes reutilizadas ficam estáveis, mas pode-se perder a ligação com a evolução do original.
- Reuso de ODPs segue a NeOn (portal ontologydesignpatterns.org).
- Quando ocorre: pode ser considerado na especificação (condições para reuso), acontece na implementação (conceitualização identifica candidatos, codificação faz o reuso, avaliação checa uso correto dos termos reutilizados) e na manutenção (adotar ou abandonar ontologias reutilizadas).
- Tip do LOT: não buscar ontologias exaustivamente a partir dos requisitos; começar a conceitualização considerando só as ontologias que o time já conhece (por exemplo SSN/SOSA, SAREF) e buscar reuso quando houver uma primeira conceitualização estável.
- Dificuldades conhecidas: heterogeneidade de língua e de conceitos, documentação deficiente, importações indisponíveis, licença ausente.
- Registros: LOV, Ontohub, BARTOC, LOV4IoT, Vocabularies for Open Data for Cities, BioPortal, OntoBee, AgroPortal (seção 4.2).

### 4.3 Implementação

Fonte: paper do LOT, seções 3.2, 4.2.

- Sprints com subconjunto priorizado de requisitos; saída de cada sprint é uma versão.
- Conceitualização por diagramas (Chowlk, que converte diagramas diagrams.net em OWL; WebVOWL; OWLGred; Graffoo; Gra.fo; OWLAx). Em todos os 18 projetos usou-se notação baseada em UML (seção 5.1).
- Codificação com editores (Protégé, WebProtégé, Fluent Editor, TopBraid Composer, PoolParty); metadados obrigatórios no código; convenção de versionamento inspirada em semver para todos os artefatos.
- Avaliação: validação e verificação; critérios de cobertura de domínio, adequação ao propósito, más práticas, consistência lógica; ferramentas: reasoners (Pellet, HermiT), OOPS! para pitfalls, Themis para executar testes dos requisitos (API REST, linguagem de teste por padrões léxico-sintáticos), TDDOnto2, OntoCheck, consultas SPARQL. Tip: executar SPARQL ou testes ajuda especialistas a achar mal-entendidos; quando só há desenvolvedores, verificação e análise de cobertura de dados são a prática comum.

### 4.4 Publicação

Fonte: paper do LOT, seções 3.3 e 4.3.

- Três subatividades: propor release candidate, documentar, publicar online.
- Documentação segundo as boas práticas FAIR de Garijo e Poveda-Villalón (2020): descrição HTML de classes, propriedades e indivíduos; metadados; propósito, escopo e resumo; diagramas; exemplos de uso; opcionalmente lista de requisitos e de testes.
- Ferramentas: LODE, WIDOCO (integra LODE, WebVOWL, Bubastis para changelog, Licensius), pyLODE; OnToology (integrado ao GitHub, gera documentação, avalia e reserva URI permanente em w3id.org/def/nome com negociação de conteúdo); VoCol.
- Publicação online segundo as receitas W3C para vocabulários RDF: acessível pela URI como arquivo formal e como HTML por negociação de conteúdo.

### 4.5 Manutenção

Fonte: paper do LOT, seções 3.4, 4.4 e 4.5.

- Situações: detecção de bugs (inclui sugestões) e novos requisitos; quem detecta reporta ao time; a correção é agendada em sprint ou gera nova versão.
- Ferramentas: issue tracker (GitHub, GitLab, Bitbucket, Jira, Mantis), WebProtégé (notas e discussões ligadas a termos), Gra.fo (comentários, histórico e restauração de versões); git como infraestrutura de versões; Kanban (Trello, Jira); integração contínua (Jenkins, Travis, GitHub Actions) para validar e verificar continuamente, com o pipeline SAREF como exemplo.
- Recomendação: um repositório git por ontologia, para independência de releases (seção 4.5, Tip).

## 5. Tabela de classificação

Critério usado: determinístico vira tool do MCP (resultado reprodutível sem julgamento); o que precisa de linguagem natural ou julgamento semântico vira passo da skill executado pelo LLM; o humano aprova onde o LOT ou a NeOn atribuem a decisão a especialistas ou usuários, ou onde o artigo primário diz que LLMs não são confiáveis sem validação externa. A coluna "Evidência LLM" cita o artigo primário.

| Fase LOT | Atividade (LOT/NeOn) | Determinístico (tool) | LLM (passo da skill) | Humano aprova | Evidência LLM no artigo primário |
|---|---|---|---|---|---|
| Requisitos | Use case specification | Nenhum | Redigir casos de uso (nome, descrição, atores, fluxo) a partir de entrevistas e documentos | Especialistas e usuários confirmam os casos de uso | Sem estudo direto; o mais próximo é "functional requirements writing" a partir de texto (Fathallah 2024a). `needs_validation` para uso de LLM nesta subatividade |
| Requisitos | Data exchange identification | `connect` (acesso à fonte), `profile` (esquema, amostras, estatísticas) | Resumir a documentação e os exemplos recebidos | Usuários entregam e confirmam as fontes | Não coberto no artigo; é atividade de coleta |
| Requisitos | Purpose and scope identification | Nenhum | Redigir propósito, escopo e requisitos não funcionais candidatos | Time, usuários e especialistas aprovam o texto | Não coberto diretamente |
| Requisitos | Functional requirements proposal (CQs, frases, tabelas) | `profile` fornece termos e atributos para tabelas; `ontology_read` fornece triples para CQ reverse engineering | Gerar CQs ou frases a partir de texto e dados; gerar CQs a partir de ontologia existente; sugerir tabelas de conceitos, relações e atributos | Especialistas e usuários revisam cada requisito | Functional requirements writing: 2 estudos (seção 4.1.1). CQ reverse engineering: 7 estudos; RETROFIT-CQ com mais de 75% das CQs executáveis como SPARQL; precisão até 84,4% com prompt enriquecido (seção 4.3.4). Alharbi 2024b entrevistou humanos antes de gerar (seção 4.2.5) |
| Requisitos | Functional requirements completion | Checagem de duplicatas e de identificadores | Pré-checar ambiguidade contra padrões CORAL; sugerir prioridade | Obrigatório: especialistas e usuários validam pelos critérios de Grüninger e Fox e priorizam (paper do LOT, 3.1.5) | Sem estudo direto. `needs_validation` para pré-checagem automática de ambiguidade |
| Requisitos | ORSD formalization | Preencher template e gravar no repositório (tool de requisitos, ver seção 6) | Redigir campos textuais do ORSD | Time aprova a versão do ORSD | Não coberto |
| Requisitos | Requirements formalisation (CQ em SPARQL ou VTC) | Validar sintaxe SPARQL, executar sobre a ontologia (`eval`) | Traduzir CQ em SPARQL e propor resultado esperado | Dev aprova a consulta e o resultado esperado | 3 estudos; F1 de 88% a 96% (Tufek 2024, seção 4.3.4) |
| Implementação | Conceptualization | `ontology_read` do modelo atual; geração de diagrama a partir do modelo (`export`) | Propor classes, hierarquias, relações, atributos e axiomas a partir do ORSD e dos dados; organizar hierarquias; propor definições | Especialistas e dev aprovam o modelo; só o dev adiciona termos (paper do LOT, 3.2.1) | 11 estudos; GPT-4o F1 72,78% no LLMs4OL (seção 4.3.4); OntoGenix com loop humano-agente (seção 4.2.5) |
| Implementação | Ontology reuse (NeOn: search, selection; cenários 3 a 7) | Busca em registros (LOV, BioPortal, etc.) por termo; resolver IRIs; `ontology_read` de ontologias externas | Extrair propósito e elementos reutilizáveis de ontologias candidatas; propor hard ou soft reuse | Dev decide o que reutilizar e como | Kholmska 2024 passo 4 (características de ontologias para decisão de reuso), seção 4.2.4 |
| Implementação | Matching / aligning (NeOn) | Armazenar alinhamentos como `owl:equivalentClass`, `owl:sameAs` via `ontology_write`; métricas P/R/F1 contra referência (`eval`) | Propor correspondências entre ontologias; classificar candidatos como corretos ou não | Dev e especialista aprovam cada alinhamento | 5 estudos; OLaLa F1 90,2%; GPT-4o 100% ao rejeitar correspondências falsas (seção 4.3.4) |
| Implementação | Encoding | `ontology_write.propose_edit` (gera diff), `ontology_write.apply_edit` (aplica), `validate` (parse sintático), metadados obrigatórios, versionamento semver | Gerar OWL/Turtle a partir do modelo e das CQs; gerar anotações; corrigir erros de sintaxe apontados pelo parser | Humano aprova todo `apply_edit` (Doumanas 2024: especialistas comparam ontologia gerada com existentes antes de compor a nova, seção 4.2.5) | 11 estudos; OntoGenix economizou 8,2% a 58,3% de tempo; F1 ainda baixo em domínios sem referência madura (SAR: 19% a 48%) (seção 4.3.4) |
| Implementação | Evaluation | `validate`: consistência por reasoner, pitfalls (OOPS!), SHACL; `eval`: execução dos test cases de CQ, cobertura de dados, métricas | Interpretar relatórios e propor correções (axiomas de disjunção, etc.); verificar axiomas individualmente; verbalizar a ontologia para checagem de CQs | Obrigatório: decisão final é humana. O artigo diz que avaliação excede a capacidade do LLM sem verificadores externos (seção 5.1) | 4 estudos; ChatGPT-4 92,2% em verificação de axiomas, 96,7% com ensemble (Tsaneva 2024); OntoChat 87,5% de aprovação de especialistas; Fathallah 2024a usa erros do RDFLib e pitfalls do OOPS! como entrada (seções 4.1.2, 4.3.4) |
| Publicação | Propose release candidate | Marcar versão (tag semver), gerar changelog | Redigir notas de release | Dev decide se é release ou pré-release | Não coberto |
| Publicação | Documentation | Gerar HTML a partir do OWL (Widoco ou pyLODE) e diagramas (`export`) | Gerar rótulos, definições, resumos, exemplos de uso para termos e para a ontologia | Especialistas validam descrições (paper do LOT, 3.3.2; Bischof 2024 usou avaliação qualitativa por especialistas) | 5 estudos; documentação gerada considerada precisa por similaridade semântica (Rebboud 2024a) (seção 4.1.3) |
| Publicação | Online publication | `publish`: URI permanente, negociação de conteúdo, arquivo e HTML | Nenhum | Obrigatório: ação pública e irreversível, aprovação explícita | Não coberto (artigo primário, seção 2.1, diz que publicação online não aparece nos papers revisados) |
| Manutenção | Bug detection | Reexecutar `validate` e `eval` em CI; registrar issue | Triar relatos, extrair sugestões de melhoria, listar conceitos faltantes a partir de relatórios de validação | Especialistas e usuários decidem o que vira correção (Kholmska 2024 envolveu humanos) | 1 estudo (Kholmska 2024, passo 8), seções 4.1.4 e 4.2.4 |
| Manutenção | New requirements | Registrar issue; vincular ao ORSD | Redigir o novo requisito como CQ ou frase; estimar impacto no modelo | Humano aprova entrada no ORSD e agendamento em sprint | Não coberto; o artigo nota que manutenção depende de integração dinâmica de conhecimento (seção 5.1) |
| NeOn | Localization (cenário 9) | Armazenar rótulos com tag de idioma | Traduzir rótulos e definições | Especialista da língua aprova | Sem estudo no artigo. `needs_validation` |
| NeOn | Modularization, pruning, extension, specialization (cenário 8) | Extração de módulo por fechamento de termos; aplicar edições via `ontology_write` | Propor que ramos podar ou especializar | Dev aprova | Sem estudo no artigo. `needs_validation` |
| NeOn | NOR re-engineering (cenário 2) | `connect` e `profile` sobre a fonte; transformação mecânica (hierarquia em OWL, tesauro em SKOS) | Propor o modelo alvo a partir do esquema da fonte | Dev e especialista aprovam | Sem estudo no artigo; o paper do LOT (3.2.2) cita essa transformação como semi-automática |

Regras transversais extraídas das fontes:

1. Nenhuma saída de LLM entra na ontologia sem passar por `propose_edit`, `validate` e aprovação humana antes de `apply_edit`. Base: artigo primário, seções 5.1 e 5.2 (fluxos híbridos, validação externa, revisão por especialistas); paper do LOT, 3.2.1 (só o desenvolvedor adiciona termos).
2. Toda avaliação combina verificação formal (reasoner, pitfalls, testes de CQ) com julgamento humano. Base: artigo primário, seção 4.3.3 (abordagens híbridas) e 5.1; paper do LOT, 3.2.4.
3. Requisitos têm identificador, status, prioridade e proveniência, e cada teste aponta para o requisito. Base: paper do LOT, 3.1.4 e 3.1.7.
4. Prompts com template de saída (JSON, Turtle, SPARQL) e papel (ontology engineer, domain expert) são a prática dominante e reduzem erros de formato. Base: artigo primário, seção 4.2.3 e 5.2.
5. Publicação só depois de avaliação; a publicação online é opcional, a documentação não. Base: site lot.linkeddata.es; paper do LOT, 3.3.

## 6. Recomendações para o akme-template

### 6.1 Encaixe das tools previstas

| Tool prevista | Atividade LOT/NeOn | Fase | Observação |
|---|---|---|---|
| `connect` | Data exchange identification (LOT 3.1.2); Non-ontological resource reuse (NeOn cenário 2) | Requisitos | Entrada do fluxo quando há fonte de dados, API ou esquema |
| `profile` | Data exchange identification; insumo para tabelas de conceitos, relações e atributos (LOT 3.1.4); insumo para NOR re-engineering | Requisitos | Deve devolver esquema, tipos, cardinalidades observadas e amostras, pois é o que as tabelas METHONTOLOGY pedem |
| `ontology_read` | Conceptualization (ler modelo atual); Ontology reuse (ler ontologias externas); CQ reverse engineering (triples como entrada, Alharbi 2024b); Evaluation; Documentation | Implementação, Publicação | Deve aceitar IRI remota para suportar reuso |
| `ontology_write.propose_edit` | Encoding (LOT 3.2.2); Matching (gravar alinhamentos); Restructuring (cenário 8) | Implementação | Saída sempre como diff revisável, nunca escrita direta |
| `ontology_write.apply_edit` | Encoding; Maintenance (correções) | Implementação, Manutenção | Só após aprovação humana; deve registrar versão |
| `validate` | Evaluation, parte de verificação sintática e lógica (LOT 3.2.4): parse, reasoner, pitfalls OOPS!, SHACL | Implementação, Manutenção (CI) | Equivale ao "rule checker" que o artigo primário (5.1) pede como validação externa |
| `eval` | Evaluation, parte de verificação contra requisitos (LOT 3.1.7 e 3.2.4): executar test cases de CQ, cobertura de dados, métricas P/R/F1 para matching | Requisitos (formalização), Implementação | Deve aceitar lista de testes com id do requisito, SPARQL e resultado esperado |
| `publish` | Online publication (LOT 3.3.3); Propose release candidate (tag de versão) | Publicação | Ação pública; exige aprovação explícita em todo uso |
| `export` | Documentation (HTML, diagramas, LOT 3.3.2); serializações (Turtle, RDF/XML, JSON-LD); exportar ORSD | Publicação | Documentação é recomendada mesmo sem publicação online |

### 6.2 Tools que a metodologia exige e não estão previstas

1. `requirements` (ou `orsd_read` / `orsd_write`): o LOT exige um ORSD com requisitos identificados, com status, prioridade, proveniência e ligação a testes (paper do LOT, 3.1.4, 3.1.6, 3.1.7). Sem uma tool que persista esse artefato, a rastreabilidade requisito, teste, ontologia se perde. Deve gravar no repositório da ontologia (paper do LOT, 4.1).
2. `ontology_search` (busca em registros como LOV, BioPortal, AgroPortal): o reuso é atividade central no LOT e em seis dos nove cenários NeOn; a busca por termo é determinística e não deve ser feita de memória pelo LLM (paper do LOT, 3.2.3 e 4.2).
3. `issue` (criar e listar issues): a manutenção no LOT é guiada por issue tracker (paper do LOT, 3.4, 4.4); bugs e novos requisitos precisam de registro antes de virar edição.
4. `release` ou extensão de `publish` com tag semver e changelog: o LOT pede convenção de versionamento para todos os artefatos (paper do LOT, 3.2.2) e distingue release de pré-release (3.3.1). Se `publish` cobrir isso, não é preciso tool separada.
5. Geração de diagrama (Chowlk) pode ficar dentro de `export`; se não ficar, falta uma tool de conceitualização visual, que o LOT usa tanto para comunicação com especialistas quanto para documentação (paper do LOT, 3.2.1, 3.3.2).

### 6.3 Etapas que a skill deve expor

Ordem derivada do fluxo base do LOT com as subatividades das seções 2.2 a 2.5 e com os pontos de aprovação da seção 5:

1. Especificar: `connect` e `profile` quando há dados; redigir casos de uso, propósito e escopo; propor requisitos (CQs, frases ou tabelas, com a regra do LOT sobre quando usar cada uma); humano valida e prioriza; gravar ORSD; opcionalmente formalizar CQs em testes.
2. Conceitualizar: ler modelo atual; propor classes, hierarquias, relações, atributos e axiomas; buscar reuso em registros quando a conceitualização estiver estável; humano aprova o modelo.
3. Codificar: `propose_edit` com OWL e metadados; `validate`; humano aprova; `apply_edit`; versão nova.
4. Avaliar: `validate` e `eval` sobre os testes dos requisitos; LLM interpreta relatórios e propõe correções como novo `propose_edit`; humano decide. Voltar à etapa 2 ou 3 se necessário.
5. Publicar: decidir release candidate; `export` da documentação; LLM gera descrições e exemplos; especialistas validam; `publish` somente com aprovação explícita.
6. Manter: registrar issues; CI com `validate` e `eval`; LLM tria; humano agenda em sprint; retorna à etapa 1 ou 3.

### 6.4 Restrições para o manifest.yml

- `ontology_write.apply_edit`, `publish` e qualquer tool que apague ou publique exigem confirmação humana por chamada.
- `validate` deve rodar antes de qualquer `apply_edit` (artigo primário, 5.1 e 6: integrar saída de LLM com validação lógica formal).
- Saídas de LLM destinadas a OWL, SPARQL ou JSON devem seguir template de formato (artigo primário, 4.2.3), e o manifest deve declarar o formato aceito por cada tool.
- Cada edição registra proveniência (quem propôs, qual requisito motivou), porque o artigo primário (5.2) aponta rastreabilidade e transparência como desafio aberto e o LOT (3.1.4) exige proveniência dos requisitos.

## 7. Referências

Fontes efetivamente lidas:

- Artigo primário: Li, J., Garijo, D., Poveda-Villalón, M. (2026). Large Language Models for Ontology Engineering: A Systematic Literature Review. Semantic Web 17(4). DOI 10.1177/22104968261465514. Cópia lida: https://oa.upm.es/97559/1/10537354.pdf (local: docs/research/sources/neon-lot.pdf e neon-lot.txt). Seções citadas: 2.1, 4.1 a 4.4, 5.1 a 5.3, 6, Tabelas 1 e 2.
- Paper do LOT: Poveda-Villalón, M., Fernández-Izquierdo, A., Fernández-López, M., García-Castro, R. (2022). LOT: An industrial oriented ontology engineering framework. Engineering Applications of Artificial Intelligence 111, 104755. DOI 10.1016/j.engappai.2022.104755. Preprint lido: https://oa.upm.es/78273/1/LatestMainPaper.pdf (registro https://oa.upm.es/78273/). Seções citadas: 2, 3, 3.1 a 3.4, 4.1 a 4.6, 5, 5.1.
- Site do LOT: https://lot.linkeddata.es/ (fases, atividades, links para template do ORSD em https://github.com/oeg-upm/LOT-resources/tree/master/ORSD, CORAL, Chowlk https://chowlk.linkeddata.es/chowlk_spec).
- Cenários NeOn: Gómez-Pérez, A., Suárez-Figueroa, M. C. (2009). NeOn Methodology for Building Ontology Networks: a Scenario-based Methodology. Lido em https://research.uni-sofia.bg/xmlui/bitstream/handle/10506/672/S3T2009_24_AGomez-Perez_MCSuarez-Figueroa.pdf?sequence=1. Seções 4 e 5.
- Glossário NeOn: Suárez-Figueroa, M. C., Gómez-Pérez, A. (2008). Towards a Glossary of Activities in the Ontology Engineering Field. LREC 2008. Lido em http://www.lrec-conf.org/proceedings/lrec2008/pdf/219_paper.pdf. Seção 2 e Tabela 2.
- Fichas da NeOn arquivadas pela Open University: ORSD e template (https://research-archive.stem.open.ac.uk/stemra-data/uploads/sites/136/2025/03/Chapter-05.pdf), glossário (https://research-archive.stem.open.ac.uk/stemra-data/uploads/sites/136/2025/03/Chapter-03-2.pdf), cenários (https://research-archive.stem.open.ac.uk/stemra-data/uploads/sites/136/2025/03/Chapter-03-1.pdf).
- Mensagem na lista W3C public-owl-dev (2008) com o endereço original do glossário: https://lists.w3.org/Archives/Public/public-owl-dev/2008JulSep/0028.html.

Fontes citadas pelas anteriores mas não lidas neste relatório (`needs_validation` para qualquer detalhe que dependa só delas):

- Suárez-Figueroa, M. C., Gómez-Pérez, A., Motta, E., Gangemi, A. (eds.) (2012). Ontology Engineering in a Networked World. Springer. https://link.springer.com/book/10.1007/978-3-642-24794-1 (paywall; o capítulo 2 não pôde ser baixado).
- Suárez-Figueroa, M. C., Gómez-Pérez, A., Fernández-López, M. (2015). The NeOn Methodology framework: A scenario-based methodology for ontology development. Applied Ontology 10(2), 107 a 145.
- NeOn Deliverables D5.4.1 (2008) e D5.4.2; D5.3.1 e D5.3.2 (glossário). Endereços em neon-project.org fora do ar no momento da pesquisa.
- Suárez-Figueroa, M. C., Gómez-Pérez, A., Villazón-Terrazas, B. (2009). How to write and use the Ontology Requirements Specification Document. ODBASE 2009.
- NeOn Glossary of Processes and Activities (PDF, 59 definições). http://www.neon-project.org/web-content/images/Publications/neonglossaryofactivities.pdf (indisponível; só as definições listadas na seção 2.7 foram lidas por fontes secundárias).
- Garijo, D., Poveda-Villalón, M. (2020). Best Practices for Implementing FAIR Vocabularies and Ontologies on the Web. Preprint: https://arxiv.org/abs/2003.13084.
- Fernández-Izquierdo, A., Poveda-Villalón, M., García-Castro, R. (2019). CORAL: a corpus of ontological requirements annotated with lexico-syntactic patterns. ESWC 2019. Corpus: http://coralcorpus.linkeddata.es/.
