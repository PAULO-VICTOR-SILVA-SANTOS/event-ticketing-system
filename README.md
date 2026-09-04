# Event Ticketing System

Sistema de venda e gerenciamento de ingressos para eventos, com emissão de ingressos digitais, pagamento online e envio automático de confirmações por e-mail.

Projeto desenvolvido como parte de portfólio, com foco em boas práticas de arquitetura de API, organização de código e integrações reais de mercado (pagamento e e-mail transacional).

## ✨ Funcionalidades (planejadas)

- Cadastro e gerenciamento de eventos
- Criação de lotes e tipos de ingresso (inteira, meia, VIP etc.)
- Checkout e pagamento via [Mercado Pago](https://www.mercadopago.com.br/)
- Emissão de ingresso digital (QR Code) por e-mail via [Resend](https://resend.com/)
- Validação de ingressos na entrada do evento
- Autenticação e autorização de usuários/organizadores

## 🛠 Stack

**Backend**
- [Python 3.13+](https://www.python.org/)
- [FastAPI](https://fastapi.tiangolo.com/) — framework web assíncrono
- [SQLAlchemy](https://www.sqlalchemy.org/) — ORM
- [Alembic](https://alembic.sqlalchemy.org/) — migrações de banco de dados
- [PostgreSQL](https://www.postgresql.org/) (via `psycopg2-binary`)
- [Pydantic](https://docs.pydantic.dev/) / `pydantic-settings` — validação de dados e configuração
- [Uvicorn](https://www.uvicorn.org/) — servidor ASGI

**Integrações**
- Mercado Pago — processamento de pagamentos
- Resend — envio de e-mails transacionais

**Frontend**
- A definir (pasta `frontend/` reservada para a aplicação cliente)

## 📁 Estrutura do projeto

```
event-ticketing-system/
├── backend/
│   └── app/
│       ├── main.py          # ponto de entrada da aplicação FastAPI
│       ├── core/             # configurações, segurança, utilitários centrais
│       ├── models/           # modelos ORM (SQLAlchemy)
│       ├── routes/           # rotas/endpoints da API
│       ├── schemas/          # schemas Pydantic (request/response)
│       └── services/         # regras de negócio e integrações externas
├── frontend/                 # aplicação cliente (a definir)
├── docs/                     # documentação adicional do projeto
├── requirements.txt
├── .env.example
└── README.md
```

## 🚀 Como rodar localmente

### Pré-requisitos

- Python 3.11+
- PostgreSQL em execução (local ou remoto)

### 1. Clone o repositório

```bash
git clone https://github.com/<seu-usuario>/event-ticketing-system.git
cd event-ticketing-system
```

### 2. Crie e ative um ambiente virtual

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/macOS
source venv/bin/activate
```

### 3. Instale as dependências

```bash
pip install -r requirements.txt
```

### 4. Configure as variáveis de ambiente

Copie o arquivo de exemplo e preencha com os seus valores:

```bash
cp .env.example .env
```

| Variável          | Descrição                                              |
|-------------------|----------------------------------------------------------|
| `DATABASE_URL`    | String de conexão do PostgreSQL                          |
| `SECRET_KEY`      | Chave secreta usada para autenticação/assinatura          |
| `MP_ACCESS_TOKEN` | Access Token da API do Mercado Pago                       |
| `MP_PUBLIC_KEY`   | Public Key do Mercado Pago (usada no frontend)             |
| `RESEND_API_KEY`  | API Key do Resend para envio de e-mails                   |

### 5. Execute as migrações (quando disponíveis)

```bash
alembic upgrade head
```

### 6. Suba a API

```bash
uvicorn backend.app.main:app --reload
```

A API estará disponível em `http://localhost:8000`, com documentação interativa em:

- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## 🗺 Roadmap

- [ ] Modelagem inicial do banco de dados (eventos, ingressos, pedidos, usuários)
- [ ] CRUD de eventos e tipos de ingresso
- [ ] Fluxo de checkout com Mercado Pago
- [ ] Geração de QR Code e envio de ingresso por e-mail
- [ ] Autenticação de usuários/organizadores
- [ ] Painel de validação de ingressos
- [ ] Frontend da aplicação

## 📄 Licença

Este projeto está sob a licença MIT. Veja o arquivo [LICENSE](LICENSE) para mais detalhes.
