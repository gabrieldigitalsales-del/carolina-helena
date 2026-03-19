# Carolina Helena - V2 Flask para Railway

Projeto em Flask com painel administrativo, catálogo, carrinho lateral, checkout por WhatsApp e conteúdo editável.

## O que entrou na V2

- Home com **lançamentos, categorias e mais vendidos**
- Busca na coleção por nome ou descrição
- Carrinho lateral abrindo automaticamente ao adicionar item
- Botão **Comprar agora** levando direto ao checkout
- Checkout com:
  - nome
  - WhatsApp
  - endereço completo
  - pagamento por cartão de crédito, cartão de débito, dinheiro ou Pix
- Pedido final enviado para o WhatsApp da loja
- Página de contato com:
  - link para WhatsApp
  - link para Instagram
  - mapa da loja
  - horário de atendimento
- Página Sobre com texto editável no admin
- Painel admin para:
  - editar textos principais do site
  - trocar logo
  - trocar imagem da página Sobre
  - editar contatos, mapa e horários
  - editar títulos e subtítulos da home
  - adicionar, editar e remover categorias
  - adicionar, editar e remover produtos
  - adicionar, editar e remover banners
  - visualizar pedidos recebidos
- Banner com `object-fit: cover`, então qualquer imagem enviada preenche a área do banner
- Footer com direitos autorais reservados e link do Instagram
- Layout claro em marrom claro e verde suave
- Estrutura pronta para Railway

## Login do painel

Padrão:

- Usuário: `admin`
- Senha: `admin123`

Em produção, altere por variáveis de ambiente:

- `ADMIN_USERNAME`
- `ADMIN_PASSWORD`
- ou `ADMIN_PASSWORD_HASH`

## Rodando localmente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

## Deploy no Railway

1. Suba este projeto para um repositório Git.
2. No Railway, crie um novo projeto apontando para o repositório.
3. Configure pelo menos:
   - `SECRET_KEY`
   - `ADMIN_USERNAME`
   - `ADMIN_PASSWORD`
4. O `Procfile` já está pronto com `gunicorn app:app`.
5. O projeto pode usar SQLite localmente. Para produção, prefira PostgreSQL via `DATABASE_URL`.

## Observações

- As imagens iniciais são de demonstração e podem ser trocadas no painel.
- O footer está no código, como solicitado.
- O admin controla a maior parte do conteúdo do site sem precisar editar o código.


## Login do admin

Acesse `/admin/login`

Credenciais padrão:
- usuário: `admin`
- senha: `admin123`

Se quiser trocar no Railway, crie a variável `ADMIN_PASSWORD`.
Só use `ADMIN_PASSWORD_HASH` se você realmente quiser trabalhar com senha criptografada.
