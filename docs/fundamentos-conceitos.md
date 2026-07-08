# Fundamentos consolidados — conceitos das referências

### Teorema CAP (impossibilidade Consistência + Disponibilidade sob partição)  
**Fonte:** CAP-GilbertLynch2002 · **Ementa:** Parte IV  
Gilbert e Lynch reafirmam formalmente o resultado de Brewer: em uma rede sujeita a falhas de comunicação, é impossível para qualquer serviço implementar memória compartilhada atômica de leitura/escrita e ainda garantir resposta a toda requisição. É um caso do trade-off geral safety (consistência) vs liveness (disponibilidade) em sistemas não confiáveis; sob partição deve-se sacrificar C ou A. Mesmo sem partição real, a assincronia torna impossível distinguir atraso de falha.  
**Aplicação:** Fundamenta a decisão de NÃO exigir consistência forte global. Como a banda móvel da frota é cara, finita e sujeita a partições, cada subsistema escolhe explicitamente seu lado do CAP: a ingestão de telemetria (Cassandra) prioriza disponibilidade/escrita (AP) e o Delta/DW-Gold prioriza consistência (fonte da verdade). É a justificativa teórica raiz da persistência poliglota.

### Segmentação de consistência e disponibilidade (data/operation/functional partitioning)  
**Fonte:** CAP-GilbertLynch2002 · **Ementa:** Parte IV  
O paper mostra que a saída prática para o CAP é segmentar o sistema em subserviços, cada um com um trade-off distinto: dados diferentes exigem garantias diferentes (o carrinho de compras pode ser altamente disponível e ocasionalmente inconsistente, mas o registro de checkout/cobrança precisa ser fortemente consistente). A segmentação pode ser por dado, por operação (leitura vs escrita), por função e por usuário/geografia.  
**Aplicação:** É a base conceitual direta da nossa persistência poliglota: telemetria de alto volume (Cassandra, AP/eventual) vs cobrança automática e dossiê regulatório (Delta/Postgres, fortemente consistente) vs cache ao vivo (Redis). O paralelo carrinho-vs-checkout mapeia exatamente para telemetria-vs-motor-de-cobrança.

### Melhor esforço de consistência / cache web (padrão Akamai)  
**Fonte:** CAP-GilbertLynch2002 · **Ementa:** Parte IV  
Para aplicações que exigem resposta rápida em todas as situações, sacrifica-se consistência: garante-se sempre resposta rápida, aceitando que ela possa estar levemente desatualizada. O exemplo clássico é o cache web distribuído, que entrega alta disponibilidade a partir de servidores próximos ao usuário, propagando atualizações eventualmente.  
**Aplicação:** Justifica o Redis como camada de cache ao vivo do dashboard: valores de estado de frota/veículos servidos com baixa latência e consistência de melhor esforço, revalidados pelo hot path do Flink/Spark, sem bloquear a experiência do operador.

### Consistência eventual e loja 'always-writeable' (conflito resolvido na leitura)  
**Fonte:** Dynamo-DeCandia2007 · **Ementa:** Parte IV  
Dynamo projeta o espaço de uma loja sempre gravável, na qual escritas nunca são rejeitadas mesmo sob falhas de rede ou servidor; para isso empurra a complexidade da reconciliação de conflitos para a leitura (todas as atualizações chegam a todas as réplicas eventualmente). Sacrifica consistência sob certos cenários de falha em troca de disponibilidade e de SLAs de latência rígidos (99,9º percentil).  
**Aplicação:** Fundamenta o requisito de 'sem perda de pacotes' e alta concorrência de escrita da telemetria: o armazenamento de telemetria (Cassandra, herdeiro do Dynamo) deve aceitar escritas de sensores mesmo com conectividade móvel intermitente, nunca descartando um evento de veículo por indisponibilidade momentânea de réplica.

### Particionamento por consistent hashing + escalabilidade incremental (nós virtuais)  
**Fonte:** Dynamo-DeCandia2007 · **Ementa:** Parte IV  
Dados são particionados e replicados em um anel via consistent hashing, de modo que a entrada/saída de um nó afeta apenas seus vizinhos imediatos. Nós virtuais (múltiplos tokens por nó físico) corrigem distribuição não uniforme e exploram heterogeneidade de hardware, permitindo escalar 'um nó por vez' sem repartição manual.  
**Aplicação:** Justifica o modelo de escala horizontal do Cassandra para telemetria e o particionamento por vehicle_id (chave de partição): garante distribuição de carga entre nós e crescimento incremental do cluster conforme a frota do consórcio de 6 locadoras cresce, sem downtime.

### Quóruns ajustáveis N/R/W (R+W>N) — consistência configurável por operação  
**Fonte:** Dynamo-DeCandia2007 · **Ementa:** Parte IV  
Cada item é replicado em N hosts; R e W são os mínimos de réplicas para leitura e escrita bem-sucedidas. Configurar R+W>N produz um sistema quórum-like, e a escolha de N,R,W permite ao cliente equilibrar durabilidade, disponibilidade, consistência e latência (a config típica em produção é (3,2,2)).  
**Aplicação:** Fundamenta o uso de consistência sintonizável do Cassandra por caso de uso: escritas de telemetria de altíssimo volume podem usar consistência baixa (ONE/LOCAL_ONE) por desempenho, enquanto leituras que alimentam o apoio a emergências (dossiê regulatório) usam QUORUM para garantir dados recentes e confiáveis.

### Sloppy quorum + hinted handoff (tolerância a falhas temporárias)  
**Fonte:** Dynamo-DeCandia2007 · **Ementa:** Parte III  
Em vez de quórum estrito, Dynamo usa os primeiros N nós saudáveis da preference list; se o nó alvo está temporariamente indisponível, a réplica vai para outro nó com uma 'dica' (hint) do destinatário pretendido, sendo reentregue quando o nó se recupera. Isso preserva as garantias de disponibilidade e durabilidade de leitura/escrita durante falhas transitórias de nó/rede.  
**Aplicação:** Sustenta a resiliência da camada de persistência de telemetria em ambiente de conectividade instável: mesmo com nós/rede oscilando, escritas de sensores não falham, alinhando-se à tolerância a falhas exigida na ingestão de fluxos contínuos (Parte III) e ao requisito de não perder pacotes.

### Anti-entropia com árvores de Merkle e read repair (recuperação de falhas permanentes)  
**Fonte:** Dynamo-DeCandia2007 · **Ementa:** Parte IV  
Para sincronizar réplicas divergentes em segundo plano, Dynamo usa árvores de Merkle (hash trees): comparando raízes e descendo apenas nos ramos divergentes, detecta chaves fora de sincronia minimizando dados transferidos e leituras de disco. O read repair complementa, atualizando oportunisticamente réplicas defasadas durante leituras.  
**Aplicação:** Justifica confiar no reparo/anti-entropia interno do Cassandra para garantir durabilidade de longo prazo da telemetria após falhas de disco ou nó, sem intervenção manual, mantendo íntegro o histórico por veículo usado no dashboard e nos dossiês.

### Membership por gossip e detecção de falhas descentralizada (sem SPOF, simetria/descentralização)  
**Fonte:** Dynamo-DeCandia2007 · **Ementa:** Parte IV  
Dynamo é totalmente descentralizado: um protocolo de gossip propaga mudanças de membership e mantém visão eventualmente consistente do anel, e a detecção de falhas é local (um nó marca outro como falho se não responde). Simetria (todo nó tem as mesmas responsabilidades) e descentralização evitam gargalos e pontos únicos de falha que, no passado, causaram indisponibilidade.  
**Aplicação:** Fundamenta a operação sem ponto único de falha do cluster Cassandra de telemetria: nós podem ser adicionados/removidos com administração mínima, essencial para um serviço 24/7 que apoia emergências, onde a indisponibilidade do armazenamento seria crítica.

### Versionamento de objetos com vector clocks e reconciliação (causalidade)  
**Fonte:** Dynamo-DeCandia2007 · **Ementa:** Parte IV  
Cada modificação gera uma versão nova e imutável; vector clocks (listas de pares nó,contador) capturam causalidade entre versões, permitindo distinguir versões que se subsumem (reconciliação sintática) de ramos concorrentes que exigem reconciliação semântica pela aplicação. O tamanho da versão fica desacoplado da taxa de atualização.  
**Aplicação:** Estabelece o vocabulário de causalidade/ordenação sob concorrência que motiva nossa decisão de resolver ordenação estrita por veículo+timestamp na camada de processamento (Flink event-time + watermarks) em vez de depender de last-write-wins, e informa como tratar atualizações concorrentes de registros cadastrais/dossiês no MongoDB.

### Alto throughput de escrita: commit log sequencial + memtable + SSTable + compactação (LSM), leitura lockless  
**Fonte:** Cassandra-Lakshman2009 · **Ementa:** Parte IV  
Cassandra transforma toda escrita em escrita sequencial em disco: grava primeiro em commit log (durabilidade), depois em estrutura em memória que, ao exceder um limiar, é despejada em arquivos imutáveis; arquivos são mesclados por compactação (merge sort), similar ao Bigtable. Como os arquivos nunca são mutados, leituras não precisam de locks — a instância é praticamente lockless, evitando a concorrência de implementações baseadas em B-Tree.  
**Aplicação:** É a justificativa técnica central para escolher Cassandra como armazenamento de telemetria: a carga da frota conectada é escrita-intensiva (bilhões de eventos de sensores), e o modelo LSM entrega altíssimo throughput de escrita sem sacrificar eficiência de leitura para o dashboard.

### Colunas ordenadas por tempo dentro da linha (clustering por timestamp)  
**Fonte:** Cassandra-Lakshman2009 · **Ementa:** Parte IV  
No modelo de Cassandra as colunas de uma column family podem ser ordenadas por tempo ou por nome; o Inbox Search do Facebook explora a ordenação temporal para sempre exibir resultados em ordem cronológica. Toda operação sob uma única row key é atômica por réplica, independentemente de quantas colunas são lidas/escritas.  
**Aplicação:** Fundamenta diretamente o requisito de 'ordenação estrita por veículo e timestamp': modelar telemetria com partition key = vehicle_id e clustering columns ordenadas por timestamp entrega leituras já ordenadas cronologicamente por veículo, com atomicidade por linha, otimizando consultas de janela temporal do dashboard e a montagem do dossiê de emergência.

### Modelo de dados wide-column / registro extensível (column families, super columns, schema flexível)  
**Fonte:** Cassandra-Lakshman2009 · **Ementa:** Parte IV  
Cassandra oferece uma tabela como mapa multidimensional distribuído indexado por chave, com colunas agrupadas em column families (e super column families); qualquer linha pode ter qualquer combinação de colunas (linhas de comprimento variável, não restritas por schema fixo). É descrito como 'casamento' entre a distribuição/disponibilidade do Dynamo e o modelo de dados do Bigtable.  
**Aplicação:** Justifica o modelo wide-column para telemetria heterogênea da frota: sensores internos/externos, câmeras 360° e computador de bordo produzem conjuntos de atributos variáveis por veículo/evento, acomodados sem alterar schema, ao contrário de uma tabela relacional rígida.

### Detector de falhas Φ Accrual (suspeição adaptativa a rede/carga)  
**Fonte:** Cassandra-Lakshman2009 · **Ementa:** Parte IV  
Em vez de um booleano up/down, o detector accrual emite um nível de suspeição Φ, ajustado dinamicamente às condições de rede e carga a partir de janelas deslizantes de tempos de chegada de gossip. Na prática reduziu o tempo de detecção de falha de ~2 min para ~15 s em cluster de 100 nós, mantendo boa acurácia.  
**Aplicação:** Fundamenta a robustez do cluster Cassandra em ambiente de latências variáveis (banda móvel): a detecção de falhas adapta-se às oscilações de rede sem gerar falsos positivos, mantendo a ingestão de telemetria estável e o roteamento correto de requisições.

### Replicação multi-datacenter (políticas Rack/Datacenter Aware)  
**Fonte:** Cassandra-Lakshman2009 · **Ementa:** Parte IV  
Cassandra replica cada linha entre múltiplos datacenters, construindo a preference list de forma que as réplicas fiquem espalhadas geograficamente e conectadas por links de alta velocidade, tolerando falhas de datacenter inteiro sem indisponibilidade. Um líder (via ZooKeeper) mantém o invariante de distribuição de faixas e políticas de rack/DC.  
**Aplicação:** Sustenta a resiliência geográfica adequada a um consórcio de 6 locadoras: telemetria e dados críticos podem ser replicados entre localidades, mantendo disponibilidade do dashboard e do apoio a emergências mesmo diante de falha de um site inteiro.

