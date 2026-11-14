// Perguntas da demo respondidas no grafo do Neo4j, com os nomes do grafo: labels = classes, arestas = nome exato das relacoes da ontologia.
// O oraculo e examples/local_demo/gabarito.json, calculado dos CSVs por oracle.py, sem o exportador.
// Cada bloco comeca com "// pergunta: <secao>.<chave do gabarito>" e devolve uma linha com a coluna "resposta".
// Dinheiro e somado em centavos inteiros (cada vl_total arredondado para centavos antes da soma), para a comparacao ser exata.
// Lido e executado por tests/test_neo4j_integration.py::test_real_competency_questions.
// As questoes CQ-002 e CQ-003 de examples/local_demo/questions.yml nao tem valor no oraculo; ver docs/exportacao-neo4j/task-9-aceitacao.md.

// pergunta: direct_answers.clientes_sem_pedido
// Quais clientes nao tem nenhum pedido? Cliente sem aresta pertenceA chegando de um Pedido.
MATCH (c:Cliente) WHERE NOT (c)<-[:pertenceA]-(:Pedido)
WITH c.id_cliente AS id ORDER BY id
RETURN collect(id) AS resposta;

// pergunta: direct_answers.produtos_do_pedido_1001
// Quais produtos, e em que quantidade, estao no pedido 1001? Devolve pares [sku, qt_itens]; o teste compara como dicionario.
MATCH (:Pedido {id_pedido: '1001'})-[:contem]->(i:ItemPedido)-[:referencia]->(s:Produto)
WITH s.sku AS sku, i.qt_itens AS qt ORDER BY sku
RETURN collect([sku, qt]) AS resposta;

// pergunta: direct_answers.todo_pedido_tem_um_cliente
// Todo pedido pertence a exatamente um cliente?
MATCH (p:Pedido)
OPTIONAL MATCH (p)-[r:pertenceA]->(:Cliente)
WITH p, count(r) AS n
RETURN count(CASE WHEN n <> 1 THEN 1 END) = 0 AS resposta;

// pergunta: measures.faturamento
// Faturamento: soma de vl_total dos pedidos com status FATURADO, uma vez por pedido, em centavos.
MATCH (p:Pedido {status: 'FATURADO'})
RETURN sum(toInteger(round(p.vl_total * 100))) AS resposta;

// pergunta: measures.qt_itens
// Quantidade total de itens vendidos: soma de qt_itens (INTEGER) em todos os itens.
MATCH (i:ItemPedido)
RETURN sum(i.qt_itens) AS resposta;

// pergunta: measures.vl_total_sem_filtro
// Soma de vl_total de todos os pedidos, sem filtro de status, em centavos.
MATCH (p:Pedido)
RETURN sum(toInteger(round(p.vl_total * 100))) AS resposta;

// pergunta: traps.fanout_faturamento_apos_itens
// Armadilha de fan-out, reproduzida de proposito: somar vl_total depois de descer para os itens conta o pedido uma vez por item.
MATCH (p:Pedido {status: 'FATURADO'})-[:contem]->(:ItemPedido)
RETURN sum(toInteger(round(p.vl_total * 100))) AS resposta;

// pergunta: keys_unique.Cliente(id_cliente)
// id_cliente identifica um cliente so?
MATCH (c:Cliente)
RETURN count(c) = count(DISTINCT c.id_cliente) AS resposta;

// pergunta: keys_unique.ItemPedido(id_pedido, sku)
// O par (id_pedido, sku) identifica um item so?
MATCH (i:ItemPedido)
RETURN count(i) = count(DISTINCT [i.id_pedido, i.sku]) AS resposta;

// pergunta: keys_unique.Pedido(id_pedido)
// id_pedido identifica um pedido so?
MATCH (p:Pedido)
RETURN count(p) = count(DISTINCT p.id_pedido) AS resposta;

// pergunta: keys_unique.Produto(sku)
// sku identifica um produto so?
MATCH (s:Produto)
RETURN count(s) = count(DISTINCT s.sku) AS resposta;
