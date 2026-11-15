"""
Script de Carga e Inicialização do Banco MongoDB Atlas — Equipe SMartCArt.
Conecta ao cluster na nuvem, cria as coleções 'produtos' e 'pedidos',
configura os índices de performance e insere o catálogo inicial.
"""

from urllib.parse import quote_plus
from pymongo import ASCENDING, DESCENDING, TEXT, MongoClient
from pymongo.errors import PyMongoError

# =============================================================================
# CONFIGURAÇÕES DE ACESSO AO MONGODB ATLAS
# =============================================================================
USUARIO = "jhonas123br_db_user"
SENHA = ""  # Cole sua senha entre as aspas OU deixe vazio para digitar no terminal
CLUSTER = "cluster0.s3g9nht.mongodb.net"
NOME_BANCO = "smartcart_db"


def obter_uri_conexao() -> str:
    """Monta a URI do MongoDB Atlas codificando caracteres especiais da senha."""
    senha_atual = SENHA.strip()
    if not senha_atual:
        senha_atual = input(
            f"Digite a senha do MongoDB Atlas para '{USUARIO}': "
        ).strip()

    usuario_codificado = quote_plus(USUARIO)
    senha_codificada = quote_plus(senha_atual)

    return (
        f"mongodb+srv://{usuario_codificado}:{senha_codificada}"
        f"@{CLUSTER}/?retryWrites=true&w=majority"
    )


def inicializar_mongodb_atlas() -> None:
    """Conecta ao cluster, cria os índices e popula os dados iniciais."""
    uri = obter_uri_conexao()
    print("\n[1/5] Conectando ao MongoDB Atlas...")

    try:
        # Abre a conexão com o cluster na nuvem
        client = MongoClient(uri)
        db = client[NOME_BANCO]

        # Testa a autenticação e a conexão de rede
        client.admin.command("ping")
        print(f"[✓] Conectado com sucesso ao banco '{NOME_BANCO}'!")

        # Referência às coleções principais do E-Commerce
        col_produtos = db["produtos"]
        col_pedidos = db["pedidos"]

        # Limpeza preventiva para evitar duplicidade ao rodar novamente
        print("[2/5] Limpando dados antigos de 'produtos' e 'pedidos'...")
        col_produtos.delete_many({})
        col_pedidos.delete_many({})

        # Criação de índices para acelerar consultas no Streamlit
        print("[3/5] Criando índices de otimização...")

        # 1. Índice textual para busca na barra de pesquisa do catálogo
        col_produtos.create_index(
            [("nome", TEXT), ("marca", TEXT), ("categorias", TEXT)],
            name="idx_busca_textual_produtos",
            default_language="portuguese",
        )

        # 2. Índice composto para filtrar por categoria e ordenar por preço
        col_produtos.create_index(
            [("categorias", ASCENDING), ("preco", ASCENDING)],
            name="idx_categoria_preco",
        )

        # 3. Índice único para o código de cada pedido finalizado
        col_pedidos.create_index(
            [("codigo_pedido", ASCENDING)],
            unique=True,
            name="idx_codigo_pedido_unico",
        )

        # 4. Índice para listar o histórico de compras de um cliente por data
        col_pedidos.create_index(
            [("cliente_id", ASCENDING), ("data_criacao", DESCENDING)],
            name="idx_cliente_historico_pedidos",
        )
        print("[✓] Índices criados com sucesso!")

        # Carga inicial de produtos com esquemas flexíveis (especificações variadas)
        print("[4/5] Inserindo produtos no catálogo...")
        produtos_iniciais = [
            {
                "_id": "PROD001",
                "nome": "Mouse Gamer Sem Fio RGB",
                "marca": "Logitech",
                "categorias": ["Periféricos", "Informática", "Gamer"],
                "preco": 349.90,
                "estoque": 45,
                "imagens": [
                    "https://images.unsplash.com/photo-1615663245857-ac93bb7c39e7"
                ],
                "especificacoes": {
                    "dpi_maximo": 25600,
                    "sensor": "HERO 25K",
                    "peso_gramas": 63,
                    "conexao": "Wireless 2.4GHz",
                },
                "ativo": True,
            },
            {
                "_id": "PROD002",
                "nome": "Teclado Mecânico RGB Switch Blue",
                "marca": "Redragon",
                "categorias": ["Periféricos", "Informática"],
                "preco": 289.00,
                "estoque": 30,
                "imagens": [
                    "https://images.unsplash.com/photo-1587829741301-dc798b83add3"
                ],
                "especificacoes": {
                    "layout": "ABNT2",
                    "switch": "Outemu Blue",
                    "retroiluminacao": "RGB",
                },
                "ativo": True,
            },
            {
                "_id": "PROD003",
                "nome": "Monitor IPS 27 Full HD 165Hz",
                "marca": "LG",
                "categorias": ["Monitores", "Informática", "Gamer"],
                "preco": 1199.00,
                "estoque": 12,
                "imagens": [
                    "https://images.unsplash.com/photo-1527443224154-c4a3942d3acf"
                ],
                "especificacoes": {
                    "tamanho_tela": "27 polegadas",
                    "taxa_atualizacao": "165Hz",
                    "painel": "IPS",
                    "tempo_resposta": "1ms",
                },
                "ativo": True,
            },
            {
                "_id": "PROD004",
                "nome": "SSD M.2 NVMe 1TB PCIe 4.0",
                "marca": "Kingston",
                "categorias": ["Hardware", "Armazenamento"],
                "preco": 429.90,
                "estoque": 80,
                "imagens": [
                    "https://images.unsplash.com/photo-1597872200969-2b65d56bd16b"
                ],
                "especificacoes": {
                    "leitura_sequencial": "3500 MB/s",
                    "escrita_sequencial": "2100 MB/s",
                    "formato": "M.2 2280",
                },
                "ativo": True,
            },
        ]

        resultado = col_produtos.insert_many(produtos_iniciais)
        print(f"[✓] {len(resultado.inserted_ids)} produtos inseridos no catálogo!")
        print(f"\n[5/5] BANCO '{NOME_BANCO}' PRONTO E CONFIGURADO NO ATLAS!")

        client.close()

    except PyMongoError as err:
        print(f"\n[ERRO] Falha ao configurar o banco no Atlas: {err}")


if __name__ == "__main__":
    inicializar_mongodb_atlas()