### Taxonomia NoSQL: key-value, documento, registro extensível (wide-column) e relacional  
**Fonte:** Cattell2011 (Scalable SQL and NoSQL Data Stores) · **Ementa:** Parte IV  
Cattell classifica as lojas escaláveis em quatro modelos de dados — key-value stores, document stores, extensible record stores (wide-column) e relational — e caracteriza NoSQL por seis traços: escala horizontal de operações simples, replicação/particionamento, interface call-level simples, concorrência mais fraca que ACID, uso de índices distribuídos/RAM e atributos dinâmicos. Cassandra é descrita como 'casamento de Dynamo e Bigtable'.  
**Aplicação:** Fornece o mapa conceitual que organiza nossa persistência poliglota: Redis (key-value) para cache ao vivo, MongoDB (documento) para cadastrais/dossiês, Cassandra (registro extensível/wide-column) para telemetria e Postgres/Delta (relacional) para DW-Gold/fonte da verdade — cada modelo escolhido pela forma de acesso predominante.

### BASE vs ACID (abrir mão de ACID global por escala e disponibilidade)  
**Fonte:** Cattell2011 (Scalable SQL and NoSQL Data Stores) · **Ementa:** Parte IV  
Sistemas NoSQL trocam as garantias ACID por BASE (Basically Available, Soft state, Eventually consistent): abrindo mão da consistência transacional global obtém-se muito maior desempenho e escalabilidade, ainda que com garantias limitadas de leitura. Cattell observa que 'o mundo não é globalmente consistente' — clientes toleram overbooking de voos e itens de carrinho vendidos antes da finalização.  
**Aplicação:** Justifica a fronteira ACID/BASE do projeto: telemetria e leituras de dashboard operam em BASE (eventual, alto throughput), enquanto o motor de cobrança automática e o DW-Gold exigem semântica transacional/consistência forte — a mesma lógica do carrinho (eventual) vs checkout (ACID).

### Caso de uso de document store (múltiplos tipos de objeto, busca por vários campos, consistência eventual aceitável)  
**Fonte:** Cattell2011 (Scalable SQL and NoSQL Data Stores) · **Ementa:** Parte IV  
Document stores são indicados quando há múltiplos tipos de objetos e é preciso consultar por vários campos, tolerando modelo eventualmente consistente com atomicidade/isolamento limitados; são schema-less (atributos dinâmicos, documentos aninhados) com índices secundários. MongoDB oferece sharding automático e consistência por documento na cópia primária.  
**Aplicação:** Fundamenta a escolha do MongoDB para dados cadastrais e dossiês de emergência: entidades heterogêneas (clientes, veículos, incidentes com anexos/estruturas aninhadas) consultadas por múltiplos campos, onde consistência por documento é suficiente e o schema flexível acomoda dossiês regulatórios variados.

### Caso de uso de key-value store (cache de dados relacionais / página pré-montada)  
**Fonte:** Cattell2011 (Scalable SQL and NoSQL Data Stores) · **Ementa:** Parte IV  
Key-value stores são a solução mais simples quando se busca objetos por uma única chave; um padrão típico é armazenar como um único objeto o resultado caro de consultas RDBMS (ex.: página personalizada do usuário), servindo-o rapidamente e reconstruindo-o só quando os dados mudam — atuando como cache de banco relacional.  
**Aplicação:** Justifica o Redis como cache ao vivo: estados agregados de frota/veículos e resultados recomputados pelo Flink/Spark são materializados por chave para servir o dashboard com baixa latência, evitando recomputações caras a cada requisição do operador.

### NewSQL / RDBMS escalável (SQL + ACID com escala horizontal para operações de escopo único)  
**Fonte:** Cattell2011 (Scalable SQL and NoSQL Data Stores) · **Ementa:** Parte IV  
Novos RDBMSs (VoltDB, Clustrix, MySQL Cluster) buscam escala horizontal shared-nothing sem abandonar SQL e transações ACID, desde que operações e transações fiquem restritas a um único nó; eles só penalizam o custo de operações multi-nó, dando vantagem de linguagem de alto nível e ACID quando a aplicação evita joins/transações cross-node.  
**Aplicação:** Contextualiza o eixo NewSQL da ementa e posiciona o DW estrela em PostgreSQL (camada Gold do Lakehouse) como o polo de consistência forte/SQL do sistema: onde precisamos de ACID e SQL analítico (cobrança, modelagem dimensional, Markov de ocupação de pátios), mantemos o relacional, reservando NoSQL para a telemetria de alto volume.

### Escala horizontal shared-nothing por sharding sobre commodity hardware  
**Fonte:** Cattell2011 (Scalable SQL and NoSQL Data Stores) · **Ementa:** Parte III  
O traço definidor dos sistemas NoSQL é o escalonamento horizontal 'shared nothing' — replicar e particionar (shard) dados por muitos servidores sem compartilhar RAM ou disco, suportando grande número de operações simples de leitura/escrita por segundo em hardware commodity. Isso contrasta com o escalonamento vertical, limitado e mais caro.  
**Aplicação:** Fundamenta a arquitetura de ingestão escalável do projeto: tanto o Kafka (partições isoladas por vehicle_id) quanto o Cassandra adotam sharding shared-nothing, permitindo absorver a alta concorrência da frota e crescer horizontalmente em nós baratos conforme o volume de telemetria aumenta.

### SLA no 99,9º percentil e o estado como principal componente do SLA  
**Fonte:** Dynamo-DeCandia2007 · **Ementa:** Parte I  
A Amazon mede SLAs no 99,9º percentil da distribuição (não na média/mediana), pois busca boa experiência para todos os clientes, não só a maioria; como a lógica de negócio costuma ser leve, o gerenciamento de estado torna-se o componente dominante do SLA. Várias técnicas do Dynamo existem só para controlar a latência de cauda.  
**Aplicação:** Fundamenta a definição de metas de latência do projeto por percentil (não por média) para o dashboard e, sobretudo, para o apoio a emergências, onde a cauda de latência de acesso ao estado (telemetria/dossiê) é o que determina a qualidade percebida da resposta.

### Retrieval-Augmented Generation (memória paramétrica + não-paramétrica)  
**Fonte:** RAG-Lewis2020 · **Ementa:** Parte III  
RAG combina um seq2seq pré-treinado (memória paramétrica, BART) com um índice denso de vetores acessado por um recuperador neural (memória não-paramétrica, um dump da Wikipédia), treinados end-to-end. O documento recuperado é tratado como variável latente marginalizada em duas formulações (RAG-Sequence e RAG-Token). O paper estabelece o padrão de 'endereçar tarefas intensivas em conhecimento' aterrando a geração em conhecimento externo recuperável em vez de só nos pesos do modelo.  
**Aplicação:** Fundamenta o concierge de IA por RAG local: o PLN por regras (gerador) é aterrado em documentos recuperados de uma base local (políticas da frota, manuais, FAQ, dossiês), dispensando LLM pago com chave. Também fundamenta a geração de dossiês de emergência a partir de evidências recuperadas em vez de texto inventado.

### Memória não-paramétrica como índice denso acessado por MIPS  
**Fonte:** RAG-Lewis2020 · **Ementa:** Parte IV  
A memória não-paramétrica é um índice de vetores densos (embeddings do DPR, um bi-encoder BERT de query e documento) e o top-K de passagens é obtido por Maximum Inner Product Search (MIPS). O MIPS é resolvido em tempo sublinear com FAISS usando aproximação Hierarchical Navigable Small World (HNSW) sobre 21M de trechos. A recuperação por similaridade é, portanto, o mecanismo concreto que liga o corpus ao gerador.  
**Aplicação:** Justifica o uso de um banco vetorial (classe Milvus/HNSW) como memória do concierge: a busca por similaridade (MIPS/HNSW) é a ponte executável entre o Big Data indexado (dossiês, manuais, telemetria descritiva) e o gerador de respostas. Conecta explicitamente a Parte III (RAG) à Parte IV (SBD vetoriais).

### Redução de alucinação, proveniência e memória human-readable/writable  
**Fonte:** RAG-Lewis2020 · **Ementa:** Parte III  
Por estar 'strongly grounded in real factual knowledge', RAG alucina menos e gera texto mais factual, específico e diverso que o baseline puramente paramétrico (BART), com avaliadores humanos preferindo RAG. Como a memória é texto bruto (não representações distribuídas), ela é interpretável (human-readable) e editável (human-writable), oferecendo proveniência/rastreabilidade das decisões.  
**Aplicação:** Requisito crítico para o dossiê de emergências destinado à regulação: respostas auditáveis, citáveis e com fonte rastreável, e não texto alucinado. Também sustenta a confiabilidade do concierge ao usuário final.

### Hot-swapping do índice (atualizar conhecimento sem re-treino)  
**Fonte:** RAG-Lewis2020 · **Ementa:** Parte III  
Como o conhecimento vive na memória não-paramétrica, ele pode ser revisto e expandido apenas substituindo o índice de documentos, sem re-treinar o modelo. O experimento de líderes mundiais (índice de 2016 vs 2018) demonstra que trocar o índice atualiza o conhecimento do sistema (70%/68% corretos com o índice contemporâneo vs 4-12% com índice desatualizado).  
**Aplicação:** Permite que a base do concierge (tarifas, disponibilidade de veículos, políticas, informações locais) seja atualizada editando o índice/documentos — essencial num sistema SEM chave de LLM paga e com dados de frota em constante mudança, evitando qualquer re-treino.

### Banco de dados vetorial cloud-native para dados não-estruturados  
**Fonte:** Manu-VectorDB2022 · **Ementa:** Parte IV  
Com modelos de embedding, dados não-estruturados (~80% do dado novo, segundo a IDC) são codificados em vetores de alta dimensão e operações como recomendação e busca viram busca por similaridade. À medida que coleções passam de bilhões de vetores, tornam-se necessários bancos vetoriais gerenciados e horizontalmente escaláveis; Manu (evolução do Milvus) provê evolvability de longo prazo, consistência ajustável, elasticidade e alto desempenho.  
**Aplicação:** Fundamenta a escolha de um banco vetorial (classe Milvus, citado na ementa) como memória de embeddings do concierge/RAG, dentro da persistência poliglota da Parte IV.

### 'Log as data' — WAL/binlog como backbone e microsserviços pub/sub  
**Fonte:** Manu-VectorDB2022 · **Ementa:** Parte III  
Manu estrutura todo o sistema como microsserviços de publish/subscribe de log: o write-ahead log (WAL) e as mensagens inter-componentes são 'logs' (streams duráveis e assináveis). Componentes de escrita são publishers e todos os componentes read-only (busca/análise/índice) são subscribers independentes, o que desacopla leitura de escrita, stateless de stateful e storage de computação. O paper afirma que isso 'ecoa plataformas de análise que usam sistemas de streaming como Kafka para conectar componentes' e é implementado sobre Kafka/Pulsar.  
**Aplicação:** Fundamenta diretamente a arquitetura centrada em Kafka do projeto: o log de tópicos isolados é o backbone que conecta o simulador aos consumidores (Flink, Spark) e à persistência, permitindo que cada componente evolua e escale de forma independente.

### Time-tick como watermark (event-time e ordem determinística)  
**Fonte:** Manu-VectorDB2022 · **Ementa:** Parte III  
Cada entrada de log recebe um timestamp global único gerado por um TSO com relógio lógico híbrido (componente físico + componente lógico para ordenar eventos no mesmo instante). Mensagens de controle chamadas time-ticks — descritas explicitamente como 'similar to watermarks in Apache Flink' — são inseridas periodicamente em cada canal para sinalizar o progresso do event-time aos subscribers e impor ordem determinística às mensagens de coordenação.  
**Aplicação:** Fundamenta o processamento por event-time + watermarks no Flink e a exigência de ordenação estrita por veículo e timestamp: o time-tick é o mecanismo canônico para saber até quando o fluxo está completo antes de fechar janelas de análise (rotas, score).

### Consistência delta (tunable / staleness limitado)  
**Fonte:** Manu-VectorDB2022 · **Ementa:** Parte IV  
Manu adota consistência delta, que garante staleness limitado: uma leitura vê dados de no máximo delta unidades de tempo atrás. Consistência forte e eventual são casos especiais (delta = 0 e delta = infinito). Operacionalmente, o subscriber compara sua última time-tick consumida (Ls) com o tempo da query (Lr) e, se Lr − Ls ≥ τ (tolerância de staleness), espera a próxima time-tick antes de executar.  
**Aplicação:** Fundamenta as decisões de consistência na persistência poliglota (Parte IV, CAP/ACID vs BASE): o cache 'ao vivo' no Redis tolera staleness limitado configurável, enquanto o dashboard de emergências pode exigir delta menor — um trade-off desempenho/consistência ajustável por consulta.

