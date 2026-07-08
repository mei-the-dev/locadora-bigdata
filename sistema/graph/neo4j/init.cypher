// ============================================================================
// Neo4j - grafo de patios/rotas para roteirizacao do veiculo VAZIO (R13).
// Nos = patios (com coordenadas geograficas); arestas ROTA ponderadas por
// distancia (great-circle via point.distance). Complementa a matriz de Markov:
// Markov diz PARA ONDE ir (probabilidade de demanda); o grafo diz COMO chegar
// (caminho minimo). Ementa III (Neo4j/GraphX; raciocinio do agente).
// Aplicar: cypher-shell -f /init.cypher (Neo4j nao roda initdb automaticamente).
// ============================================================================

// --- Patios (6 canonicos; coerentes com fleetlib.domain) --------------------
UNWIND [
  {id:'PAT-GAL', nome:'Galeao',        emp:'AutoRio Locadora', lat:-22.809, lon:-43.250},
  {id:'PAT-SDU', nome:'Santos Dumont', emp:'MoveFrota',        lat:-22.910, lon:-43.163},
  {id:'PAT-BAR', nome:'Barra',         emp:'VelozCar',         lat:-23.000, lon:-43.365},
  {id:'PAT-COP', nome:'Copacabana',    emp:'AutoRio Locadora', lat:-22.971, lon:-43.182},
  {id:'PAT-CEN', nome:'Centro',        emp:'UnidasFrota',      lat:-22.906, lon:-43.185},
  {id:'PAT-NIT', nome:'Niteroi',       emp:'MoveFrota',        lat:-22.895, lon:-43.123}
] AS p
MERGE (n:Patio {id: p.id})
SET n.nome = p.nome,
    n.empresa_dona = p.emp,
    n.location = point({latitude: p.lat, longitude: p.lon, crs:'WGS-84'});

// --- Arestas ROTA entre todos os pares, peso = distancia (km) ---------------
MATCH (a:Patio), (b:Patio)
WHERE a.id < b.id
MERGE (a)-[r1:ROTA]->(b)
MERGE (b)-[r2:ROTA]->(a)
WITH a, b, r1, r2, round(point.distance(a.location, b.location) / 1000.0, 2) AS d
SET r1.distancia_km = d, r2.distancia_km = d;

// --- Exemplo: caminho de reposicionamento mais curto (Galeao -> Barra) ------
// MATCH (o:Patio {nome:'Galeao'}), (d:Patio {nome:'Barra'}),
//       p = shortestPath((o)-[:ROTA*..4]-(d))
// RETURN [n IN nodes(p) | n.nome] AS rota,
//        reduce(s=0.0, r IN relationships(p) | s + r.distancia_km) AS km_total;

// --- Exemplo: patios vizinhos ordenados por distancia (a partir de Centro) --
// MATCH (o:Patio {nome:'Centro'})-[r:ROTA]->(d:Patio)
// RETURN d.nome AS destino, r.distancia_km AS km ORDER BY km ASC;
