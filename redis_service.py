"""
Módulo de Integração com o Redis — Equipe SMartCArt.
Fornece a classe RedisService para cache de catálogo com TTL (Cache Invalidation),
ranking de produtos mais acessados, carrinho de compras dinâmico (Hash)
e controle de tokens de sessão ativa.
"""

import json
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple
import redis
from redis.exceptions import RedisError
from mongo_service import MongoService


class RedisService:
    """Gerencia as operações em memória (Chave-Valor) no Redis."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        password: Optional[str] = None,
    ) -> None:
        """Inicializa o cliente Redis e valida a conexão com PING."""
        self.host = host or os.getenv("REDIS_HOST", "localhost")
        self.port = port or int(os.getenv("REDIS_PORT", 6379))
        self.password = password or os.getenv("REDIS_PASSWORD") or None

        try:
            self.client = redis.Redis(
                host=self.host,
                port=self.port,
                password=self.password,
                decode_responses=True,
            )
            self.client.ping()
        except RedisError as err:
            print(f"[Redis Error] Não foi possível conectar ao Redis: {err}")
            raise

    # =========================================================================
    # CONTROLE DE TOKENS DE LOGIN / SESSÃO ATIVA (TTL)
    # =========================================================================

    def criar_sessao(
        self,
        cliente_id: str,
        cliente_nome: str,
        ttl_segundos: int = 3600,
    ) -> Optional[str]:
        """Gera um token de sessão e armazena no Redis com expiração (TTL)."""
        token = str(uuid.uuid4())
        payload = json.dumps(
            {"cliente_id": cliente_id, "cliente_nome": cliente_nome}
        )
        try:
            self.client.setex(f"sessao:{token}", ttl_segundos, payload)
            return token
        except RedisError as err:
            print(f"[Redis Error] Erro ao criar sessão: {err}")
            return None

    def validar_sessao(self, token: str) -> Optional[Dict[str, str]]:
        """Verifica se o token existe e ainda não expirou no Redis."""
        try:
            dados = self.client.get(f"sessao:{token}")
            return json.loads(dados) if dados else None
        except RedisError as err:
            print(f"[Redis Error] Erro ao validar sessão: {err}")
            return None

    def encerrar_sessao(self, token: str) -> bool:
        """Remove o token de sessão (Logout)."""
        try:
            return self.client.delete(f"sessao:{token}") > 0
        except RedisError as err:
            print(f"[Redis Error] Erro ao encerrar sessão: {err}")
            return False

    # =========================================================================
    # TELA 1: CACHE DE CATÁLOGO (TTL) E RANKING DE MAIS ACESSADOS
    # =========================================================================

    def listar_produtos_com_cache(
        self,
        mongo_service: MongoService,
        categoria: Optional[str] = None,
        termo_busca: Optional[str] = None,
        apenas_em_estoque: bool = False,
        ttl_segundos: int = 300,
    ) -> Tuple[List[Dict[str, Any]], str]:
        """
        Consulta o catálogo no Redis primeiro (Cache Hit).
        Em caso de Cache Miss, busca no MongoService e salva no Redis com TTL.
        """
        cat_key = categoria or "Todas"
        busca_key = (termo_busca or "").strip().lower()
        chave_cache = f"cache:catalogo:{cat_key}:{busca_key}:{apenas_em_estoque}"

        try:
            dados_cache = self.client.get(chave_cache)
            if dados_cache:
                return json.loads(dados_cache), "REDIS (Cache Hit)"
        except RedisError as err:
            print(f"[Redis Warning] Falha ao ler cache, buscando no MongoDB: {err}")

        # Cache Miss -> consulta o MongoDB Atlas usando o serviço do grupo
        produtos = mongo_service.listar_produtos(
            categoria=categoria,
            termo_busca=termo_busca,
            apenas_em_estoque=apenas_em_estoque,
        )

        try:
            self.client.setex(
                chave_cache,
                ttl_segundos,
                json.dumps(produtos, default=str),
            )
        except RedisError as err:
            print(f"[Redis Warning] Não foi possível gravar cache: {err}")

        return produtos, "MONGODB ATLAS (Cache Miss -> Armazenado no Redis)"

    def invalidar_cache_catalogo(self) -> int:
        """Remove todas as chaves de cache do catálogo (Cache Invalidation)."""
        try:
            chaves = self.client.keys("cache:catalogo:*")
            if chaves:
                return self.client.delete(*chaves)
            return 0
        except RedisError as err:
            print(f"[Redis Error] Erro ao invalidar cache: {err}")
            return 0

    def registrar_acesso_produto(self, produto_id: str, nome_produto: str) -> None:
        """Incrementa o contador de acessos do produto usando Sorted Set."""
        try:
            membro = f"{produto_id}|{nome_produto}"
            self.client.zincrby("ranking:produtos_mais_acessados", 1, membro)
        except RedisError as err:
            print(f"[Redis Error] Erro ao registrar acesso ao produto: {err}")

    def obter_mais_acessados(self, limite: int = 5) -> List[Dict[str, Any]]:
        """Retorna os produtos mais acessados ordenados do maior para o menor."""
        try:
            ranking = self.client.zrevrange(
                "ranking:produtos_mais_acessados", 0, limite - 1, withscores=True
            )
            resultado = []
            for membro, score in ranking:
                prod_id, nome = membro.split("|", 1)
                resultado.append(
                    {"produto_id": prod_id, "nome": nome, "acessos": int(score)}
                )
            return resultado
        except RedisError as err:
            print(f"[Redis Error] Erro ao buscar ranking: {err}")
            return []

    # =========================================================================
    # TELA 2: CARRINHO DE COMPRAS DINÂMICO DA SESSÃO (REDIS HASH)
    # =========================================================================

    def _chave_carrinho(self, cliente_id: str) -> str:
        return f"carrinho:{cliente_id}"

    def adicionar_item_carrinho(
        self,
        cliente_id: str,
        produto: Dict[str, Any],
        quantidade: int = 1,
    ) -> bool:
        """Adiciona ou incrementa um produto no Hash do carrinho do cliente."""
        chave = self._chave_carrinho(cliente_id)
        produto_id = str(produto["_id"])

        try:
            item_existente = self.client.hget(chave, produto_id)
            if item_existente:
                item = json.loads(item_existente)
                item["quantidade"] += int(quantidade)
            else:
                item = {
                    "produto_id": produto_id,
                    "nome": produto.get("nome", "Produto"),
                    "marca": produto.get("marca", ""),
                    "preco": float(produto.get("preco", 0.0)),
                    "quantidade": int(quantidade),
                }

            self.client.hset(chave, produto_id, json.dumps(item))
            self.client.expire(chave, 86400)  # Expira carrinho abandonado em 24h
            return True
        except RedisError as err:
            print(f"[Redis Error] Erro ao adicionar item ao carrinho: {err}")
            return False

    def atualizar_quantidade_carrinho(
        self,
        cliente_id: str,
        produto_id: str,
        nova_quantidade: int,
    ) -> bool:
        """Altera a quantidade de um item no carrinho (ou remove se <= 0)."""
        if nova_quantidade <= 0:
            return self.remover_item_carrinho(cliente_id, produto_id)

        chave = self._chave_carrinho(cliente_id)
        try:
            item_raw = self.client.hget(chave, produto_id)
            if not item_raw:
                return False
            item = json.loads(item_raw)
            item["quantidade"] = int(nova_quantidade)
            self.client.hset(chave, produto_id, json.dumps(item))
            return True
        except RedisError as err:
            print(f"[Redis Error] Erro ao atualizar quantidade: {err}")
            return False

    def remover_item_carrinho(self, cliente_id: str, produto_id: str) -> bool:
        """Remove um produto específico do carrinho ativo."""
        try:
            return self.client.hdel(self._chave_carrinho(cliente_id), produto_id) > 0
        except RedisError as err:
            print(f"[Redis Error] Erro ao remover item do carrinho: {err}")
            return False

    def obter_carrinho(self, cliente_id: str) -> List[Dict[str, Any]]:
        """Retorna todos os itens atuais do carrinho do cliente."""
        try:
            itens_hash = self.client.hgetall(self._chave_carrinho(cliente_id))
            return [json.loads(valor) for valor in itens_hash.values()]
        except RedisError as err:
            print(f"[Redis Error] Erro ao ler carrinho: {err}")
            return []

    def calcular_total_carrinho(self, cliente_id: str) -> float:
        """Calcula o valor total dos itens no carrinho."""
        itens = self.obter_carrinho(cliente_id)
        return round(sum(i["preco"] * i["quantidade"] for i in itens), 2)

    def limpar_carrinho(self, cliente_id: str) -> bool:
        """Apaga a chave do carrinho no Redis (usado após o checkout)."""
        try:
            return self.client.delete(self._chave_carrinho(cliente_id)) > 0
        except RedisError as err:
            print(f"[Redis Error] Erro ao limpar carrinho: {err}")
            return False

    # =========================================================================
    # TELA 4: CHECKOUT INTEGRADO (REDIS -> MONGODB ATLAS)
    # =========================================================================

    def finalizar_checkout(
        self,
        cliente_id: str,
        cliente_nome: str,
        mongo_service: MongoService,
        forma_pagamento: str = "PIX",
    ) -> Optional[str]:
        """
        Persiste o pedido no MongoDB via MongoService, limpa o carrinho no Redis
        e invalida o cache do catálogo para refletir a baixa de estoque.
        """
        itens = self.obter_carrinho(cliente_id)
        if not itens:
            return None

        valor_total = self.calcular_total_carrinho(cliente_id)
        codigo_pedido = mongo_service.salvar_pedido(
            cliente_id=cliente_id,
            cliente_nome=cliente_nome,
            itens_carrinho=itens,
            valor_total=valor_total,
            forma_pagamento=forma_pagamento,
        )

        if codigo_pedido:
            self.limpar_carrinho(cliente_id)
            self.invalidar_cache_catalogo()

        return codigo_pedido

    def fechar_conexao(self) -> None:
        """Encerra o pool de conexões com o Redis."""
        if self.client:
            self.client.close()