### Elasticidade de granularidade fina (decupagem por funcionalidade)  
**Fonte:** Manu-VectorDB2022 · **Ementa:** Parte III  
O paper argumenta que elasticidade e isolamento de recursos devem ser geridos no nível da funcionalidade, não do sistema — separar read de write é insuficiente. Manu separa query nodes, index nodes e data nodes (workers stateless que buscam cópias read-only) para que cada tipo escale independentemente conforme a carga, já que a busca/indexação são computacionalmente intensivas e usam aceleradores.  
**Aplicação:** Fundamenta a arquitetura de containers/microsserviços (docker-compose) com componentes que escalam de forma independente: separar o hot path de emergências (Spark) da análise contínua (Flink) e da ingestão em lote, cada um com seu perfil de recurso.

### Segmento growing/sealed + indexação stream vs batch (hot/cold)  
**Fonte:** Manu-VectorDB2022 · **Ementa:** Parte III  
Dados novos entram em segmentos 'growing' pesquisados por brute-force scan para baixa latência; ao atingir tamanho/tempo (512MB ou ~10s) o segmento é 'sealed' e recebe índice construído para alta eficiência. Manu combina indexação em stream (on-the-fly, sem parar a busca) e em batch, e constrói índices temporários leves (IVF-FLAT) em slices para acelerar até ~10x a busca dos dados frescos.  
**Aplicação:** Fundamenta o padrão hot path + batch e a maturação Bronze→Silver→Gold no Delta/MinIO: dados quentes servidos com baixa latência e reprocessados/consolidados em lote — análogo às arquiteturas Lambda/Kappa da Parte III.

### Relaxar complexidade transacional (row-level ACID basta)  
**Fonte:** Manu-VectorDB2022 · **Ementa:** Parte IV  
Como modelos de aprendizado codificam a semântica de uma entidade num único vetor, transações multi-linha/multi-tabela são desnecessárias e row-level ACID é suficiente para a maioria das aplicações vetoriais. Relaxar a complexidade transacional é apontado como a 'oportunidade-chave' para atingir consistência ajustável e elasticidade — o oposto das regras de DBMS relacional tradicional.  
**Aplicação:** Justifica o uso de NoSQL wide-column (Cassandra) para telemetria de altíssimo volume sem exigir transações distribuídas — a persistência é escolhida pela carga (poliglota), não forçada num único modelo relacional.

### Object storage (MinIO/S3) desacoplado da computação  
**Fonte:** Manu-VectorDB2022 · **Ementa:** Parte III  
Manu persiste os dados grandes (binlog, índices, coleções) em object storage barato e altamente disponível — AWS S3, MinIO ou sistema de arquivos — com API S3-compatível intercambiável, e usa etcd (KV) só para status/metadados. A alta latência do object storage não é gargalo porque os workers computam sobre cópias read-only em memória.  
**Aplicação:** Fundamenta o MinIO como camada de armazenamento do Lakehouse (o Data Lake da Parte III, com S3/ADLS/GCS) e a decupagem storage/compute — a mesma tecnologia (MinIO) é literalmente adotada como fonte da verdade Delta no projeto.

### Particionamento por hash/canal (isolamento e throughput)  
**Fonte:** Manu-VectorDB2022 · **Ementa:** Parte III  
Cada shard corresponde a um canal WAL / bucket lógico via consistent hashing num anel de loggers, e cada entidade é hasheada a um shard pelo seu ID. Requisições de tipos distintos (definição de dados, coordenação, manipulação) usam canais próprios para não interferirem entre si, aumentando o throughput; a manipulação é distribuída por múltiplos canais.  
**Aplicação:** Fundamenta a partição do Kafka por vehicle_id e o uso de tópicos isolados por tipo de evento — preserva a ordem por veículo e evita interferência entre fluxos sob alta concorrência.

### NewSQL: escalabilidade de sistemas + consistência de BD  
**Fonte:** Spanner-Corbett2012 · **Ementa:** Parte IV  
Spanner combina, da comunidade de BD, interface semi-relacional/SQL, transações de propósito geral e consistência externa; e, da comunidade de sistemas, escalabilidade, sharding automático, tolerância a falhas e replicação consistente em escala global. É o primeiro sistema a suportar transações distribuídas externamente consistentes, evoluindo de um key-value versionado (estilo Bigtable) para um banco temporal multi-versão; o próprio texto o cita no contexto de NewSQL (junto a VoltDB).  
**Aplicação:** Fundamenta a categoria NewSQL da ementa (Parte IV: escalabilidade NoSQL + consistência SQL) e contextualiza a convergência DW vs Big Data vs AI stacks (Parte I) — referência para justificar as escolhas de persistência e o DW estrela como camada Gold.

### TrueTime: incerteza de relógio explícita + commit-wait  
**Fonte:** Spanner-Corbett2012 · **Ementa:** Parte I  
TrueTime expõe o tempo como um intervalo [earliest, latest] com incerteza limitada ε (geralmente < 10ms, via GPS + relógios atômicos com algoritmo de Marzullo), ao contrário de APIs de tempo comuns que escondem a incerteza. A regra commit-wait faz o coordenador esperar até TT.after(s) ser verdadeiro antes de tornar o commit visível, garantindo que os timestamps atribuídos reflitam a ordem de serialização real.  
**Aplicação:** Fundamenta teoricamente a exigência de ordenação estrita por timestamp e o valor de timestamps globalmente significativos e monotônicos como base do event-time — a mesma disciplina temporal que o Flink emula com watermarks e que o time-tick do Manu implementa.

### Consistência externa / linearizabilidade  
**Fonte:** Spanner-Corbett2012 · **Ementa:** Parte I  
Spanner garante consistência externa (equivalente a linearizabilidade): se uma transação T1 committa antes de T2 iniciar, então o timestamp de commit de T1 é menor que o de T2 — formalmente tabs(commit T1) < tabs(start T2) ⇒ s1 < s2. A ordem de serialização é globalmente coerente e os timestamps de commit refletem essa ordem, mesmo com transações distribuídas.  
**Aplicação:** É o requisito de correção que justifica a ordenação estrita por veículo e timestamp sem perda de pacotes: garante que a sequência causal de eventos (ex.: a cronologia de uma emergência) seja processada e persistida na ordem real em que ocorreu.

### Multi-versão + leituras snapshot no passado (audit read no timestamp t)  
**Fonte:** Spanner-Corbett2012 · **Ementa:** Parte IV  
Spanner é multi-versão: cada valor é versionado e timestampado com seu commit time, e versões antigas são coletadas por política configurável. Transações read-only são lock-free e snapshot reads executam 'no passado' em qualquer réplica suficientemente atualizada (com staleness opcionalmente limitado pelo cliente). Uma leitura de auditoria de toda a base em t vê exatamente os efeitos de toda transação committada até t, sem bloquear as escritas em curso.  
**Aplicação:** Fundamenta o dossiê para regulação e o time-travel do Delta: reconstrução reproduzível e ponto-no-tempo do estado da frota/veículo em um instante t, sem bloquear a ingestão ao vivo — mesma ideia do 'time travel' do Manu (checkpoint + replay de WAL).

### Replicação Paxos + failover automático + resharding (alta disponibilidade)  
**Fonte:** Spanner-Corbett2012 · **Ementa:** Parte I  
Spanner fragmenta os dados em grupos de máquinas de estado Paxos com líderes de longa duração (leases de 10s) sobre o file system distribuído Colossus, e faz resharding, migração e failover automáticos entre réplicas para disponibilidade e localidade. O relato do cliente F1 mostra que o failover automático foi 'quase invisível' e eliminou o resharding manual doloroso do MySQL sharded.  
**Aplicação:** Fundamenta os requisitos de alta disponibilidade e 'sem perda de pacotes' e os fundamentos de SBD distribuídos da Parte I (computação distribuída, replicação, tolerância a falhas) para uma frota conectada que precisa estar sempre disponível.

### Diretório: unidade de localidade/colocação por escolha de chave  
**Fonte:** Spanner-Corbett2012 · **Ementa:** Parte IV  
O 'directory' (conjunto de chaves contíguas com prefixo comum) é a unidade de placement e de movimentação de dados entre grupos Paxos, e todas as chaves de um diretório compartilham a configuração de replicação. Ao escolher chaves com cuidado — chaves primárias e tabelas INTERLEAVE — a aplicação controla a localidade, colocando fisicamente junto o que é acessado junto (ex.: os dados de cada usuário no seu próprio diretório).  
**Aplicação:** Fundamenta a modelagem de chave por vehicle_id (particionamento e clustering) na telemetria (Cassandra) e no Kafka: co-localizar e ordenar juntos os dados de um mesmo veículo para localidade de acesso e ordem por partição.

### Modelo de programação Map/Reduce (paralelização automática)  
**Fonte:** Dean2004 — MapReduce-Dean2004.txt · **Ementa:** Parte III  
MapReduce é um modelo de programação em que o usuário escreve apenas map (par chave/valor -> pares intermediários) e reduce (mescla valores da mesma chave), e o runtime cuida sozinho de particionar dados, escalonar, tratar falhas de máquina e balancear carga (Seções 1-2). Restringir o modelo é o que permite paralelizar e distribuir automaticamente sobre milhares de PCs commodity. Foi a base do reescrita do sistema de indexação do Google, reduzindo ~3800 linhas para ~700.  
**Aplicação:** Fundamenta o paradigma de processamento em lote da camada Spark (hot path de emergências + batch e ingestão Delta Bronze->Silver->Gold no MinIO). Justifica por que expressamos agregações da frota (contagens, sumarizações financeiras, matriz da cadeia de Markov de ocupação de pátios) como transformações declarativas cuja distribuição/tolerância a falhas fica a cargo do motor, e não do código do grupo.

### Tolerância a falhas por re-execução (worker/master, commits atômicos)  
**Fonte:** Dean2004 — MapReduce-Dean2004.txt · **Ementa:** Parte III  
O mestre faz ping periódico nos workers; tarefas de um worker falho voltam a 'idle' e são reescalonadas em outra máquina (Seção 3.3). Com operadores determinísticos, o resultado distribuído é idêntico ao de uma execução sequencial, garantido por commits atômicos (rename atômico da saída). A re-execução é o mecanismo primário de tolerância a falhas, tornando o sistema resiliente a falhas em larga escala (grupos de 80 máquinas caídas continuam progredindo).  
**Aplicação:** Sustenta o requisito de 'sem perda de pacotes' e alta disponibilidade: a recuperação por reprocessamento determinístico é o modelo adotado por Spark e Flink na nossa pipeline. Justifica desenhar transformações idempotentes/determinísticas sobre a telemetria para que reprocessos (após falha de nó) produzam o mesmo estado Gold.

### Otimização de localidade (mover computação para os dados)  
**Fonte:** Dean2004 — MapReduce-Dean2004.txt · **Ementa:** Parte I  
Largura de banda de rede é recurso escasso; o mestre escalona cada tarefa map na máquina (ou próximo) que contém uma réplica do bloco de entrada gerido pelo GFS, de modo que a maioria dos dados é lida localmente sem consumir rede (Seção 3.4). Essa ideia deriva de 'active disks': empurrar computação para perto do disco.  
**Aplicação:** Fundamenta duas decisões: (1) a computação de borda (computador de bordo/Edge) que pré-processa e agrega no veículo antes de transmitir, poupando a banda móvel 'cara e finita'; (2) o escalonamento por localidade do Spark sobre o MinIO, lendo partições onde residem. Princípio central de computação distribuída (Parte I).

### Particionamento por chave e garantia de ordenação dentro da partição  
**Fonte:** Dean2004 — MapReduce-Dean2004.txt · **Ementa:** Parte III  
As chaves intermediárias são distribuídas por uma função de partição (padrão hash(key) mod R), e o usuário pode customizá-la — por exemplo, hash(Hostname(url)) mod R para que todas as entradas de um mesmo host caiam na mesma saída (Seção 4.1). Dentro de cada partição, os pares são processados em ordem crescente de chave (Seção 4.2), o que facilita saídas ordenadas.  
**Aplicação:** Justifica diretamente a decisão de particionar os tópicos Kafka por vehicle_id: coloca todos os eventos de um veículo na mesma partição, preservando a 'ordenação estrita por veículo e timestamp' exigida. A garantia de ordem intra-partição é o alicerce conceitual para o processamento event-time por veículo no Flink.

