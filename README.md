# Monitor de Estoque → Telegram

Checa produtos da Amazon e de outras lojas pelo GitHub Actions (mais ou menos a cada minuto) e
manda uma mensagem no Telegram quando um deles fica disponível dentro da faixa de preço, com o
link para comprar.

## Interface

**https://nagliostro.github.io/amazon-monitor/**

Nela você adiciona, edita e pausa produtos, define a faixa de preço, manda alertas de teste,
força uma checagem e pausa o monitor inteiro. Para conectar, crie um token em
<https://github.com/settings/personal-access-tokens/new>:

- *Repository access*: **Only select repositories** → `amazon-monitor`
- *Permissions*: **Contents** e **Actions** → *Read and write*

O token fica salvo só no navegador onde você o colou.

## Lojas

- **Amazon**: lê o botão de compra, o preço e o vendedor. Pode exigir que o vendedor seja a Amazon.
- **Outras lojas** (Kabum, Magalu, Mercado Livre etc.): lê o estoque e o preço que a página
  declara em `schema.org`. Se a loja não declarar, preencha o **texto que indica esgotado**
  (ex.: "Esgotado"). Quando esse texto some da página, o produto conta como disponível.

## Arquivos

- `produtos.json`: a lista (editada pela interface)
- `estado.json`: último status de cada produto, para não repetir alertas
- `monitor.py`: a checagem
- `.github/workflows/monitor.yml`: agendamento (a cada 5 min, 4 min de checagem por execução)
- `docs/`: a interface (GitHub Pages) e o `design.md`

## Limitações

- O GitHub pode atrasar o agendamento em horários de pico e **desativa o cron depois de 60 dias**
  sem commits. Editar a lista pela interface conta como commit.
- Os IPs do GitHub são de datacenter, e algumas lojas respondem com captcha ou bloqueio. Isso
  aparece como aviso no produto.
- Os termos do GitHub Actions preferem uso ligado a software, então o GitHub pode desativar o workflow.
