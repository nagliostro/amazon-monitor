# Monitor Amazon → Telegram

Checa a página do produto mais ou menos a cada minuto pelo GitHub Actions. Quando o produto fica
disponível (vendido pela Amazon e abaixo do preço máximo), manda uma mensagem no Telegram com um
link que já põe o item no carrinho. Você só finaliza a compra.

## Configuração (uma vez)

1. **Bot do Telegram**
   - No Telegram, fale com **@BotFather** → `/newbot` → copie o **token**.
   - Mande qualquer mensagem para o seu bot novo e abra
     `https://api.telegram.org/bot<TOKEN>/getUpdates`. O número em `"chat":{"id": ...}` é o seu
     **chat id**.

2. **Repositório no GitHub** (público, para os minutos do Actions serem ilimitados)
   - Envie esta pasta para um repositório novo.
   - Em *Settings → Secrets and variables → Actions*:
     - **Secrets:** `TELEGRAM_TOKEN`, `TELEGRAM_CHAT_ID`
     - **Variables (opcionais):** `PRECO_MAXIMO` (ex.: `3500`), `SO_AMAZON` (`1` ou `0`), `ASIN`

3. **Teste:** aba *Actions → Monitor Amazon → Run workflow*. O log mostra o resultado de cada checagem.

Teste do Telegram no seu PC:

```
set TELEGRAM_TOKEN=...
set TELEGRAM_CHAT_ID=...
python monitor.py --teste-telegram
```

## Como funciona

- O agendamento dispara a cada 5 min. Cada execução fica 4 min checando a cada ~60 s.
- O `estado.json` guarda se o alerta já foi enviado, para não mandar mensagem repetida. Quando o
  produto esgota de novo, o alerta é rearmado.
- Se a Amazon devolver captcha, a checagem aparece como `bloqueado` no log e tenta de novo na próxima.

## Limitações

- O GitHub pode atrasar o agendamento em horários de pico e **desativa o cron depois de 60 dias**
  sem commits no repositório. Os commits do `estado.json` só acontecem quando o estado muda.
- Os IPs do GitHub são de datacenter, e a Amazon às vezes responde com captcha.
- Os termos do GitHub Actions preferem uso ligado a software. Monitoramento leve costuma passar,
  mas o GitHub pode desativar o workflow.