### Combiner (agregação parcial no lado do produtor)  
**Fonte:** Dean2004 — MapReduce-Dean2004.txt · **Ementa:** Parte III  
Quando a função reduce é comutativa e associativa, um Combiner executa uma mescla parcial na própria máquina do map antes do envio pela rede, reduzindo drasticamente o tráfego (ex.: contagens <the,1> agregadas localmente) (Seção 4.3).  
**Aplicação:** Fundamenta a pré-agregação na borda (Edge) e a redução de granularidade antes do envio ao broker MQTT/Kafka, atacando o gargalo de 'banda móvel cara e finita'. Modela por que sumarizamos telemetria no veículo/ponte em vez de transmitir cada leitura crua.

### Backup tasks / mitigação de stragglers (execução especulativa)  
**Fonte:** Dean2004 — MapReduce-Dean2004.txt · **Ementa:** Parte III  
Máquinas lentas ('stragglers') dominam o tempo total; perto do fim o mestre dispara execuções de backup das tarefas restantes e aceita a primeira que concluir, cortando o tempo total (ex.: sort 44% mais lento sem backup) com custo de recursos de poucos por cento (Seção 3.6).  
**Aplicação:** Justifica confiar na execução especulativa nativa de Spark/Flink para cumprir SLA de latência do dashboard de emergências e do hot path, evitando que um nó degradado atrase respostas críticas (apoio a emergências em tempo hábil).

### Falhas de componentes são a norma (projeto para hardware commodity)  
**Fonte:** Ghemawat2003 — GFS-Ghemawat2003.txt · **Ementa:** Parte I  
Em clusters de milhares de máquinas commodity, falhas de disco, memória, rede e software são rotineiras, não excepcionais; portanto monitoramento constante, detecção de erro, tolerância a falhas e recuperação automática devem ser integrais ao sistema (Seção 1 e 2.1). Essa premissa reorienta todo o espaço de projeto de sistemas distribuídos.  
**Aplicação:** É a premissa filosófica (Parte I: computação distribuída e SBD distribuídos) por trás de toda a stack: réplicas em Kafka/Cassandra, Delta como fonte da verdade recuperável, e containers reconstituíveis via docker-compose. Justifica assumir falhas como estado normal do consórcio de 6 locadoras.

### Arquitetura master único + chunkservers + replicação (metadados na memória)  
**Fonte:** Ghemawat2003 — GFS-Ghemawat2003.txt · **Ementa:** Parte III  
Um master mantém todos os metadados (namespace, mapeamento arquivo->chunks, localizações) em memória, enquanto os dados são divididos em chunks de 64MB replicados (3x por padrão) em chunkservers; os clientes falam com o master só para metadados e trocam dados diretamente com os chunkservers, evitando gargalo (Seções 2.3-2.6). GFS é o ancestral direto do HDFS.  
**Aplicação:** Fundamenta a escolha de um data lake de objetos (MinIO/S3-compatível) como camada de armazenamento distribuído e replicado, e a separação entre plano de metadados e plano de dados — exatamente o modelo HDFS citado na Parte III da ementa (Data Lakes, HDFS, cloud stores).

### Carga append-only e Atomic Record Append (filas produtor-consumidor)  
**Fonte:** Ghemawat2003 — GFS-Ghemawat2003.txt · **Ementa:** Parte III  
A observação de que a maioria dos arquivos é mutada por append (escritas aleatórias praticamente inexistem) levou ao record append: centenas de produtores em máquinas distintas anexam concorrentemente ao mesmo arquivo com atomicidade 'pelo menos uma vez' e sincronização mínima (Seções 2.1, 3.3). Esses arquivos servem como filas produtor-consumidor e merge multi-via.  
**Aplicação:** Modela a natureza da telemetria (série temporal só de acréscimo) e fundamenta o log de commit append-only — exatamente a semântica do log do Kafka e do transaction log do Delta Lake. Sustenta a ingestão concorrente e de alta vazão de muitos veículos sem locks distribuídos.

### Modelo de consistência relaxado + registros auto-validáveis/idempotência  
**Fonte:** Ghemawat2003 — GFS-Ghemawat2003.txt · **Ementa:** Parte III  
GFS oferece consistência relaxada (regiões 'defined' vs 'consistent but undefined') e transfere às aplicações técnicas simples: preferir append a overwrite, checkpointing e escrever registros auto-validáveis e auto-identificáveis, filtrando duplicatas por IDs únicos (Seções 2.7.1-2.7.2). O record append pode inserir padding/duplicatas que o leitor descarta.  
**Aplicação:** Fundamenta a camada Bronze como zona bruta imutável (append) e o desenho de deduplicação por chave (vehicle_id + timestamp) nas transições Silver/Gold. Antecipa o trade-off CAP/BASE (Parte IV) e a ética de dados (Parte III) ao tratar entrega 'at-least-once' com filtragem de duplicatas.

### Log de operações como linha do tempo lógica (ordem total, replicado)  
**Fonte:** Ghemawat2003 — GFS-Ghemawat2003.txt · **Ementa:** Parte III  
O operation log é o único registro persistente dos metadados e serve como linha do tempo lógica que define a ordem das operações concorrentes; é replicado em várias máquinas e só se responde ao cliente após o flush local e remoto, com checkpoints para acelerar recuperação (Seção 2.6.3). Arquivos/chunks são identificados eternamente pelos tempos lógicos de criação.  
**Aplicação:** Fundamenta a arquitetura log-cêntrica do projeto: Kafka como log de commit ordenado da frota e o transaction log do Delta como 'fonte da verdade'. Justifica derivar todo o estado (Cassandra, MongoDB, Redis, DW Gold) por replay ordenado do log.

### Integridade de dados por checksumming  
**Fonte:** Ghemawat2003 — GFS-Ghemawat2003.txt · **Ementa:** Parte III  
Cada chunkserver quebra o chunk em blocos de 64KB com checksum de 32 bits e verifica antes de retornar dados, de modo que corrupções não se propagam; ao detectar mismatch, lê-se de outra réplica e o master clona o chunk (Seção 5.2). A verificação é otimizada para o caso dominante de append.  
**Aplicação:** Fundamenta a garantia de 'sem perda de pacotes' e não-corrupção da telemetria: justifica validação/checksum na ponte MQTT->Kafka e o uso de formatos com verificação de integridade (Avro/Parquet-Delta) na ingestão, entregando dossiês íntegros para regulação de emergências.

### Modelo de dados wide-column: mapa esparso, distribuído, ordenado e multidimensional  
**Fonte:** Chang2006 — Bigtable-Chang2006.txt · **Ementa:** Parte IV  
Bigtable é um mapa esparso, persistente e ordenado indexado por (linha, coluna, timestamp) -> bytes não interpretados, dando ao cliente controle dinâmico sobre layout e localidade dos dados (Seção 2). Não é modelo relacional pleno; é o ancestral direto do Apache Cassandra.  
**Aplicação:** Fundamenta diretamente a escolha de Cassandra (wide-column) para a telemetria na persistência poliglota: linha = vehicle_id, colunas de sensores, versões por timestamp de microssegundo. Encaixa no item 'wide-column: Cassandra/Bigtable' da Parte IV.

### Chave de linha ordenada e tablets (localidade e distribuição)  
**Fonte:** Chang2006 — Bigtable-Chang2006.txt · **Ementa:** Parte IV  
Os dados são mantidos em ordem lexicográfica pela row key; faixas de linhas (tablets) são a unidade de distribuição e balanceamento, e o cliente escolhe chaves para obter localidade (ex.: URL invertida agrupa páginas do mesmo domínio) (Seção 2, Rows). Leituras de faixas curtas tocam poucas máquinas.  
**Aplicação:** Fundamenta o desenho da chave de particionamento/clustering no Cassandra: partition key = vehicle_id e clustering por timestamp, garantindo varreduras eficientes de janela temporal por veículo — base física para atender a 'ordenação estrita por veículo e timestamp' nas consultas do dashboard.

### Column families (unidade de acesso, localidade e compressão)  
**Fonte:** Chang2006 — Bigtable-Chang2006.txt · **Ementa:** Parte IV  
Colunas se agrupam em famílias, a unidade básica de controle de acesso e de contabilização de disco/memória; dados de uma família são comprimidos juntos e podem ir para 'locality groups' separados para leituras eficientes (Seções 2 Column Families e 6). Poucas famílias, muitas colunas.  
**Aplicação:** Fundamenta a modelagem de colunas da telemetria no Cassandra e o controle de acesso por família para privacidade (Parte III: ética/privacidade) — separando dados sensíveis (usados no dossiê de emergência/regulação) de dados operacionais frequentes.

### Versionamento por timestamp e garbage collection de versões  
**Fonte:** Chang2006 — Bigtable-Chang2006.txt · **Ementa:** Parte IV  
Cada célula guarda múltiplas versões indexadas por timestamp (int64), lidas em ordem decrescente; políticas por família permitem manter só as últimas N versões ou apenas as recentes (ex.: últimos 7 dias), com GC automático (Seção 2 Timestamps).  
**Aplicação:** Fundamenta o versionamento nativo da série temporal por veículo e a política de retenção da telemetria no Cassandra (janelas móveis), controlando volume e custo de armazenamento sem código extra de expurgo.

### Motor de armazenamento LSM: memtable + SSTable imutável + commit log + compaction  
**Fonte:** Chang2006 — Bigtable-Chang2006.txt · **Ementa:** Parte III  
Escritas vão para um commit log (redo) e para um buffer ordenado em memória (memtable); ao atingir limite, a memtable vira uma SSTable imutável em disco, e compactações (minor/merging/major) mesclam SSTables, sendo análogas à Log-Structured Merge-Tree (Seções 5.3-5.4, 6). SSTables imutáveis simplificam concorrência e split rápido de tablets.  
**Aplicação:** Explica por que Cassandra (mesmo motor LSM) suporta a altíssima vazão de escrita da telemetria com alta concorrência do nosso cenário. Fundamenta a expectativa de desempenho write-optimized da camada de telemetria e o padrão de imutabilidade também presente nas SSTables/Parquet.

### Infra em camadas: Bigtable sobre GFS + coordenação por Chubby (Paxos)  
**Fonte:** Chang2006 — Bigtable-Chang2006.txt · **Ementa:** Parte I  
Bigtable é construído sobre outras peças: usa GFS para logs/dados, um sistema de gestão de cluster, e o serviço de lock/consenso Chubby (5 réplicas, Paxos) para eleger o master, descobrir tablet servers e guardar esquema/ACLs (Seções 4-5). Simplicidade e reuso de infraestrutura são lições centrais (Seção 9).  
**Aplicação:** Fundamenta a decisão arquitetural de compor serviços especializados em camadas (broker MQTT -> Kafka -> processamento -> persistência poliglota -> apresentação) em vez de um monólito, e o papel de um serviço de coordenação/consenso (análogo Kafka/ZooKeeper) — princípio de SBD distribuídos da Parte I.

### Atomicidade por linha e ausência de transações cross-row (ACID vs BASE)  
**Fonte:** Chang2006 — Bigtable-Chang2006.txt · **Ementa:** Parte IV  
Toda leitura/escrita sob uma única row key é atômica, e há transações single-row (read-modify-write), mas deliberadamente não há transações gerais entre linhas — a lição foi adiar recursos até o uso ficar claro, e a maioria das aplicações só precisa de transação de linha única (Seções 2 Rows, 3 e 9).  
**Aplicação:** Fundamenta o trade-off BASE da telemetria (Parte IV: CAP, ACID vs BASE, persistência poliglota): consistência forte por veículo (linha) é suficiente, enquanto a consistência forte transacional fica reservada ao motor de cobrança/DW relacional em PostgreSQL, justificando a divisão poliglota.

### RDD: dataset distribuído tolerante a falhas por linhagem (lineage)  
**Fonte:** Zaharia2012 — SparkRDD-Zaharia2012.txt · **Ementa:** Parte III  
RDD é uma coleção particionada, somente-leitura, criada por transformações determinísticas de granularidade grossa (map, filter, join); em vez de replicar dados, registra-se a linhagem das transformações, de modo que uma partição perdida é recomputada a partir dos pais, sem rollback global (Seções 1-2). Isso dá tolerância a falhas barata e reuso em memória.  
**Aplicação:** É o núcleo teórico da camada Spark do projeto (hot path de emergências, batch e ETL Delta). Fundamenta a recuperação eficiente por recomputação de partições perdidas em vez de replicação cara, adequada ao processamento das emergências e da matriz de Markov.

