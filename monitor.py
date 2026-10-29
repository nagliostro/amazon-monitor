"""Monitora um produto da Amazon e avisa pelo Telegram quando ele fica disponível.

Variáveis de ambiente:
  ASIN              código do produto (padrão: B0HK2KVYD7)
  PRECO_MAXIMO      só avisa se o preço for menor ou igual (ex.: 3500). Vazio = sem limite
  SO_AMAZON         "1" = só avisa se o vendedor for a Amazon (padrão: 1)
  DURACAO_MIN       por quantos minutos esta execução fica checando (padrão: 4)
  INTERVALO_S       segundos entre checagens (padrão: 60)
  TELEGRAM_TOKEN    token do bot (@BotFather)
  TELEGRAM_CHAT_ID  seu chat id
"""

import json
import os
import random
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ASIN = os.getenv("ASIN", "B0HK2KVYD7")
PRECO_MAXIMO = float(os.getenv("PRECO_MAXIMO") or "inf")
SO_AMAZON = os.getenv("SO_AMAZON", "1") == "1"
DURACAO_MIN = float(os.getenv("DURACAO_MIN", "4"))
INTERVALO_S = float(os.getenv("INTERVALO_S", "60"))
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

URL_PRODUTO = f"https://www.amazon.com.br/dp/{ASIN}"
URL_CARRINHO = f"https://www.amazon.com.br/gp/aws/cart/add.html?ASIN.1={ASIN}&Quantity.1=1"
ARQUIVO_ESTADO = Path(__file__).with_name("estado.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


def preco_para_float(texto: str) -> float | None:
    numeros = re.sub(r"[^\d,]", "", texto).replace(",", ".")
    try:
        return float(numeros)
    except ValueError:
        return None


def checar(sessao: requests.Session) -> dict:
    """Retorna {"status": "disponivel" | "indisponivel" | "bloqueado" | "erro", ...}."""
    try:
        resp = sessao.get(URL_PRODUTO, headers=HEADERS, timeout=30)
    except requests.RequestException as e:
        return {"status": "erro", "detalhe": str(e)}

    html = resp.text
    if resp.status_code != 200:
        return {"status": "erro", "detalhe": f"HTTP {resp.status_code}"}
    if "validateCaptcha" in html or "api-services-support@amazon.com" in html:
        return {"status": "bloqueado", "detalhe": "captcha da Amazon"}

    sopa = BeautifulSoup(html, "html.parser")
    titulo = (sopa.select_one("#productTitle") or sopa.new_tag("x")).get_text(strip=True)
    disponibilidade = (sopa.select_one("#availability") or sopa.new_tag("x")).get_text(" ", strip=True)
    tem_botao = bool(sopa.select_one("#add-to-cart-button, #buy-now-button"))

    preco_el = sopa.select_one(
        "#corePrice_feature_div .a-offscreen, #corePriceDisplay_desktop_feature_div .a-offscreen, "
        "#apex_desktop .a-offscreen, #price_inside_buybox"
    )
    preco_txt = preco_el.get_text(strip=True) if preco_el else ""
    preco = preco_para_float(preco_txt) if preco_txt else None

    vendedor_el = sopa.select_one(
        "#merchantInfoFeature_feature_div, #tabular-buybox, #merchant-info, #sellerProfileTriggerId"
    )
    vendedor = vendedor_el.get_text(" ", strip=True) if vendedor_el else ""
    vendido_pela_amazon = "amazon" in vendedor.lower()

    disponivel = tem_botao and "indisponível" not in disponibilidade.lower()
    motivo = ""
    if disponivel and SO_AMAZON and not vendido_pela_amazon:
        disponivel, motivo = False, f"vendedor não é a Amazon ({vendedor[:60]})"
    if disponivel and preco is not None and preco > PRECO_MAXIMO:
        disponivel, motivo = False, f"preço {preco_txt} acima do limite"

    return {
        "status": "disponivel" if disponivel else "indisponivel",
        "titulo": titulo,
        "preco": preco_txt,
        "vendedor": vendedor[:80],
        "disponibilidade": disponibilidade[:80],
        "motivo": motivo,
    }


def enviar_telegram(texto: str) -> None:
    if not (TELEGRAM_TOKEN and TELEGRAM_CHAT_ID):
        print("[telegram não configurado]", texto)
        return
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": texto, "parse_mode": "HTML"},
        timeout=20,
    ).raise_for_status()


def ler_estado() -> dict:
    try:
        return json.loads(ARQUIVO_ESTADO.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {"disponivel": False}


def salvar_estado(estado: dict) -> None:
    ARQUIVO_ESTADO.write_text(json.dumps(estado, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    if "--teste-telegram" in sys.argv:
        enviar_telegram(f"✅ Monitor configurado.\n<a href=\"{URL_PRODUTO}\">Produto monitorado</a>")
        return 0

    estado = ler_estado()
    sessao = requests.Session()
    fim = time.time() + DURACAO_MIN * 60

    while True:
        r = checar(sessao)
        print(time.strftime("%H:%M:%S"), json.dumps(r, ensure_ascii=False))

        if r["status"] == "disponivel" and not estado.get("disponivel"):
            enviar_telegram(
                f"🚨 <b>DISPONÍVEL!</b>\n{r['titulo'][:120]}\n"
                f"Preço: {r['preco'] or '?'}\nVendedor: {r['vendedor'] or '?'}\n\n"
                f"👉 <a href=\"{URL_CARRINHO}\">Colocar no carrinho e finalizar</a>\n"
                f"<a href=\"{URL_PRODUTO}\">Abrir página do produto</a>"
            )
            estado = {"disponivel": True, "desde": time.strftime("%Y-%m-%d %H:%M:%S")}
            salvar_estado(estado)
        elif r["status"] == "indisponivel" and estado.get("disponivel"):
            # voltou a esgotar: rearma o alerta para a próxima reposição
            estado = {"disponivel": False}
            salvar_estado(estado)

        if time.time() + INTERVALO_S > fim:
            break
        time.sleep(INTERVALO_S + random.uniform(-10, 10))

    return 0


if __name__ == "__main__":
    sys.exit(main())
