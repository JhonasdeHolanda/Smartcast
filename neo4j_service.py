"""
Módulo de Integração com o Neo4j AuraDB — Equipe Smart Cart.
Modela os nós (:Cliente), (:Produto) e (:Categoria) com os relacionamentos
[:COMPROU], [:AVALIOU] e [:PERTENCE_A] para recomendação cruzada em Cypher.
"""

import os
from typing import Any, Dict, List, Optional
from neo4j import GraphDatabase
from neo4j.exceptions import AuthError, Neo4jError

# =============================================================================
# CREDENCIAIS PADRÃO DO NEO4J AURADB (Smart Cart)
# =============================================================================
NEO4J_URI_PADRAO = "neo4j+s://3e8c7878.databases.neo4j.io"
NEO4J_USER_PADRAO = "3e8c7878"
NEO4J_PASS_PADRAO = "n5vOlAF6MAk1BNBYoafhwPByUo0QRO8n8dtED-eomqs"
NEO4J_DB_PADRAO = "3e8c7878"


class Neo4jService:
    """Gerencia a conexão e as consultas em grafo (Cypher) no Neo4j AuraDB."""

    def __init__(
        self,
        uri: Optional[str] = None,
        user: Optional[str] = None,
        password: Optional[str] = None,
        database: Optional[str] = None,
    ) -> None:
        self.uri = uri or os.getenv("NEO4J_URI", NEO4J_URI_PADRAO)
        self.user = user or os.getenv("NEO4J_USERNAME", NEO4J_USER_PADRAO)
        self.password = password or os.getenv("NEO4J_PASSWORD", NEO4J_PASS_PADRAO)
        self.database = database or os.getenv("NEO4J_DATABASE", NEO4J_DB_PADRAO)

        try:
            self.driver = GraphDatabase.driver(
                self.uri, auth=(self.user, self.password)
            )
            self.driver.verify_connectivity()
        except AuthError:
            # Fallback caso a instância AuraDB utilize o usuário padrão 'neo4j'
            self.user = "neo4j"
            self.driver = GraphDatabase.driver(
                self.uri, auth=(self.user, self.password)
            )
            self.driver.verify_connectivity()
        except Neo4jError as err:
            print(f"[Neo4j Error] Falha ao conectar ao AuraDB: {err}")
            raise

    def close(self) -> None:
        """Encerra o driver do Neo4j."""
        if self.driver:
            self.driver.close()

    # =========================================================================
    # SCHEMA, CONSTRAINTS E SINCRONIZAÇÃO DE NÓS
    # =========================================================================

    def criar_constraints(self) -> None:
        """Cria restrições de unicidade e índices para otimizar buscas no grafo."""
        comandos = [
            "CREATE CONSTRAINT cliente_id_unique IF NOT EXISTS FOR (c:Cliente) REQUIRE c.cliente_id IS UNIQUE",
            "CREATE CONSTRAINT produto_id_unique IF NOT EXISTS FOR (p:Produto) REQUIRE p.produto_id IS UNIQUE",
            "CREATE CONSTRAINT categoria_nome_unique IF NOT EXISTS FOR (cat:Categoria) REQUIRE cat.nome IS UNIQUE",
        ]
        with self.driver.session(database=self.database) as session:
            for cypher in comandos:
                session.run(cypher)

    def sincronizar_produto(self, produto: Dict[str, Any]) -> None:
        """Cria ou atualiza um nó (:Produto) e seus vínculos (:Categoria)."""
        query = """
        MERGE (p:Produto {produto_id: $produto_id})
        SET p.nome = $nome,
            p.marca = $marca,
            p.preco = $preco
        WITH p
        UNWIND $categorias AS cat_nome
        MERGE (cat:Categoria {nome: cat_nome})
        MERGE (p)-[:PERTENCE_A]->(cat)
        """
        with self.driver.session(database=self.database) as session:
            session.run(
                query,
                produto_id=str(produto["_id"]),
                nome=produto.get("nome", "Produto"),
                marca=produto.get("marca", ""),
                preco=float(produto.get("preco", 0.0)),
                categorias=produto.get("categorias", ["Geral"]),
            )

    def garantir_cliente(self, cliente_id: str, cliente_nome: str) -> None:
        """Garante que o nó (:Cliente) exista no grafo."""
        query = """
        MERGE (c:Cliente {cliente_id: $cliente_id})
        SET c.nome = $cliente_nome
        """
        with self.driver.session(database=self.database) as session:
            session.run(query, cliente_id=cliente_id, cliente_nome=cliente_nome)

    # =========================================================================
    # RELACIONAMENTOS [:COMPROU] E [:AVALIOU]
    # =========================================================================

    def registrar_compra(
        self,
        cliente_id: str,
        cliente_nome: str,
        itens_carrinho: List[Dict[str, Any]],
    ) -> None:
        """Cria ou incrementa o relacionamento [:COMPROU] após o checkout."""
        query = """
        MERGE (c:Cliente {cliente_id: $cliente_id})
        SET c.nome = $cliente_nome
        WITH c
        UNWIND $itens AS item
        MERGE (p:Produto {produto_id: item.produto_id})
        ON CREATE SET p.nome = item.nome, p.marca = item.marca, p.preco = item.preco
        MERGE (c)-[r:COMPROU]->(p)
        ON CREATE SET r.quantidade_total = item.quantidade, r.ultima_compra = datetime()
        ON MATCH SET r.quantidade_total = coalesce(r.quantidade_total, 0) + item.quantidade,
                     r.ultima_compra = datetime()
        """
        itens_formatados = [
            {
                "produto_id": str(i.get("produto_id") or i.get("_id")),
                "nome": i.get("nome", "Produto"),
                "marca": i.get("marca", ""),
                "preco": float(i.get("preco", 0.0)),
                "quantidade": int(i.get("quantidade", 1)),
            }
            for i in itens_carrinho
        ]
        with self.driver.session(database=self.database) as session:
            session.run(
                query,
                cliente_id=cliente_id,
                cliente_nome=cliente_nome,
                itens=itens_formatados,
            )

    def registrar_avaliacao(
        self,
        cliente_id: str,
        cliente_nome: str,
        produto_id: str,
        nota: int,
    ) -> None:
        """Cria ou atualiza o relacionamento [:AVALIOU {nota}] entre Cliente e Produto."""
        query = """
        MERGE (c:Cliente {cliente_id: $cliente_id})
        SET c.nome = $cliente_nome
        WITH c
        MATCH (p:Produto {produto_id: $produto_id})
        MERGE (c)-[r:AVALIOU]->(p)
        SET r.nota = $nota,
            r.data = datetime()
        """
        with self.driver.session(database=self.database) as session:
            session.run(
                query,
                cliente_id=cliente_id,
                cliente_nome=cliente_nome,
                produto_id=str(produto_id),
                nota=int(nota),
            )

    # =========================================================================
    # MOTOR DE RECOMENDAÇÃO CRUZADA (CYPHER / INDEX-FREE ADJACENCY)
    # =========================================================================

    def obter_recomendacoes_cruzadas(
        self, cliente_id: str, limite: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Filtragem Colaborativa no Grafo:
        Encontra outros clientes que compraram ou avaliaram bem (nota >= 4)
        os mesmos produtos que o cliente atual e recomenda outros itens
        adquiridos/bem avaliados por esses perfis similares.
        """
        query = """
        MATCH (c1:Cliente {cliente_id: $cliente_id})-[r1:COMPROU|AVALIOU]->(comum:Produto)
        WHERE type(r1) = 'COMPROU' OR r1.nota >= 4
        MATCH (c2:Cliente)-[r2:COMPROU|AVALIOU]->(comum)
        WHERE c1 <> c2 AND (type(r2) = 'COMPROU' OR r2.nota >= 4)
        MATCH (c2)-[r3:COMPROU|AVALIOU]->(rec:Produto)
        WHERE NOT (c1)-[:COMPROU]->(rec)
          AND (type(r3) = 'COMPROU' OR r3.nota >= 4)
        OPTIONAL MATCH (rec)-[:PERTENCE_A]->(cat:Categoria)
        RETURN rec.produto_id AS produto_id,
               rec.nome AS nome,
               rec.marca AS marca,
               rec.preco AS preco,
               collect(DISTINCT cat.nome) AS categorias,
               collect(DISTINCT c2.nome) AS clientes_similares,
               collect(DISTINCT comum.nome) AS produtos_em_comum,
               count(DISTINCT c2) AS relevancia
        ORDER BY relevancia DESC, rec.preco ASC
        LIMIT $limite
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(query, cliente_id=cliente_id, limite=limite)
            return [dict(record) for record in result]

    def obter_populares_no_grafo(
        self, cliente_id: str, limite: int = 4
    ) -> List[Dict[str, Any]]:
        """
        Retorna os produtos mais bem avaliados/comprados no grafo caso o cliente
        ainda seja novo e não possua histórico suficiente para filtragem cruzada.
        """
        query = """
        MATCH (p:Produto)
        OPTIONAL MATCH (c:Cliente)-[comp:COMPROU]->(p)
        OPTIONAL MATCH (c2:Cliente)-[av:AVALIOU]->(p)
        OPTIONAL MATCH (p)-[:PERTENCE_A]->(cat:Categoria)
        RETURN p.produto_id AS produto_id,
               p.nome AS nome,
               p.marca AS marca,
               p.preco AS preco,
               collect(DISTINCT cat.nome) AS categorias,
               count(DISTINCT comp) AS total_compras,
               round(avg(av.nota), 1) AS media_notas
        ORDER BY total_compras DESC, media_notas DESC
        LIMIT $limite
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(query, cliente_id=cliente_id, limite=limite)
            return [dict(record) for record in result]

    def obter_grafo_cliente(self, cliente_id: str) -> List[Dict[str, Any]]:
        """Retorna todas as conexões [:COMPROU] e [:AVALIOU] do cliente atual."""
        query = """
        MATCH (c:Cliente {cliente_id: $cliente_id})-[r:COMPROU|AVALIOU]->(p:Produto)
        OPTIONAL MATCH (p)-[:PERTENCE_A]->(cat:Categoria)
        RETURN type(r) AS relacao,
               p.nome AS produto,
               p.marca AS marca,
               r.quantidade_total AS quantidade,
               r.nota AS nota,
               collect(DISTINCT cat.nome) AS categorias
        ORDER BY relacao, produto
        """
        with self.driver.session(database=self.database) as session:
            result = session.run(query, cliente_id=cliente_id)
            return [dict(record) for record in result]