### Transformações coarse-grained vs. atualizações fine-grained (DSM)  
**Fonte:** Zaharia2012 — SparkRDD-Zaharia2012.txt · **Ementa:** Parte III  
Diferente de memória compartilhada distribuída (DSM), que exige replicação ou log de cada escrita, RDDs só se escrevem por transformações em massa; isso restringe a aplicações de escrita em bulk, mas viabiliza tolerância a falhas eficiente, mitigação de stragglers por backup e escalonamento por localidade (Seção 2.3, Tabela 1). Não servem para atualizações assíncronas fine-grained (ex.: crawler incremental).  
**Aplicação:** Justifica a divisão de responsabilidades: Spark (bulk/analítico sobre RDD/DataFrame) para ETL e lote, enquanto atualizações fine-grained de estado ao vivo ficam em Redis (cache) e Cassandra — separação que a própria Parte IV chama de persistência poliglota.

### Reuso em memória para algoritmos iterativos e consultas interativas  
**Fonte:** Zaharia2012 — SparkRDD-Zaharia2012.txt · **Ementa:** Parte III  
Persistir resultados intermediários em RAM evita I/O, replicação e serialização entre passos, dando até 20x de aceleração em algoritmos iterativos (regressão logística, k-means, PageRank) e latência de 5-7s ao varrer 1TB interativamente (Seções 1, 3.2, 6). É o diferencial frente a encadear jobs MapReduce.  
**Aplicação:** Fundamenta o cálculo iterativo da cadeia de Markov (matriz estocástica) de ocupação de pátios e o scoring/ML sobre a frota, além de consultas interativas do dashboard Streamlit — casos iterativos/interativos exatamente onde Spark supera Hadoop clássico.

### Avaliação preguiçosa, DAG de estágios e dependências narrow vs. wide  
**Fonte:** Zaharia2012 — SparkRDD-Zaharia2012.txt · **Ementa:** Parte III  
Transformações são lazy; ao disparar uma ação, o escalonador monta um DAG de estágios, faz pipelining das dependências narrow dentro de um estágio e coloca fronteiras de estágio (shuffle) nas dependências wide (Seções 2.2, 4-5.1). Dependências narrow também recuperam falhas de forma mais barata (só as partições pais perdidas).  
**Aplicação:** Fundamenta o modelo de execução das pipelines ETL Bronze->Silver->Gold no Spark e a expectativa de custo de shuffle. Orienta escrever transformações que maximizem pipelining narrow para reduzir movimentação de dados na ingestão de telemetria.

### Controle de particionamento para co-localizar joins (evitar shuffle)  
**Fonte:** Zaharia2012 — SparkRDD-Zaharia2012.txt · **Ementa:** Parte III  
O usuário pode fixar o Partitioner de um RDD (ex.: hash por URL) e particionar outro do mesmo modo, de forma que o join não exija comunicação — no PageRank isso elevou o speedup de 2.4x para 7.4x, e o particionamento consistente entre iterações replica o que frameworks como Pregel fazem (Seções 3.2.2, 4).  
**Aplicação:** Reforça a decisão de particionar por vehicle_id de ponta a ponta (Kafka -> Spark/Flink): joins e agregações por veículo tornam-se locais, sem shuffle, atendendo desempenho e a ordenação por veículo. Alinha a estratégia de partição entre streaming e batch.

### Checkpointing para linhagens longas (com dependências wide)  
**Fonte:** Zaharia2012 — SparkRDD-Zaharia2012.txt · **Ementa:** Parte III  
Quando a linhagem cresce muito (ou tem dependências wide), recomputar fica caro e um único nó falho pode obrigar recomputação total; então convém materializar checkpoints em armazenamento estável, o que é simples porque RDDs são imutáveis (pode ser em background, sem snapshot global) (Seções 2.3, 5.4, 6.3). Para linhagens narrow sobre dados estáveis, checkpoint raramente compensa.  
**Aplicação:** Fundamenta o papel do Delta Lake como ponto de materialização/checkpoint durável (fonte da verdade) entre etapas de streaming e batch, cortando tempo de recuperação do hot path de emergências e das cargas iterativas (Markov/ML) com linhagem longa.

### DataFrame API: integração de processamento relacional e procedural  
**Fonte:** Armbrust2015 — SparkSQL-Armbrust2015.txt · **Ementa:** Parte III  
Spark SQL introduz o DataFrame — coleção distribuída de linhas com esquema, avaliada de forma preguiçosa — que mescla consultas declarativas (where, groupBy, join) com o código procedural do Spark e passa por um otimizador relacional, algo impossível no RDD cru cujas funções são opacas ao motor (Seções 1, 3). Combina o melhor de SQL e programação geral.  
**Aplicação:** Fundamenta a implementação da ELT de alta performance (Parte II) e das transformações Bronze->Silver->Gold em Spark, e a materialização do DW estrela como camada Gold do Lakehouse. Habilita o dashboard analítico (frota/emergências/financeiro) com consultas declarativas otimizadas.

### Catalyst: otimizador extensível baseado em regras sobre árvores  
**Fonte:** Armbrust2015 — SparkSQL-Armbrust2015.txt · **Ementa:** Parte II  
Catalyst é um otimizador construído com pattern-matching de Scala que aplica regras componíveis em quatro fases — análise, otimização lógica, planejamento físico (com custo) e geração de código para bytecode via quasiquotes — e expõe pontos de extensão para novas fontes, regras e tipos (Seção 4). O codegen o torna competitivo com engines em C++/LLVM como Impala.  
**Aplicação:** Fundamenta a decisão de usar Spark SQL como motor de ELT/consulta de alta performance da camada Gold (Parte II: ETL->ELT, otimização/escala) e demonstra a convergência DW + Big Data (Parte I) num único motor que otimiza automaticamente as consultas do consórcio.

### Cache colunar em memória com compressão  
**Fonte:** Armbrust2015 — SparkSQL-Armbrust2015.txt · **Ementa:** Parte II  
Spark SQL materializa dados quentes em armazenamento colunar em memória, aplicando esquemas como dictionary e run-length encoding, o que reduz a pegada de memória em uma ordem de magnitude frente a objetos JVM — especialmente útil para consultas interativas e algoritmos iterativos de ML (Seção 3.6).  
**Aplicação:** Fundamenta o uso de formato colunar (Parquet/Delta) na camada Gold do Lakehouse e a compressão/otimização de armazenamento que a Parte II exige (compressão, colunar, OLAP), acelerando as consultas do dashboard financeiro e de frota.

### Data Source API com predicate/projection pushdown e federação de consultas  
**Fonte:** Armbrust2015 — SparkSQL-Armbrust2015.txt · **Ementa:** Parte III  
Fontes de dados implementam interfaces (TableScan, PrunedScan, PrunedFilteredScan, CatalystScan) que permitem empurrar projeções e filtros para o armazenamento (JDBC/RDBMS, Parquet, e planejado HBase/Cassandra), viabilizando federação: um único programa consulta fontes heterogêneas minimizando dados transferidos (Seções 4.4.1, 5.3).  
**Aplicação:** Fundamenta a persistência poliglota unificada por consulta (Parte IV) e o conceito de Data Fabric (Parte III): o Spark SQL federa Delta (Gold), Cassandra (telemetria), MongoDB (cadastrais/dossiês) e o PostgreSQL do DW, empurrando filtros a cada fonte para eficiência.

### Inferência de esquema para dados semiestruturados (JSON/Avro)  
**Fonte:** Armbrust2015 — SparkSQL-Armbrust2015.txt · **Ementa:** Parte III  
Um algoritmo de passe único infere o esquema de coleções JSON/semiestruturadas via uma operação de reduce que mescla, com uma função associativa de 'supertipo mais específico', os esquemas de cada registro — permitindo consultar imediatamente dados que evoluem no tempo, com suporte de primeira classe a tipos complexos (structs, arrays, maps) (Seções 3.2, 5.1).  
**Aplicação:** Fundamenta a ingestão da camada Bronze de sensores/eventos semiestruturados e dos documentos de dossiê (MongoDB) e do payload Avro do simulador, permitindo consultar dados brutos sem ETL rígido prévio e lidar com esquemas que mudam (novos sensores/câmeras 360°).

### UDFs inline e DataFrames como representação de pipelines de ML  
**Fonte:** Armbrust2015 — SparkSQL-Armbrust2015.txt · **Ementa:** Parte III  
Spark SQL permite registrar UDFs inline em Scala/Java/Python (inclusive chamando a API distribuída internamente) e a MLlib adota DataFrames como formato de troca de um pipeline de ML (tokenizer -> featurizer -> modelo), tornando etapas componíveis e expostas em todas as linguagens e até em SQL (Seções 3.7, 5.2). Suporta ainda tipos definidos pelo usuário (ex.: vetores).  
**Aplicação:** Fundamenta a orquestração de IA sobre Spark SQL (Parte III: ML pipelines + Spark SQL): pipelines de featurização/scoring da frota, preparação de dados para o RAG local e o PLN por regras do concierge, tudo expresso como transformações de DataFrame — sem depender de chave de LLM paga.

### Kafka como log distribuído particionado (event bus de ingestão)  
**Fonte:** Kafka-Kreps2011 · **Ementa:** Parte III  
Kafka combina os benefícios de agregadores de log e sistemas de mensageria: é distribuído, escalável, de alto throughput e serve consumo online e offline com um único software. Produtores publicam em tópicos, mensagens ficam em brokers e consumidores assinam e puxam os dados. No LinkedIn processava centenas de GB/dia com latência fim-a-fim de ~10s.  
**Aplicação:** Fundamenta o Kafka como barramento central que recebe a telemetria vinda da ponte MQTT e desacopla o simulador de frota dos consumidores analíticos (Flink/Spark), unificando o caminho online (dashboard/emergências) e o offline (Delta/batch) num único sistema.

### Particionamento por chave semântica; partição = unidade mínima de paralelismo  
**Fonte:** Kafka-Kreps2011 · **Ementa:** Parte III  
Um tópico é dividido em partições distribuídas entre brokers; a partição é a menor unidade de paralelismo e é consumida por um único consumidor dentro de cada consumer group. O produtor pode rotear por uma função de particionamento/chave, garantindo que todas as mensagens de uma mesma chave caiam na mesma partição e cheguem a um único processo consumidor, sem necessidade de locking/coordenação.  
**Aplicação:** Justifica particionar os tópicos Kafka por vehicle_id: dá paralelismo horizontal entre veículos e, simultaneamente, coloca toda a telemetria de um veículo na mesma partição/consumidor — base tanto da ordenação estrita quanto do estado por veículo no Flink.

### Garantia de ordenação estrita dentro de uma partição  
**Fonte:** Kafka-Kreps2011 · **Ementa:** Parte III  
Kafka garante que mensagens de uma única partição são entregues ao consumidor exatamente na ordem em que foram anexadas ao log; não há garantia de ordenação entre partições distintas.  
**Aplicação:** Atende diretamente ao requisito de 'ordenação estrita por veículo e timestamp': como cada veículo mapeia para uma partição, a ordem dos eventos por veículo é preservada fim-a-fim sem precisar de coordenação/ordenação global.

### Consumo pull-based com rewind/replay por offset gerenciado pelo consumidor  
**Fonte:** Kafka-Kreps2011 · **Ementa:** Parte III  
Kafka adota modelo pull: cada consumidor puxa na taxa máxima que sustenta, evitando ser inundado. As mensagens são endereçadas por offset lógico no log e o offset consumido é mantido pelo próprio consumidor (broker stateless), permitindo rebobinar e reprocessar dados após um erro de aplicação — recurso essencial para as cargas ETL no DW/Hadoop.  
**Aplicação:** Sustenta o reprocessamento das camadas Delta (Bronze->Silver->Gold): se um job Spark falhar ou a lógica mudar, o consumidor rebobina o offset e reprocessa; e cada consumidor (Flink hot path vs Spark batch) lê o mesmo tópico na própria cadência.

