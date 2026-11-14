// Perguntas de competencia do Olist (CQ-006, CQ-007 e CQ-008 de validation/questions.yml) respondidas no grafo do
// Neo4j carregado pelo akme. Os dados e a ontologia do Olist nao estao no repositorio: estas consultas valem para o
// grafo do registro de execucao em docs/exportacao-neo4j/task-9-aceitacao.md (Olist completo, com as tres correcoes
// descritas la). Nenhum valor de linha aparece aqui: o pedido da CQ-008 entra pelo parametro $pedido.
//
// Cada bloco comeca com "// pergunta: <id>". As consultas aplicam as regras da ontologia do Olist:
//   C-001: uma avaliacao por pedido, a de review_answer_timestamp mais recente (texto ISO, ordena como data);
//   C-002: cada pedido conta uma vez por categoria ou por vendedor, nunca uma vez por item;
//   C-003: atraso so para pedido delivered com data de entrega.
// O corte de 30 ou mais pedidos avaliados (CQ-006 e CQ-007) nao esta no texto da pergunta: vem da justificativa
// registrada no changelog do Olist quando as respostas foram reservadas.
//
// No Neo4j Browser, antes da CQ-008:  :param pedido => '<order_id da pergunta>'
// No cypher-shell:                    :param pedido => '<order_id da pergunta>'

// pergunta: CQ-006
// Nota media por categoria de produto; as tres piores entre as categorias com 30 ou mais pedidos avaliados.
// Produto sem aresta pertenceACategoria usa a propriedade do produto; sem ela, 'sem categoria'.
MATCH (a:Avaliacao)-[:refereSeAoPedido]->(p:Pedido)
WITH p, a ORDER BY a.review_answer_timestamp DESC, a.review_id DESC
WITH p, head(collect(a)) AS a
MATCH (p)-[:contemItem]->(:ItemPedido)-[:referenteAoProduto]->(pr:Produto)
OPTIONAL MATCH (pr)-[:pertenceACategoria]->(c:CategoriaProduto)
WITH DISTINCT coalesce(c.product_category_name, pr.product_category_name, 'sem categoria') AS categoria, p, a
WITH categoria, avg(toFloat(a.review_score)) AS media, count(*) AS pedidos
WHERE pedidos >= 30
RETURN categoria, round(media, 2) AS media, pedidos ORDER BY media ASC, categoria LIMIT 3;

// pergunta: CQ-007
// Nota media e numero de pedidos avaliados por vendedor; o pior entre os vendedores com 30 ou mais pedidos avaliados.
MATCH (a:Avaliacao)-[:refereSeAoPedido]->(p:Pedido)
WITH p, a ORDER BY a.review_answer_timestamp DESC, a.review_id DESC
WITH p, head(collect(a)) AS a
MATCH (p)-[:contemItem]->(:ItemPedido)-[:vendidoPor]->(v:Vendedor)
WITH DISTINCT v, p, a
WITH v.seller_id AS vendedor, avg(toFloat(a.review_score)) AS media, count(*) AS pedidos
WHERE pedidos >= 30
RETURN vendedor, round(media, 2) AS media, pedidos ORDER BY media ASC, vendedor LIMIT 1;

// pergunta: CQ-008
// O pedido $pedido foi entregue com atraso, e de quantos dias? As datas ficaram texto na etapa 5 (para nao perder a
// hora); o atraso e por dia, comparando as datas sem a hora.
MATCH (p:Pedido {order_id: $pedido})
WITH p, date(left(p.order_delivered_customer_date, 10)) AS entregue,
        date(left(p.order_estimated_delivery_date, 10)) AS estimado
RETURN p.order_status AS status, entregue, estimado,
       CASE WHEN p.order_status = 'delivered' AND p.order_delivered_customer_date IS NOT NULL
            THEN duration.inDays(estimado, entregue).days END AS atraso_dias;
