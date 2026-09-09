# Sistema de Emissão de Ingressos

Sistema completo para venda e gestão de ingressos de eventos, com pagamento via Pix e cartão de crédito, emissão de ingresso digital com QR Code e check-in na portaria em tempo real.

🔗 **[Acesse o sistema em produção](https://event-ticketing-system-five.vercel.app)**
📄 **[Documentação da API](https://web-production-e71e8.up.railway.app/docs)**

## Sobre o projeto

Este sistema foi desenvolvido para um evento corporativo real — uma confraternização de uma equipe hospitalar — e está em produção, sendo utilizado de ponta a ponta: desde o cadastro e pagamento dos participantes até o check-in na entrada do evento. Não é um protótipo ou prova de conceito.

## Stack tecnológica

**Backend**
- Python 3.13
- FastAPI
- SQLAlchemy
- Alembic (migrações)
- PostgreSQL (Supabase)
- JWT (autenticação)

**Frontend**
- HTML5, CSS3 e JavaScript puro (sem framework)
- Painel administrativo completo + página pública de venda

**Pagamentos**
- Mercado Pago — Pix e Cartão de crédito via Checkout Bricks
- Webhook para confirmação automática de pagamento

**E-mail transacional**
- Resend

**Geração de ingresso**
- qrcode + Pillow

**Deploy**
- Backend: Railway
- Frontend: Vercel
- Banco de dados: Supabase

## Funcionalidades

Tudo listado abaixo já está implementado e em produção:

- Cadastro de participantes com detecção de duplicata (por e-mail ou WhatsApp)
- Pagamento via Pix (QR Code dinâmico) e Cartão de crédito, processados pelo Mercado Pago
- Confirmação automática de pagamento via webhook
- Emissão de ingresso digital com QR Code, enviado automaticamente por e-mail (Resend)
- Check-in por QR Code na portaria do evento
- Painel administrativo completo:
  - Dashboard com métricas do evento
  - Gestão de participantes
  - Gestão de despesas, com cálculo automático das taxas do Mercado Pago
  - Configurações do evento
- Tema claro/escuro no painel
- Proteção contra concorrência: lock a nível de banco para evitar overselling de vagas e cadastros duplicados em acessos simultâneos
- Expiração automática de cadastros pendentes não pagos (TTL de 20 minutos), liberando a vaga automaticamente

## Instalação e execução local

### Pré-requisitos

- Python 3.13+
- PostgreSQL (ou uma instância Supabase)
- Conta no Mercado Pago (credenciais de teste ou produção)
- Conta no Resend

### Passos

1. Clone o repositório

```bash
git clone https://github.com/PAULO-VICTOR-SILVA-SANTOS/event-ticketing-system.git
cd event-ticketing-system
```

2. Crie e ative um ambiente virtual

```bash
python3.13 -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```

3. Instale as dependências

```bash
pip install -r requirements.txt
```

4. Configure as variáveis de ambiente

Crie um arquivo `.env` na raiz do projeto com base no `.env.example`, incluindo:

```
DATABASE_URL=
SECRET_KEY=
MP_ACCESS_TOKEN=
MP_PUBLIC_KEY=
RESEND_API_KEY=
RESEND_FROM_EMAIL=
```

5. Execute as migrações

```bash
alembic upgrade head
```

6. Suba a aplicação

```bash
uvicorn backend.app.main:app --reload
```

A API estará disponível em `http://localhost:8000`, com documentação interativa em `/docs`.

7. Abra o frontend

Sirva os arquivos estáticos da pasta `frontend/` com um servidor local simples, por exemplo:

```bash
npx serve frontend
```

Ou use a extensão Live Server do VS Code, apontando para `frontend/index.html`.

## Próximos passos

- Lembrete automático 48h antes do evento (scheduler)
- Testes automatizados com cobertura completa (pytest)

## Licença

Este projeto está sob a licença MIT.