### Broker stateless com retenção temporal e transferência zero-copy (page cache/sendfile)  
**Fonte:** Kafka-Kreps2011 · **Ementa:** Parte III  
O broker não guarda estado de consumo; usa layout de log em segmentos, o page cache do SO e a API sendfile (zero-copy) para atingir throughput linear até muitos TB. As mensagens são retidas por um SLA temporal (ex.: 7 dias) independentemente de terem sido consumidas, o que viabiliza consumidores online e offline sobre os mesmos dados.  
**Aplicação:** Justifica o Kafka como buffer durável que desacopla produtor e consumidores sob banda móvel cara e finita; a janela de retenção permite ao Spark batch consumir mais tarde sem exigir consumo imediato, e mitiga a 'perda de pacotes' ao persistir a telemetria antes do processamento.

### Serialização Avro com schema registry e envio em lote (batching)  
**Fonte:** Kafka-Kreps2011 · **Ementa:** Parte III  
O LinkedIn usa Avro por ser eficiente e suportar evolução de schema: cada mensagem carrega o id do schema e os bytes serializados, com um schema registry leve garantindo o contrato entre produtores e consumidores. Enviar mensagens em lote (batch 50 vs 1) elevou o throughput em quase uma ordem de grandeza (de 50k para 400k msg/s) ao amortizar o overhead de RPC.  
**Aplicação:** Fundamenta a escolha de Avro no simulador de frota e do schema registry como contrato entre a borda (Edge) e os consumidores; o batching é a técnica que conserva a banda móvel cara ao amortizar o overhead por mensagem.

### Entrega at-least-once por padrão; deduplicação a cargo da aplicação  
**Fonte:** Kafka-Kreps2011 · **Ementa:** Parte III  
Kafka garante at-least-once; exactly-once exigiria two-phase commit, considerado desnecessário e custoso para log. Na falha de um consumidor, o que assume a partição pode receber duplicatas posteriores ao último offset comitado, cabendo à aplicação deduplicar via offsets ou chave única — abordagem mais barata que 2PC.  
**Aplicação:** Orienta a combinar Kafka (at-least-once) com exactly-once a jusante no Flink (via snapshots) e escritas idempotentes no Delta, satisfazendo o 'sem perda de pacotes' sem pagar o custo de two-phase commit no broker.

### Consumer groups e rebalanceamento para balanceamento de carga  
**Fonte:** Kafka-Kreps2011 · **Ementa:** Parte III  
Kafka agrupa consumidores em consumer groups: cada mensagem vai a apenas um consumidor do grupo, e o rebalanceamento (coordenado de forma descentralizada via Zookeeper) redistribui partições quando brokers/consumidores entram ou saem. Sobre-particionar o tópico (mais partições que consumidores) é o que permite balanceamento fino.  
**Aplicação:** Atende ao requisito de 'balanceamento' sob alta concorrência: sobre-particionar por vehicle_id permite escalar consumidores Flink/Spark elasticamente, com rebalanceamento automático em manutenção ou falha de nós.

### Discretized Streams (D-Streams): micro-batches determinísticos e stateless  
**Fonte:** SparkStreaming-Zaharia2013 · **Ementa:** Parte III  
D-Streams estruturam a computação de stream como uma série de tarefas batch curtas, stateless e determinísticas sobre pequenos intervalos de tempo, guardando o estado em RDDs em memória. O modelo alcança latência sub-segundo e throughput de 60M+ registros/s em 100 nós, sendo 2–5x mais rápido que Storm/S4.  
**Aplicação:** Fundamenta o uso do Spark (micro-batch) no hot path de emergências e na ingestão batch Delta, oferecendo processamento determinístico e reproduzível sobre os lotes lidos do Kafka.

### Recuperação por linhagem (RDD), paralela e com especulação para stragglers  
**Fonte:** SparkStreaming-Zaharia2013 · **Ementa:** Parte III  
Em vez de replicação 2x ou upstream backup serial (lento), D-Streams rastreiam a linhagem das operações determinísticas e recomputam em paralelo, por todo o cluster, as partições RDD perdidas — recuperando em 1–2s mesmo com checkpoint a cada 30s. Nós lentos (stragglers) são tratados com execução especulativa, como nos sistemas batch, algo inviável em operadores contínuos.  
**Aplicação:** Justifica a robustez do caminho Spark (batch/hot path) sem o custo de replicação: falhas e nós lentos no cluster de containers são absorvidos por recomputação paralela via linhagem.

### Consistência exactly-once por discretização determinística do tempo  
**Fonte:** SparkStreaming-Zaharia2013 · **Ementa:** Parte III  
Como o tempo é discretizado em intervalos e cada RDD de saída reflete toda a entrada daquele intervalo e dos anteriores, D-Streams oferecem semântica de consistência clara e processamento 'exactly-once' no cluster, evitando os estados inconsistentes entre nós dos sistemas record-at-a-time (onde um nó pode ficar para trás de outro).  
**Aplicação:** Fundamenta agregados financeiros/operacionais consistentes no Spark (ex.: totalizações para a cobrança automática pós-uso), onde inconsistência entre nós ou dupla contagem seria inaceitável.

### Unificação de streaming, batch e consultas interativas na mesma engine (RDD)  
**Fonte:** SparkStreaming-Zaharia2013 · **Ementa:** Parte III  
Por usarem o mesmo modelo, as mesmas estruturas (RDDs) e a mesma tolerância a falhas do batch, os D-Streams combinam-se com RDDs estáticos: pode-se juntar um stream com dados históricos, rodar o mesmo programa em 'modo batch' sobre dados passados, e fazer consultas ad-hoc interativas sobre o estado do stream.  
**Aplicação:** Base para o Spark unir dados ao vivo com o histórico Delta (Silver/Gold) — ex.: enriquecer um evento de emergência com o cadastro/histórico do veículo — sustentando hot path + batch numa engine só (aproximação prática de Lambda).

### Operadores de saída idempotentes  
**Fonte:** SparkStreaming-Zaharia2013 · **Ementa:** Parte III  
Operadores de saída como save são projetados idempotentes: cada intervalo grava em um caminho conhecido e não sobrescreve dados de um intervalo já computado, de modo que recomputar um RDD (após falha ou reprocessamento) não corrompe nem duplica a saída.  
**Aplicação:** Justifica escritas idempotentes do Spark nas camadas Delta e nos sinks (Cassandra/MongoDB), garantindo que recuperações/reprocessamentos não gerem cobranças ou registros duplicados.

### Flink: dataflow único para stream e batch (batch como caso especial de stream)  
**Fonte:** Flink-Carbone2015 · **Ementa:** Parte III  
Flink assume o processamento de streams como o modelo unificador: todo programa compila para um grafo de dataflow (DAG de operadores stateful) executado por um único runtime de streaming, sendo o batch um caso especial de stream finito. Ajustando o buffer-timeout, atinge 80M+ eventos/s com latência de percentil-99 de 50ms (e até 20ms com throughput menor).  
**Aplicação:** Fundamenta o Flink como motor de análise contínua da frota (rotas, score, janelas), alinhado à stack moderna valorizada, entregando alto throughput e baixa latência sobre a mesma engine.

### Noções de tempo (event/ingestion/processing) e low-watermarks  
**Fonte:** Flink-Carbone2015 · **Ementa:** Parte III  
Flink distingue event-time (quando o evento ocorreu no sensor), ingestion-time e processing-time. Para lidar com o skew entre event-time e o relógio da máquina, insere low-watermarks que marcam o progresso global do event-time, propagados a partir das fontes e, em operadores com múltiplas entradas, tomando o mínimo dos watermarks recebidos. Event-time dá a semântica mais confiável, ainda que com alguma latência.  
**Aplicação:** Justifica diretamente o uso de event-time + watermarks nos jobs Flink: a telemetria dos veículos chega fora de ordem/atrasada pela rede móvel, e os watermarks permitem fechar janelas corretamente pelo timestamp do evento, não pelo de chegada.

### Janelamento flexível: assigner + trigger + evictor  
**Fonte:** Flink-Carbone2015 · **Ementa:** Parte III  
O janelamento em Flink é um operador stateful configurado por três funções: um assigner (atribui cada registro a janelas lógicas), um trigger opcional (quando computar o resultado) e um evictor opcional (quais registros reter). Isso cobre janelas de tempo/contagem/sessão/punctuation e absorve out-of-order de forma transparente; se o stream é particionado por chave, a janela é local e dispensa coordenação entre workers.  
**Aplicação:** Fundamenta as janelas por vehicle_id no Flink para cálculo de rotas e score em janelas deslizantes de event-time, executadas localmente por veículo sem coordenação entre nós.

### Estado gerenciado, particionado por chave, com StateBackend configurável  
**Fonte:** Flink-Carbone2015 · **Ementa:** Parte III  
Flink torna o estado explícito na API (variáveis locais registradas e uma abstração de estado chave-valor particionado) e permite configurar como o estado é armazenado e checkpointado via StateBackend (HDFS, bancos, etc.). O mecanismo de checkpointing garante que qualquer estado registrado seja durável com semântica de atualização exactly-once.  
**Aplicação:** Justifica manter estado por veículo no Flink chaveado por vehicle_id (última posição, acumuladores de rota/score) com durabilidade exactly-once, essencial para a análise contínua e cálculo incremental.

### Exactly-once exige fontes persistentes e replayable  
**Fonte:** Flink-Carbone2015 · **Ementa:** Parte III  
As garantias exactly-once do Flink assumem que as fontes de dados sejam persistentes e replayable — arquivos ou filas duráveis como Apache Kafka. A recuperação reverte os operadores ao último snapshot e reinicia as fontes a partir da última barreira, limitando a recomputação aos registros entre duas barreiras consecutivas.  
**Aplicação:** Fecha o acoplamento Kafka->Flink da arquitetura: o Kafka durável e replayable é precisamente a fonte que habilita a semântica exactly-once do Flink e a recuperação limitada — os dois componentes se justificam mutuamente.

### Troca de dados pipelined com backpressure e buffer-timeout  
**Fonte:** Flink-Carbone2015 · **Ementa:** Parte III  
Os streams intermediários pipelined executam produtores e consumidores concorrentemente e propagam backpressure do consumidor para o produtor (modulado por pools de buffers). Um buffer é enviado ao encher ou ao atingir um timeout, permitindo equilibrar latência (poucos ms com timeout baixo) e throughput (buffers maiores).  
**Aplicação:** Justifica a resiliência do Flink a picos de concorrência da frota: o backpressure regula naturalmente a vazão sem colapso, e o buffer-timeout permite calibrar o trade-off latência/throughput conforme a urgência (emergências vs analytics de rota).

### Asynchronous Barrier Snapshotting (ABS): snapshots consistentes sem parar a execução  
**Fonte:** 10.48550__arXiv.1506.08603 · **Ementa:** Parte III  
O ABS injeta barreiras periódicas nas fontes que fluem por todo o grafo de execução; ao alinhar as barreiras de todas as entradas, cada operador snapshota seu estado e repassa a barreira adiante, sem interromper a computação. Em topologias acíclicas persiste apenas os estados dos operadores (snapshot mínimo, sem registros em trânsito), estendendo Chandy-Lamport; a avaliação em Flink mostra baixo impacto no throughput e escalabilidade linear mesmo com snapshots frequentes.  
**Aplicação:** É o mecanismo concreto de tolerância a falhas exactly-once dos jobs Flink da arquitetura: garante continuidade e ausência de perda com overhead baixo — requisito crítico para o monitoramento 24/7 da frota autônoma.

### Recuperação limitada a partir do último snapshot consistente  
**Fonte:** 10.48550__arXiv.1506.08603 · **Ementa:** Parte III  
A recuperação reverte todos os estados de operadores ao último snapshot bem-sucedido e reinicia as fontes a partir da última barreira; a recomputação máxima fica limitada aos registros entre duas barreiras consecutivas. Snapshots síncronos (estilo Naiad) que param a computação têm alto impacto (bursts que violam SLAs), enquanto o ABS mantém a vazão estável.  
**Aplicação:** Fundamenta um RTO baixo e previsível para o Flink em produção contínua: uma falha não reprocessa horas/meses de fluxo, apenas o intervalo entre barreiras, mantendo dashboard e rotas atualizados e adequados a pipelines latência-crítica como resposta a emergências.

### Requisitos intrínsecos do processamento de streams  
**Fonte:** 10.48550__arXiv.2008.00842 · **Ementa:** Parte III  
Um data stream é produzido incrementalmente, é de alto volume, tempo real e potencialmente ilimitado; o sistema não controla nem a taxa nem a ordem de chegada, e processa on-the-fly com memória limitada em passagem única, exigindo computação incremental. Daí decorrem requisitos além de latência/throughput: gestão de out-of-order, gestão de estado, tolerância a falhas e gestão de carga/elasticidade.  
**Aplicação:** Enquadra os fundamentos da Parte III que justificam toda a camada de tempo real: é por causa desses requisitos que a arquitetura precisa de Kafka (ingestão contínua), Flink (estado + out-of-order) e mecanismos de tolerância a falhas, e não de um banco tradicional.

