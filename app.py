import re
import streamlit as st
from mongo_service import MongoService
from redis_service import RedisService

st.set_page_config(
    page_title="Smart Cart | Loja de Tecnologia",
    page_icon="🛒",
    layout="wide",
)

# =============================================================================
# ESTILIZAÇÃO VISUAL (CSS CUSTOMIZADO)
# =============================================================================
st.markdown(
    """
    <style>
    .block-container {
        padding-top: 1.5rem;
        padding-bottom: 2rem;
    }
    .store-banner {
        background: linear-gradient(135deg, #0f172a 0%, #1e293b 60%, #0f766e 100%);
        padding: 1.5rem 2rem;
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.08);
        margin-bottom: 1.25rem;
    }
    .store-banner h1 {
        margin: 0;
        font-size: 2rem;
        font-weight: 800;
        color: #f8fafc;
        letter-spacing: -0.5px;
    }
    .store-banner p {
        margin: 0.35rem 0 0 0;
        color: #cbd5e1;
        font-size: 0.95rem;
    }
    .product-card {
        background-color: #111827;
        border: 1px solid #1f2937;
        border-radius: 14px;
        padding: 1.2rem;
        margin-bottom: 0.5rem;
        transition: border-color 0.2s ease;
    }
    .product-card:hover {
        border-color: #14b8a6;
    }
    .badge-brand {
        display: inline-block;
        background-color: rgba(20, 184, 166, 0.15);
        color: #2dd4bf;
        padding: 0.18rem 0.6rem;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 600;
        margin-right: 0.4rem;
    }
    .badge-cat {
        display: inline-block;
        background-color: rgba(148, 163, 184, 0.14);
        color: #cbd5e1;
        padding: 0.18rem 0.6rem;
        border-radius: 999px;
        font-size: 0.78rem;
        margin-right: 0.3rem;
    }
    .price-tag {
        font-size: 1.65rem;
        font-weight: 800;
        color: #f8fafc;
        margin: 0.65rem 0 0.2rem 0;
    }
    .stock-ok {
        color: #34d399;
        font-size: 0.83rem;
        font-weight: 500;
    }
    .stock-out {
        color: #f87171;
        font-size: 0.83rem;
        font-weight: 600;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def formatar_brl(valor: float) -> str:
    return f"R$ {float(valor):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def gerar_id_cliente(nome: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", nome.strip().lower()).strip("_")
    return f"cli_{slug or 'visitante'}"


@st.cache_resource
def iniciar_servicos():
    mongo = MongoService()
    redis_srv = RedisService()
    return mongo, redis_srv


try:
    mongo, redis_srv = iniciar_servicos()
except Exception as e:
    st.error(f"Não foi possível conectar aos bancos de dados: {e}")
    st.stop()

# Estados de navegação e sessão
if "token_sessao" not in st.session_state:
    st.session_state.token_sessao = None
if "pagina_ativa" not in st.session_state:
    st.session_state.pagina_ativa = "catalogo"

sessao_ativa = (
    redis_srv.validar_sessao(st.session_state.token_sessao)
    if st.session_state.token_sessao
    else None
)

# =============================================================================
# BARRA LATERAL: CONTA, MAIS VISTOS E INFORMAÇÕES TÉCNICAS (TTL / REDIS)
# =============================================================================
with st.sidebar:
    st.markdown("## 🛍️ Minha Conta")

    if not sessao_ativa:
        st.caption("Entre com seu nome para começar a comprar.")
        nome_input = st.text_input("Seu nome", placeholder="Ex: Felipe Leal")
        entrar_clicado = st.button("Entrar na Loja", type="primary", use_container_width=True)
    else:
        st.success(f"Olá, **{sessao_ativa['cliente_nome']}**!")
        if st.button("Sair da Conta", use_container_width=True):
            redis_srv.encerrar_sessao(st.session_state.token_sessao)
            st.session_state.token_sessao = None
            st.session_state.pagina_ativa = "catalogo"
            st.rerun()

    st.divider()
    st.markdown("### 🔥 Mais Vistos")
    ranking = redis_srv.obter_mais_acessados(limite=5)
    if ranking:
        for idx, item in enumerate(ranking, start=1):
            st.markdown(f"**{idx}.** {item['nome']} · `{item['acessos']}x`")
    else:
        st.caption("Explore os produtos para gerar o ranking em tempo real.")

    # Painel técnico recolhido com controles de TTL e chaves do Redis
    st.divider()
    with st.expander("🛠️ Informações técnicas"):
        ttl_sessao = st.number_input(
            "TTL da Sessão (segundos)",
            min_value=10,
            value=3600,
            step=30,
            help="Tempo de expiração do token de login no Redis (SETEX).",
        )
        ttl_cache = st.number_input(
            "TTL do Cache do Catálogo (segundos)",
            min_value=10,
            value=300,
            step=30,
            help="Tempo que a lista de produtos permanece na memória do Redis antes de expirar.",
        )

        if sessao_ativa:
            ttl_restante = redis_srv.client.ttl(f"sessao:{st.session_state.token_sessao}")
            st.caption(f"Cliente ID: `{sessao_ativa['cliente_id']}`")
            st.caption(f"Chave Carrinho: `carrinho:{sessao_ativa['cliente_id']}`")
            st.caption(f"Token Sessão: `{st.session_state.token_sessao[:16]}...`")
            if ttl_restante and ttl_restante > 0:
                st.caption(f"Expira em: `{ttl_restante}s`")

        if st.button("Limpar Cache do Catálogo", use_container_width=True):
            removidas = redis_srv.invalidar_cache_catalogo()
            st.toast(f"Cache limpo ({removidas} chave(s) removida(s)).")
            st.rerun()

        if st.button("Repor Estoque dos Produtos", use_container_width=True):
            mongo.produtos.update_many({}, {"$set": {"estoque": 20}})
            redis_srv.invalidar_cache_catalogo()
            st.toast("Estoque restaurado no MongoDB e cache invalidado!")
            st.rerun()

    # Processa o login usando o TTL definido em "Informações técnicas"
    if not sessao_ativa and entrar_clicado:
        if not nome_input.strip():
            st.warning("Digite seu nome para continuar.")
        else:
            cli_id = gerar_id_cliente(nome_input)
            token = redis_srv.criar_sessao(
                cliente_id=cli_id,
                cliente_nome=nome_input.strip(),
                ttl_segundos=int(ttl_sessao),
            )
            st.session_state.token_sessao = token
            st.session_state.pagina_ativa = "catalogo"
            st.rerun()

# =============================================================================
# CABEÇALHO DA LOJA
# =============================================================================
st.markdown(
    """
    <div class="store-banner">
        <h1>Smart Cart</h1>
        <p>Hardware, periféricos e setup gamer com entrega rápida e checkout instantâneo.</p>
    </div>
    """,
    unsafe_allow_html=True,
)

if not sessao_ativa:
    st.info("👈 Digite seu nome na barra lateral esquerda para acessar o catálogo e o carrinho.")
    st.stop()

cliente_id = sessao_ativa["cliente_id"]
cliente_nome = sessao_ativa["cliente_nome"]

itens_carrinho = redis_srv.obter_carrinho(cliente_id)
qtd_total_carrinho = sum(i["quantidade"] for i in itens_carrinho)
total_carrinho = redis_srv.calcular_total_carrinho(cliente_id)

# =============================================================================
# BARRA DE NAVEGAÇÃO PERSISTENTE
# =============================================================================
nav1, nav2, nav3, nav4 = st.columns(4)
with nav1:
    if st.button(
        "🖥️ Catálogo",
        use_container_width=True,
        type="primary" if st.session_state.pagina_ativa == "catalogo" else "secondary",
    ):
        st.session_state.pagina_ativa = "catalogo"
        st.rerun()
with nav2:
    if st.button(
        f"🛒 Carrinho ({qtd_total_carrinho})",
        use_container_width=True,
        type="primary" if st.session_state.pagina_ativa == "carrinho" else "secondary",
    ):
        st.session_state.pagina_ativa = "carrinho"
        st.rerun()
with nav3:
    if st.button(
        "📦 Meus Pedidos",
        use_container_width=True,
        type="primary" if st.session_state.pagina_ativa == "pedidos" else "secondary",
    ):
        st.session_state.pagina_ativa = "pedidos"
        st.rerun()
with nav4:
    if st.button(
        "✨ Para Você",
        use_container_width=True,
        type="primary" if st.session_state.pagina_ativa == "recomendacoes" else "secondary",
    ):
        st.session_state.pagina_ativa = "recomendacoes"
        st.rerun()

st.write("")

# =============================================================================
# PÁGINA 1: CATÁLOGO DE PRODUTOS
# =============================================================================
if st.session_state.pagina_ativa == "catalogo":
    col_busca, col_cat, col_est = st.columns([3, 2, 1.2])
    with col_busca:
        termo_busca = st.text_input(
            "Pesquisar",
            placeholder="Buscar por nome, marca ou categoria...",
            label_visibility="collapsed",
        )
    with col_cat:
        categoria = st.selectbox(
            "Categoria",
            [
                "Todas",
                "Periféricos",
                "Informática",
                "Gamer",
                "Hardware",
                "Armazenamento",
                "Monitores",
            ],
            label_visibility="collapsed",
        )
    with col_est:
        apenas_estoque = st.checkbox("Disponíveis", value=True)

    produtos, origem = redis_srv.listar_produtos_com_cache(
        mongo_service=mongo,
        categoria=categoria,
        termo_busca=termo_busca,
        apenas_em_estoque=apenas_estoque,
        ttl_segundos=int(ttl_cache),
    )

    st.caption(f"⚡ Fonte de carregamento: {origem} | TTL configurado: {int(ttl_cache)}s")

    if not produtos:
        st.warning("Nenhum produto encontrado com esses filtros.")
    else:
        cols = st.columns(2)
        for idx, prod in enumerate(produtos):
            with cols[idx % 2]:
                estoque_qtd = int(prod.get("estoque", 0))
                categorias_html = "".join(
                    f'<span class="badge-cat">{c}</span>'
                    for c in prod.get("categorias", [])
                )
                estoque_html = (
                    f'<span class="stock-ok">● Em estoque ({estoque_qtd} un.)</span>'
                    if estoque_qtd > 0
                    else '<span class="stock-out">● Esgotado</span>'
                )

                st.markdown(
                    f"""
                    <div class="product-card">
                        <div>
                            <span class="badge-brand">{prod.get('marca', 'Marca')}</span>
                            {categorias_html}
                        </div>
                        <h3 style="margin: 0.6rem 0 0.2rem 0; color: #f8fafc;">
                            {prod.get('nome', 'Produto')}
                        </h3>
                        <div class="price-tag">{formatar_brl(prod.get('preco', 0))}</div>
                        <div>{estoque_html}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                imagem_url = prod.get("imagem") or prod.get("imagem_url")
                if imagem_url:
                    st.image(imagem_url, use_container_width=True)

                b1, b2 = st.columns(2)
                with b1:
                    if st.button(
                        "👁️ Detalhes (+1 Ranking)",
                        key=f"view_{prod['_id']}",
                        use_container_width=True,
                    ):
                        redis_srv.registrar_acesso_produto(
                            str(prod["_id"]), prod.get("nome", "Produto")
                        )
                        st.toast(f"Visualização registrada: {prod.get('nome')}")
                        st.rerun()
                with b2:
                    if st.button(
                        "🛒 Adicionar ao Carrinho",
                        key=f"add_{prod['_id']}",
                        disabled=(estoque_qtd <= 0),
                        type="primary",
                        use_container_width=True,
                    ):
                        redis_srv.adicionar_item_carrinho(cliente_id, prod, quantidade=1)
                        st.toast(f"✅ {prod.get('nome')} adicionado ao carrinho!")
                        st.rerun()

# =============================================================================
# PÁGINA 2: CARRINHO E CHECKOUT
# =============================================================================
elif st.session_state.pagina_ativa == "carrinho":
    st.subheader("🛒 Seu Carrinho de Compras")

    if not itens_carrinho:
        st.info("Seu carrinho está vazio no momento.")
        if st.button("Voltar para o Catálogo", type="primary"):
            st.session_state.pagina_ativa = "catalogo"
            st.rerun()
    else:
        col_itens, col_resumo = st.columns([2.2, 1.2])

        with col_itens:
            for item in itens_carrinho:
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([3, 1.2, 1.3, 0.9])
                    with c1:
                        st.markdown(f"**{item['nome']}**")
                        st.caption(
                            f"{item.get('marca', '')} · Unitário: {formatar_brl(item['preco'])}"
                        )
                    with c2:
                        nova_qtd = st.number_input(
                            "Qtd",
                            min_value=1,
                            value=int(item["quantidade"]),
                            key=f"qtd_{item['produto_id']}",
                            label_visibility="collapsed",
                        )
                        if nova_qtd != item["quantidade"]:
                            redis_srv.atualizar_quantidade_carrinho(
                                cliente_id, item["produto_id"], int(nova_qtd)
                            )
                            st.rerun()
                    with c3:
                        subtotal = item["preco"] * item["quantidade"]
                        st.markdown(f"**{formatar_brl(subtotal)}**")
                    with c4:
                        if st.button("🗑️", key=f"del_{item['produto_id']}", help="Remover item"):
                            redis_srv.remover_item_carrinho(cliente_id, item["produto_id"])
                            st.rerun()

        with col_resumo:
            with st.container(border=True):
                st.markdown("### Resumo do Pedido")
                st.write(f"Itens selecionados: **{qtd_total_carrinho}**")
                st.write("Frete: **Grátis**")
                st.divider()
                st.markdown(f"## {formatar_brl(total_carrinho)}")

                forma_pgto = st.selectbox(
                    "Forma de Pagamento",
                    [
                        "PIX",
                        "Cartão de Crédito",
                        "Cartão de Débito",
                        "Boleto",
                    ],
                )

                if st.button("Finalizar Compra", type="primary", use_container_width=True):
                    codigo = redis_srv.finalizar_checkout(
                        cliente_id=cliente_id,
                        cliente_nome=cliente_nome,
                        mongo_service=mongo,
                        forma_pagamento=forma_pgto,
                    )
                    if codigo:
                        st.success(f"Compra confirmada! Pedido **{codigo}** registrado.")
                        st.balloons()
                    else:
                        st.error("Não foi possível finalizar o pedido.")

# =============================================================================
# PÁGINA 3: HISTÓRICO DE PEDIDOS (MONGODB ATLAS)
# =============================================================================
elif st.session_state.pagina_ativa == "pedidos":
    st.subheader("📦 Meus Pedidos")
    pedidos = mongo.listar_historico_pedidos(cliente_id)

    if not pedidos:
        st.info("Você ainda não realizou nenhum pedido nesta conta.")
    else:
        for ped in pedidos:
            data_fmt = ped["data_criacao"].strftime("%d/%m/%Y às %H:%M")
            with st.expander(
                f"Pedido {ped['codigo_pedido']}  ·  {formatar_brl(ped['valor_total'])}  ·  {ped['status']}"
            ):
                col_p1, col_p2 = st.columns(2)
                with col_p1:
                    st.write(f"**Pagamento:** {ped.get('forma_pagamento')}")
                with col_p2:
                    st.write(f"**Data:** {data_fmt}")

                st.divider()
                for item in ped.get("itens", []):
                    st.write(
                        f"• **{item.get('nome')}** — {item.get('quantidade')}x "
                        f"({formatar_brl(item.get('preco', 0))} cada)"
                    )

# =============================================================================
# PÁGINA 4: RECOMENDAÇÕES (NEO4J)
# =============================================================================
elif st.session_state.pagina_ativa == "recomendacoes":
    st.subheader("✨ Recomendados para Você")
    st.info(
        "Área reservada para o motor de recomendação em grafos (Neo4j) baseado no histórico de compras."
    )