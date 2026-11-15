"""
Script de Carga Inicial e Constraints do Neo4j AuraDB — Equipe Smart Cart.
Sincroniza os produtos do MongoDB Atlas com o grafo e cria perfis de clientes
com relacionamentos [:COMPROU] e [:AVALIOU] para recomendação cruzada.
"""

from mongo_service import MongoService
from neo4j_service import Neo4jService


def popular_grafo():
    print("1. Conectando ao MongoDB Atlas e ao Neo4j AuraDB...")
    mongo = MongoService()
    grafo = Neo4jService()

    print("2. Criando constraints e índices no Neo4j...")
    grafo.criar_constraints()

    print("3. Sincronizando produtos e categorias do MongoDB para o Neo4j...")
    produtos = mongo.listar_produtos()
    if not produtos:
        print("Nenhum produto encontrado no MongoDB. Rode populador_atlas.py primeiro.")
        return

    for prod in produtos:
        grafo.sincronizar_produto(prod)
        print(f"   -> Produto sincronizado: {prod['nome']}")

    # Mapeia os produtos por palavra-chave para criar histórico realista
    by_name = {p["nome"]: p for p in produtos}
    mouse = next((p for n, p in by_name.items() if "Mouse" in n), produtos[0])
    teclado = next((p for n, p in by_name.items() if "Teclado" in n), produtos[-1])
    monitor = next((p for n, p in by_name.items() if "Monitor" in n), produtos[0])
    ssd = next((p for n, p in by_name.items() if "SSD" in n), produtos[-1])

    print("4. Criando clientes simulados com [:COMPROU] e [:AVALIOU]...")
    perfis_simulados = [
        {
            "id": "cli_ana_silva",
            "nome": "Ana Silva",
            "compras": [mouse, teclado, monitor],
            "avaliacoes": [(mouse, 5), (teclado, 5), (monitor, 4)],
        },
        {
            "id": "cli_carlos_souza",
            "nome": "Carlos Souza",
            "compras": [teclado, ssd],
            "avaliacoes": [(teclado, 5), (ssd, 5)],
        },
        {
            "id": "cli_mariana_costa",
            "nome": "Mariana Costa",
            "compras": [mouse, monitor, ssd],
            "avaliacoes": [(mouse, 4), (monitor, 5), (ssd, 4)],
        },
    ]

    for perfil in perfis_simulados:
        grafo.registrar_compra(perfil["id"], perfil["nome"], perfil["compras"])
        for prod_item, nota in perfil["avaliacoes"]:
            grafo.registrar_avaliacao(
                perfil["id"], perfil["nome"], str(prod_item["_id"]), nota
            )
        print(f"   -> Perfil criado: {perfil['nome']}")

    mongo.fechar_conexao()
    grafo.close()
    print("\nCarga inicial do Neo4j AuraDB concluída com sucesso!")


if __name__ == "__main__":
    popular_grafo()