# 🛒 SMartCArt — Módulo de Persistência Orientada a Documentos (MongoDB Atlas)

Módulo responsável pela camada de banco de dados orientado a documentos do projeto **SMartCArt** (**Estudo de Caso 01: E-Commerce Inteligente & Motor de Recomendação**), desenvolvido para a disciplina de **Implementação de Bancos de Dados NoSQL** (Prof. Ricardo Roberto de Lima).

---

## 🏗️ Arquitetura e Papel do MongoDB no Projeto

Na arquitetura de **Persistência Poliglota** da aplicação, o **MongoDB Atlas** atua como armazenamento principal para dados semi-estruturados, catálogo flexível e histórico transacional imutável:

* **Coleção `produtos` (Catálogo Flexível):** Armazena especificações técnicas heterogêneas em subdocumentos JSON (`especificacoes`), permitindo que diferentes categorias de hardware (mouses, monitores, teclados, SSDs) tenham atributos próprios sem necessidade de alteração de esquema.
* **Coleção `pedidos` (Checkout e Histórico):** Persiste os pedidos finalizados utilizando o padrão *Embedded Documents* (documentos embutidos), salvando o snapshot exato dos itens e valores no momento da compra.

---

## 📂 Estrutura dos Arquivos

```text
Smartcast/
├── mongo_service.py      # Classe de serviço com operações CRUD, busca textual e checkout atômico
├── populador_atlas.py    # Script de inicialização, criação de índices e carga inicial (seeds)
├── requirements.txt      # Dependências Python necessárias para conexão com o Atlas
└── README.md             # Documentação técnica e guia de uso
```

---

## ☁️ Configuração no MongoDB Atlas (Nuvem)

O banco de dados está hospedado em um cluster **M0 (AWS / São Paulo - `sa-east-1`)** no MongoDB Atlas:

* **Banco de Dados:** `smartcart_db`
* **Coleções:** `produtos` e `pedidos`
* **Acesso de Rede (Network Access):** Liberado (`0.0.0.0/0`) para permitir a conexão simultânea de toda a equipe e a demonstração ao vivo durante a defesa.
* **Índices Criados Automaticamente (`populador_atlas.py`):**
  * `idx_busca_textual_produtos`: Índice `TEXT` composto (`nome`, `marca`, `categorias`) em português para pesquisas na barra de busca.
  * `idx_categoria_preco`: Índice composto (`categorias`, `preco`) para filtragem e ordenação rápida.
  * `idx_codigo_pedido_unico`: Índice `UNIQUE` em `codigo_pedido` para evitar duplicidade de pedidos.
  * `idx_cliente_historico_pedidos`: Índice composto (`cliente_id`, `data_criacao DESC`) para consulta eficiente do histórico do cliente.

---

## ⚙️ Instalação e Execução

### 1. Instalar as dependências
No terminal, dentro da pasta do projeto, execute:
```bash
pip install -r requirements.txt
```
*(Certifique-se de que `pymongo[srv]` está listado no `requirements.txt`).*

### 2. Popular ou resetar o banco na nuvem (Opcional)
Caso precise restaurar os dados iniciais e recriar os índices no MongoDB Atlas:
```bash
python populador_atlas.py
```

---

## 🚀 Como Integrar na Interface Streamlit

A classe `MongoService` (em `mongo_service.py`) abstrai toda a comunicação com o Atlas. Basta importá-la no código principal do Streamlit:

```python
from mongo_service import MongoService

# Inicializa a conexão com o MongoDB Atlas
mongo = MongoService()

# 1. Listar todos os produtos ativos do catálogo
produtos = mongo.listar_produtos()

# 2. Filtrar por categoria e/ou termo de busca (Full-Text Search)
produtos_filtrados = mongo.listar_produtos(
    categoria="Gamer",
    termo_busca="Mouse",
    apenas_em_estoque=True
)

# 3. Buscar detalhes de um produto específico pelo ID
detalhes = mongo.buscar_produto_por_id("PROD001")

# 4. Finalizar Pedido (Checkout) e dar baixa atômica no estoque ($inc)
itens_carrinho = [
    {
        "produto_id": "PROD001",
        "nome": "Mouse Gamer Sem Fio RGB",
        "preco_unitario": 349.90,
        "quantidade": 1,
        "subtotal": 349.90
    }
]

codigo_pedido = mongo.salvar_pedido(
    cliente_id="CLI001",
    cliente_nome="Cliente Exemplo",
    itens_carrinho=itens_carrinho,
    valor_total=349.90,
    forma_pagamento="PIX"
)

# 5. Consultar histórico de compras do cliente
historico = mongo.listar_historico_pedidos("CLI001")
```