### Causas de desordem e arquitetura out-of-order vs in-order  
**Fonte:** 10.48550__arXiv.2008.00842 · **Ementa:** Parte III  
A desordem nos streams decorre de fatores externos (a rede, com latência/banda/carga variáveis) e da ingestão de múltiplas fontes não coordenadas (ex.: vários sensores), além de operações internas (joins, janelas). Há dois arquétipos: sistemas in-order (bufferizam e reordenam até um limite, com custo de memória/latência) e sistemas out-of-order (rastreiam progresso via watermarks/punctuations e processam na ordem de chegada até um lateness bound).  
**Aplicação:** Justifica adotar a arquitetura out-of-order (Flink com watermarks) em vez de reordenar tudo: sensores/câmeras 360° dos veículos são múltiplas fontes sobre rede móvel instável — o cenário clássico de desordem descrito pelo survey.

### Gerações de sistemas de streaming: escolha da 2a geração (moderna)  
**Fonte:** 10.48550__arXiv.2008.00842 · **Ementa:** Parte III  
A 1a geração (DSMSs como Aurora/STREAM/Borealis) era scale-up, operava sobre streams ordenados e tinha garantias limitadas; a 2a geração (Storm, Spark Streaming, Flink, Millwheel, Google Dataflow) é distribuída, data-parallel e shared-nothing sobre hardware commodity, convergindo para processamento tolerante a falhas de streams massivos out-of-order, com exactly-once via snapshots distribuídos e fontes replayable.  
**Aplicação:** Fundamenta a escolha deliberada da stack moderna (Kafka+Flink+Spark) valorizada pelo professor, situando o projeto na 2a geração e justificando exactly-once + fontes replayable como padrões de projeto, e não como opcionais.

### Revision processing e triggers (accumulate/discard/retract) para dados tardios  
**Fonte:** 10.48550__arXiv.2008.00842 · **Ementa:** Parte III  
O modelo Dataflow separa três dimensões: o event-time em que dados tardios são processados, o processing-time em que os resultados são materializados, e como atualizações posteriores se relacionam a resultados anteriores. Um trigger decide quando emitir/atualizar um resultado, com políticas de accumulating (sobrescreve), discarding (complementa) e accumulating-and-retracting (sobrescreve e retrata o anterior) para incorporar corretamente dados tardios ou retratados.  
**Aplicação:** Orienta o tratamento de telemetria tardia sem invalidar saídas: janelas com triggers/lateness no Flink podem retratar/atualizar rotas e valores antes de consolidar a cobrança pós-uso, evitando faturar sobre input parcial.

### Crítica à arquitetura Lambda e caminho para processamento unificado (Kappa)  
**Fonte:** Flink-Carbone2015 · **Ementa:** Parte III  
A arquitetura Lambda combina um caminho streaming (resultados rápidos e aproximados) e um caminho batch offline (resultados tardios e exatos), mas sofre de alta latência (imposta pelos lotes), alta complexidade (orquestrar vários sistemas e implementar a lógica de negócio duas vezes) e imprecisão por não tratar o tempo explicitamente. Flink propõe abraçar o stream como modelo unificador, iniciando o processamento em pontos distintos de um stream durável (Kafka/Kinesis) para cobrir tempo real, agregação em janelas grandes e reprocessamento de histórico.  
**Aplicação:** Fundamenta a decisão arquitetural entre Lambda e Kappa: usar Kafka durável + Flink para unificar caminhos reduz a dupla implementação; no projeto, o Flink faz a análise contínua unificada por event-time enquanto o Spark cobre o hot path de emergências e a ingestão batch Delta.

### Separação DW/OLAP vs. OLTP — data warehouse subject-oriented, integrated, time-varying, non-volatile  
**Fonte:** Chaudhuri & Dayal 1997 (10.1145__248603.248616.txt) · **Ementa:** Parte II  
O DW é definido (Inmon) como coleção de dados orientada a assunto, integrada, variante no tempo e não-volátil, mantida SEPARADA dos bancos operacionais porque OLAP tem requisitos funcionais/de desempenho distintos de OLTP: consultas ad hoc complexas com scans/joins/agregados sobre milhões de registros, versus transações curtas, atômicas e isoladas. Rodar OLAP contra o OLTP degrada o throughput transacional; o DW consolida dados históricos de múltiplas fontes heterogêneas. O paper cita explicitamente 'fleet management' em transporte como caso clássico de DW.  
**Aplicação:** Justifica manter a camada analítica (nosso esquema estrela dw_locadora, que passa a ser a Gold do Lakehouse) fisicamente separada dos 4 OLTP das 6 locadoras (app de reserva/cobrança). O dashboard de frota/emergências/financeiro roda OLAP sobre a Gold, nunca sobre os bancos de reserva, preservando o desempenho transacional do app.

### Esquema estrela (star schema): fato central + uma dimensão por eixo, com surrogate keys  
**Fonte:** Chaudhuri & Dayal 1997 (10.1145__248603.248616.txt) · **Ementa:** Parte II  
A maioria dos DWs usa star schema: uma única fact table cujas tuplas guardam medidas numéricas e foreign keys (tipicamente chaves geradas/surrogate por eficiência) para cada dimensão, mais uma dimension table por dimensão com os atributos descritivos. Modelagem ER/normalização, boa para OLTP, é declarada inadequada para decisão porque prioriza minimizar conflito de concorrência em vez de eficiência de query e de carga.  
**Aplicação:** Fundamenta diretamente o modelo aprovado na Avaliação 02 — fatos Reserva, Locação e Movimentação, mais dimensões Tempo, Cliente, Veículo, Empresa e Pátio. Esse star schema em PostgreSQL (schema dw_locadora) é adotado como a camada Gold do Lakehouse a ser estendido.

### Snowflake, dimensões conformadas e fact constellation (múltiplos fatos compartilham dimensões)  
**Fonte:** Chaudhuri & Dayal 1997 (10.1145__248603.248616.txt) · **Ementa:** Parte II  
O snowflake refina o star normalizando as hierarquias das dimensões (ex.: país->estado->cidade), o que facilita a manutenção das dimensões; e fact constellation é quando várias fact tables compartilham as mesmas dimension tables (ex.: despesa projetada e real). As hierarquias das dimensões definem os caminhos de sumarização usados no roll-up.  
**Aplicação:** Nossos três fatos (Reserva/Locação/Movimentação) compartilham as dimensões conformadas Tempo/Cliente/Veículo/Empresa/Pátio: isso é formalmente uma fact constellation. A dimensão Pátio multipapel (retirada/devolução/origem/destino) é role-playing sobre a mesma dimensão conformada, e a hierarquia de Tempo/Pátio sustenta o drill-down do dashboard.

### ETL back-end: extração via gateways/ODBC de múltiplas fontes, limpeza, transformação, carga e refresh incremental  
**Fonte:** Chaudhuri & Dayal 1997 (10.1145__248603.248616.txt) · **Ementa:** Parte II  
O DW é populado por ferramentas de extração de múltiplos bancos operacionais e fontes externas (gateways/ODBC), limpeza (migração de dados, scrubbing com fuzzy matching, auditoria) e utilitários de load. O refresh periódico usa carga incremental (só as tuplas atualizadas), tratada como sequência de transações curtas que commitam periodicamente com checkpoints para reinício após falha, explorando paralelismo pipelined e particionado; dados derivados/índices precisam ser atualizados de forma consistente com a base.  
**Aplicação:** Fundamenta o ETL da Av.02 (5 scripts integrando 4 fontes OLTP com limpeza/conformação). No Lakehouse esse ETL evolui para ELT de alta performance Bronze->Silver->Gold no Spark; o refresh incremental vira ingestão contínua e o mecanismo de checkpoint corresponde ao exactly-once do Spark/Delta.

### Operações OLAP: roll-up, drill-down, slice-and-dice e pivot sobre hierarquias dimensionais  
**Fonte:** Chaudhuri & Dayal 1997 (10.1145__248603.248616.txt) · **Ementa:** Parte II  
O modelo multidimensional expõe medidas numéricas como valores no espaço de dimensões hierárquicas; as operações centrais são roll-up (aumenta o nível de agregação), drill-down (aumenta o detalhe), slice-and-dice (seleção/projeção reduzindo dimensionalidade) e pivot (reorienta a visão). Tempo é destacado como dimensão de especial importância para análise de tendências.  
**Aplicação:** O dashboard de frota faz drill-down frota->empresa->pátio->veículo e roll-up de ocupação/receita por dia->semana->mês (hierarquia de Tempo), slice-and-dice para isolar emergências por região. É a base do BI 4.0 / analytics aumentada sobre a Gold.

### Views materializadas / summary tables (pré-agregação) e seleção de views  
**Fonte:** Chaudhuri & Dayal 1997 (10.1145__248603.248616.txt) · **Ementa:** Parte II  
Como muitas queries de DW usam agregados, materializam-se summary tables pré-agregadas (fato agregado por dimensões selecionadas) para acelerar consultas. Os desafios são: escolher quais views materializar (um algoritmo guloso teve bom desempenho), reescrever a query para usá-las (noção de 'geradores mínimos') e atualizá-las no load/refresh. Fazer roll-up a partir de um resultado parcialmente agregado depende das propriedades algébricas da função (Sum rola; funções estatísticas nem sempre).  
**Aplicação:** A camada Gold guarda agregados pré-computados (ocupação por pátio/tempo, receita por empresa/período) para atender a latência do dashboard. A ressalva de 'roll-up a partir de parcial só se a função permite' conecta-se diretamente à classificação de agregados de Gray e às janelas de pré-agregação do Flink.

### Índices de DW: bitmap index e join index para star schema  
**Fonte:** Chaudhuri & Dayal 1997 (10.1145__248603.248616.txt) · **Ementa:** Parte II  
Servidores de DW usam bitmap indices (vetor de bits por valor de domínio) que aceleram interseção/união/join/agregação via operações lógicas AND/OR — bons para baixa cardinalidade e, com compressão RLE, também para alta. Join indices pré-computam o join fato-dimensão (multikey join index materializa um join n-way do star). Índices e views materializadas são estruturas redundantes cuja escolha é um problema de projeto físico.  
**Aplicação:** Sustenta a otimização/escala da Parte II (indexação, particionamento) no DW PostgreSQL da camada Gold; as queries do dashboard sobre o star schema se apoiam em índices nas FKs das dimensões conformadas para acelerar filtros por empresa/veículo/tempo.

### Paralelismo particionado e servidores ROLAP vs. MOLAP  
**Fonte:** Chaudhuri & Dayal 1997 (10.1145__248603.248616.txt) · **Ementa:** Parte II  
Processar bases massivas exige data partitioning e parallel query (pioneirismo Teradata). ROLAP mapeia o modelo multidimensional para SQL sobre um RDBMS (herdando escalabilidade e transações do relacional); MOLAP guarda arrays multidimensionais (excelente indexação, mas má utilização com dados esparsos — usa storage de 2 níveis e compressão). O warehouse pode ser distribuído/federado para balanceamento, escalabilidade e disponibilidade.  
**Aplicação:** Fundamenta o MPP/particionamento da Parte II: a ingestão particiona por vehicle_id (Kafka/Spark) e a Gold é servida em modo ROLAP sobre PostgreSQL. O consórcio de 6 locadoras corresponde a uma arquitetura federada de data marts, com administração parcialmente descentralizada.

### Repositório de metadados e gestão do warehouse  
**Fonte:** Chaudhuri & Dayal 1997 (10.1145__248603.248616.txt) · **Ementa:** Parte II  
Elemento essencial da arquitetura de DW é o repositório de metadados (esquema, definições de view, scripts, mapeamentos fonte->alvo, regras de negócio) mais ferramentas de monitoramento e administração; em arquitetura distribuída o repositório é replicado com cada fragmento do warehouse.  
**Aplicação:** Sustenta a necessidade de catálogo e linhagem do pipeline. No Lakehouse, o transaction log do Delta atua como essa camada de metadados versionada (registra quais objetos compõem cada versão de tabela), unificando os metadados de Bronze/Silver/Gold sem servidor de metadados dedicado sempre ligado.

