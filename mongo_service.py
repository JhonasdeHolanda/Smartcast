"""
Módulo de Integração com o MongoDB Atlas — Equipe SMartCArt.
Fornece a classe MongoService para consulta de catálogo, controle atômico
de estoque e persistência de pedidos finalizados no checkout.
"""

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import quote_plus
from pymongo import DESCENDING, MongoClient
from pymongo.errors import ConnectionFailure, PyMongoError

# =============================================================================
# CREDENCIAIS PADRÃO DO CLUSTER ATLAS (SMartCArt)
# =============================================================================
USUARIO_PADRAO = "jhonas123br_db_user"
SENHA_PADRAO = "SmartCart2026"
CLUSTER_PADRAO = "cluster0.s3g9nht.mongodb.net"


class MongoService:
    """Gerencia todas as operações de leitura e escrita no MongoDB Atlas."""

    def __init__(
        self,
        uri: Optional[str] = None,
        db_name: str = "smartcart_db",
    ) -> None:
        """
        Inicializa o cliente PyMongo conectado ao banco 'smartcart_db'.
        Aceita uma URI explícita, a variável de ambiente MONGO_URI ou monta
        automaticamente usando as credenciais padrão acima.
        """
        if uri:
            self.uri = uri
        elif os.getenv("MONGO_URI"):
            self.uri = os.environ["MONGO_URI"]
        else:
            user_enc = quote_plus(USUARIO_PADRAO)
            pass_enc = quote_plus(SENHA_PADRAO)
            self.uri = (
                f"mongodb+srv://{user_enc}:{pass_enc}"
                f"@{CLUSTER_PADRAO}/?retryWrites=true&w=majority"
            )

        self.db_name = db_name

        try:
            self.client: MongoClient = MongoClient(self.uri)
            self.db = self.client[self.db_name]
            self.produtos = self.db["produtos"]
            self.pedidos = self.db["pedidos"]

            # Valida a conexão no momento da inicialização
            self.client.admin.command("ping")
        except ConnectionFailure as err:
            print(f"[MongoDB Error] Não foi possível conectar ao Atlas: {err}")
            raise

    # =========================================================================
    # TELA 1: CATÁLOGO E BUSCA DE PRODUTOS
    # =========================================================================

    def listar_produtos(
        self,
        categoria: Optional[str] = None,
        termo_busca: Optional[str] = None,
        apenas_em_estoque: bool = False,
    ) -> List[Dict[str, Any]]:
        """Retorna os produtos ativos aplicando filtros opcionais."""
        query: Dict[str, Any] = {"ativo": True}

        if apenas_em_estoque:
            query["estoque"] = {"$gt": 0}

        if categoria and categoria != "Todas":
            query["categorias"] = categoria

        if termo_busca and termo_busca.strip():
            query["$text"] = {"$search": termo_busca.strip()}

        try:
            return list(self.produtos.find(query))
        except PyMongoError as err:
            print(f"[MongoDB Error] Erro ao listar produtos: {err}")
            return []

    def buscar_produto_por_id(self, produto_id: str) -> Optional[Dict[str, Any]]:
        """Busca um único produto pelo seu identificador (_id)."""
        try:
            return self.produtos.find_one({"_id": produto_id, "ativo": True})
        except PyMongoError as err:
            print(f"[MongoDB Error] Erro ao buscar produto '{produto_id}': {err}")
            return None

    def cadastrar_produto(self, produto_doc: Dict[str, Any]) -> bool:
        """Insere um novo documento de produto no catálogo."""
        try:
            produto_doc.setdefault("ativo", True)
            self.produtos.insert_one(produto_doc)
            return True
        except PyMongoError as err:
            print(f"[MongoDB Error] Erro ao cadastrar produto: {err}")
            return False

    def atualizar_estoque(self, produto_id: str, quantidade_vendida: int) -> bool:
        """Subtrai atomicamente a quantidade vendida usando o operador $inc."""
        try:
            resultado = self.produtos.update_one(
                {"_id": produto_id, "estoque": {"$gte": quantidade_vendida}},
                {"$inc": {"estoque": -quantidade_vendida}},
            )
            return resultado.modified_count > 0
        except PyMongoError as err:
            print(f"[MongoDB Error] Erro ao atualizar estoque de '{produto_id}': {err}")
            return False

    # =========================================================================
    # TELA 4: CHECKOUT E HISTÓRICO DE PEDIDOS
    # =========================================================================

    def salvar_pedido(
        self,
        cliente_id: str,
        cliente_nome: str,
        itens_carrinho: List[Dict[str, Any]],
        valor_total: float,
        forma_pagamento: str = "PIX",
    ) -> Optional[str]:
        """Grava o pedido finalizado na coleção 'pedidos' e baixa o estoque."""
        timestamp_atual = int(datetime.now(timezone.utc).timestamp())
        codigo_pedido = f"PED-{timestamp_atual}"

        pedido_doc = {
            "codigo_pedido": codigo_pedido,
            "cliente_id": cliente_id,
            "cliente_nome": cliente_nome,
            "itens": itens_carrinho,
            "valor_total": float(valor_total),
            "status": "FINALIZADO",
            "forma_pagamento": forma_pagamento,
            "data_criacao": datetime.now(timezone.utc),
        }

        try:
            self.pedidos.insert_one(pedido_doc)

            for item in itens_carrinho:
                p_id = item.get("produto_id") or item.get("_id")
                qtd = item.get("quantidade", 1)
                if p_id:
                    self.atualizar_estoque(str(p_id), int(qtd))

            return codigo_pedido
        except PyMongoError as err:
            print(f"[MongoDB Error] Falha ao salvar pedido: {err}")
            return None

    def listar_historico_pedidos(self, cliente_id: str) -> List[Dict[str, Any]]:
        """Retorna os pedidos de um cliente do mais recente para o mais antigo."""
        try:
            cursor = self.pedidos.find({"cliente_id": cliente_id}).sort(
                "data_criacao", DESCENDING
            )
            return list(cursor)
        except PyMongoError as err:
            print(f"[MongoDB Error] Erro ao buscar histórico de '{cliente_id}': {err}")
            return []

    def fechar_conexao(self) -> None:
        """Encerra a conexão com o MongoDB Atlas."""
        if self.client:
            self.client.close()