### Operador CUBE: generalização N-dimensional de GROUP BY (roll-up, cross-tab, valor ALL)  
**Fonte:** Gray et al. 1997 (DataCube-Gray1997.txt) · **Ementa:** Parte II  
GROUP BY produz agregados 0- ou 1-dimensionais; o operador CUBE generaliza para N dimensões, tratando cada atributo de agregação como um eixo do N-espaço e computando os super-agregados de todas as 2^k combinações de group-by, com um valor especial ALL representando o conjunto agregado em cada eixo. A novidade é que 'cubes são relações', então o operador se encaixa em SQL e em programas de análise não-procedurais, unificando histograma, cross-tab, roll-up, drill-down e subtotais.  
**Aplicação:** É a base formal do OLAP multidimensional do dashboard: um cubo frota x tempo x pátio x empresa com totais e subtotais (ALL) para a visão executiva/financeira (BI 4.0), materializado como agregados na camada Gold.

### Classificação de agregados: distributiva, algébrica e holística  
**Fonte:** Gray et al. 1997 (DataCube-Gray1997.txt) · **Ementa:** Parte II (fundamenta III)  
Funções DISTRIBUTIVAS (COUNT, SUM, MIN, MAX) computam-se a partir de sub-agregados (agregado de agregados); ALGÉBRICAS (AVG, desvio-padrão, MaxN, centro de massa) precisam apenas de uma M-tupla de estado de tamanho fixo (ex.: AVG guarda soma+contagem); HOLÍSTICAS (MEDIAN, MODE, RANK) não têm limite constante de estado. Super-agregados de distributivas/algébricas são calculados eficientemente a partir do 'core' GROUP BY (economia de ~fator T de chamadas), enquanto holísticas exigem o custoso algoritmo 2^N.  
**Aplicação:** Fundamenta a divisão hot-path/batch da arquitetura: as janelas event-time do Flink (particionadas por vehicle_id) calculam incrementalmente, com estado LIMITADO, contagens/scores distributivos e médias algébricas de telemetria; já métricas holísticas (mediana/percentis de latência, valor mais frequente) são deferidas ao batch Spark sobre a Gold. Também justifica pré-agregar a Gold a partir do core Silver.

### Falência da arquitetura de dois níveis (data lake + data warehouse): reliability, staleness, TCO e ML  
**Fonte:** Armbrust et al. 2021 — Lakehouse (Lakehouse-Armbrust2021.txt) · **Ementa:** Parte II  
A arquitetura dominante de dois níveis (dados primeiro ETLados para o lake e depois ELTados para um warehouse) sofre de quatro problemas: reliability (manter lake e warehouse consistentes exige engenharia contínua e introduz falhas/bugs), data staleness (o warehouse fica dias atrasado — 86% dos analistas usam dados desatualizados), suporte limitado a analytics avançado/ML (TensorFlow/PyTorch/XGBoost são mal servidos via ODBC/JDBC sobre warehouses) e alto custo total (ETL contínuo + cópia dupla de storage + lock-in em formato proprietário).  
**Aplicação:** Motiva a decisão central de NÃO manter DW e data lake separados: nossa arquitetura é um Lakehouse único (MinIO + Delta) onde o DW estrela vira a camada Gold. Isso elimina o segundo ETL lake->warehouse, reduz a staleness do dashboard de frota e permite que ML/RAG (concierge, score, previsão) leiam diretamente os mesmos dados.

### Arquitetura Lakehouse: camada de metadados transacional sobre object store barato em formato aberto, com features de DBMS  
**Fonte:** Armbrust et al. 2021 — Lakehouse (Lakehouse-Armbrust2021.txt) · **Ementa:** Parte II  
Um Lakehouse é definido como sistema de gestão de dados sobre storage barato e de acesso direto (S3/Parquet/ORC) que também provê as features analíticas de um DBMS — ACID, versionamento, auditoria, indexação, caching e otimização de queries — através de uma camada de metadados transacional (Delta Lake/Iceberg/Hudi) sobre os arquivos abertos. Combina o baixo custo e o acesso aberto do lake com a gestão e o desempenho do warehouse, sendo especialmente adequado a nuvem com compute e storage separados.  
**Aplicação:** Define a espinha dorsal do sistema: MinIO (object store S3) + Delta (camada transacional) guardando Parquet aberto, organizado em Bronze/Silver/Gold. Spark, Flink, as libs de ML e o concierge/RAG acessam os mesmos arquivos diretamente, e o Delta é a 'fonte da verdade' declarada na arquitetura.

### Otimizações de desempenho independentes de formato: caching de dados quentes, dados auxiliares (min/max/zone maps, Bloom) e data layout (Z-order)  
**Fonte:** Armbrust et al. 2021 — Lakehouse (Lakehouse-Armbrust2021.txt) · **Ementa:** Parte II  
Sem poder alterar o formato aberto, o Lakehouse atinge desempenho competitivo (bate cloud DWs no TPC-DS) com três técnicas: caching de arquivos quentes em SSD/RAM (seguro graças ao log transacional que valida o cache), estruturas de dados auxiliares (estatísticas min/max por arquivo para data skipping, índices Bloom) e otimização de layout (ordenar registros por Z-order/curvas de Hilbert para localidade multidimensional). Queries concentram-se num subconjunto 'quente' cacheado; para dados 'frios', o determinante é minimizar I/O via zone maps.  
**Aplicação:** O Redis do projeto é o cache 'ao vivo' de dados quentes; o Delta mantém min/max por arquivo para pular partições no hot-path de emergências; particionar/ordenar por vehicle_id + tempo (Z-order) dá a localidade necessária para consultas por veículo e por janela temporal.

### APIs DataFrame declarativas ligam ML/Data Science ao Lakehouse (plano avaliado preguiçosamente e otimizado)  
**Fonte:** Armbrust et al. 2021 — Lakehouse (Lakehouse-Armbrust2021.txt) · **Ementa:** Parte II (fundamenta III)  
Bibliotecas de ML adotaram DataFrames como abstração; APIs DataFrame declarativas (Spark SQL) avaliam as transformações de forma preguiçosa e passam o plano ao otimizador, empurrando seleções/projeções para o 'data source' e herdando o caching e o data-skipping do Lakehouse. Assim workloads de ML leem diretamente os arquivos abertos (Parquet) com as mesmas otimizações do SQL, sem o gargalo de exportar via ODBC/JDBC.  
**Aplicação:** O ETL Bronze->Silver->Gold e o cálculo de scores no Spark usam DataFrames declarativos com pushdown; o concierge/RAG e a previsão de ocupação por Cadeias de Markov leem features direto da Gold/Delta, sem copiar dados para um sistema à parte.

### Acesso direto ao object store habilita colaboração distribuída / data mesh e governança por formato aberto  
**Fonte:** Armbrust et al. 2021 — Lakehouse (Lakehouse-Armbrust2021.txt) · **Ementa:** Parte II (fundamenta III)  
Como todos os datasets ficam diretamente acessíveis num object store em formato aberto, designs Lakehouse favorecem estruturas colaborativas distribuídas — o 'data mesh', em que times distintos possuem produtos de dados end-to-end — sem exigir que consumidores sejam onboarded no mesmo compute. O formato aberto também atende exigências crescentes de governança/regulação (buscar, deletar ou migrar dados sem depender de um fornecedor).  
**Aplicação:** O consórcio de 6 locadoras é um cenário multi-produtor/multi-consumidor: cada locadora pode possuir seu produto de dados sobre o object store compartilhado (data mesh). O formato aberto sustenta o dossiê para regulação e os requisitos de governança/privacidade de dados dos clientes.

### Object stores são key-value sem atomicidade cross-key, com consistência eventual e LIST caro  
**Fonte:** Armbrust et al. 2020 — Delta Lake (10.14778__3415478.3415560.txt) · **Ementa:** Parte II (fundamenta III)  
Cloud object stores (S3/ADLS/GCS/MinIO) são key-value baratos e escaláveis, mas sem garantias entre chaves: updates multi-objeto não são atômicos (leitores veem escritas parciais; um update que falha deixa a tabela corrompida), a consistência é eventual (LIST após PUT pode não retornar o objeto novo) e operações de metadados são caras (S3 LIST retorna até 1000 chaves por chamada, dezenas–centenas de ms). Guardar tabelas como 'just a bunch of Parquet files' herda todos esses problemas.  
**Aplicação:** O MinIO do projeto é exatamente um store S3-like com essas limitações; isso motiva usar Delta (e não Parquet cru) como fonte da verdade para garantir escritas atômicas sob a alta concorrência de telemetria de toda a frota.

### Delta Lake: log de transações no próprio object store + concorrência otimista = ACID serializável sem servidor de metadados  
**Fonte:** Armbrust et al. 2020 — Delta Lake (10.14778__3415478.3415560.txt) · **Ementa:** Parte II  
Delta mantém, dentro do próprio object store, um log de transações (registros JSON com ações add/remove de arquivos, mais checkpoints em Parquet) que define quais objetos compõem cada versão da tabela; protocolos de concorrência otimista sobre as operações do store dão isolamento serializável/snapshot SEM precisar de um serviço de metadados sempre ligado (compute e storage escalam separadamente). O log guarda estatísticas min/max por arquivo, tornando buscas de metadados ordens de grandeza mais rápidas (varrer bilhões de partições).  
**Aplicação:** O Delta é a 'fonte da verdade' do Lakehouse: sob alta concorrência, múltiplos jobs Spark/Flink escrevem Bronze/Silver/Gold com garantias ACID; as estatísticas min/max no log aceleram consultas por veículo/tempo no dashboard e no hot-path de emergências.

### Time travel, versionamento, audit log e MERGE/DELETE (uso SIEM/forense e compliance)  
**Fonte:** Armbrust et al. 2020 — Delta Lake (10.14778__3415478.3415560.txt) · **Ementa:** Parte II  
Sobre o log, o Delta oferece time travel (consultar snapshot ponto-no-tempo e fazer rollback de updates errôneos), audit logging e UPSERT/MERGE/DELETE eficientes para compliance (ex.: GDPR — deletar/corrigir dados de um indivíduo). Um dos maiores casos de uso relatados é SIEM: eventos de sistema em tabelas Delta na escala de petabytes, com jobs de streaming/ML/graph detectando intrusões e mais de 100 analistas investigando alertas, com os dados retidos para análise forense meses depois.  
**Aplicação:** O time travel reconstrói o estado ponto-no-tempo do veículo para montar o dossiê de emergência entregue à regulação (análogo direto ao caso SIEM/forense do paper); o audit log dá rastreabilidade; MERGE/DELETE atende à privacidade dos clientes (cadastrais no MongoDB + histórico versionado no Delta).

### Escritas exactly-once em streaming via ação txn (appId/version rastreando offset)  
**Fonte:** Armbrust et al. 2020 — Delta Lake (10.14778__3415478.3415560.txt) · **Ementa:** Parte II (fundamenta III)  
Delta permite que a aplicação grave uma ação txn com campos appId e version no MESMO registro de log das ações add/remove (inserido atomicamente). Assim um job de stream registra, junto com os dados, o offset já commitado; após um crash ele sabe quais escritas já entraram na tabela e retoma do ponto correto, garantindo semântica exactly-once — mecanismo integrado ao Spark Structured Streaming.  
**Aplicação:** A ingestão Kafka -> Spark/Flink -> Delta usa esse mecanismo para não duplicar nem perder telemetria (requisito 'sem perda de pacotes'), commitando o offset atomicamente com os dados e assim preservando a ordenação estrita por vehicle_id + timestamp.

### I/O de streaming e Delta como message bus: unifica fila + lake + warehouse  
**Fonte:** Armbrust et al. 2020 — Delta Lake (10.14778__3415478.3415560.txt) · **Ementa:** Parte II (fundamenta III)  
Delta suporta streaming escrevendo objetos pequenos com baixa latência e coalescendo-os transacionalmente em objetos maiores depois; leituras 'tailing' das novas linhas permitem tratar a tabela como um message bus. Com isso, um pipeline que antes exigia uma fila (Kafka) + object store + dois data warehouses (Figura 1 do paper) é substituído por tabelas Delta em object storage barato, com menos cópias e menos sistemas a manter.  
**Aplicação:** Reforça o hot-path de emergências (ingestão de baixa latência) e a unificação de storage: a Bronze recebe ingestão contínua e é lida em streaming pelas etapas Silver/Gold, reduzindo cópias entre lake e o DW Gold — exatamente a proposta Lakehouse adotada no projeto.

