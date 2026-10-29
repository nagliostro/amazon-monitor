"""Monitora produtos (Amazon e outras lojas) e avisa pelo Telegram quando ficam disponíveis.

A lista de produtos fica em produtos.json (editada pela interface em docs/index.html).
O último status de cada produto fica em estado.json.

Variáveis de ambiente:
  DURACAO_MIN       por quantos minutos esta execução fica checando (padrão: 4; 0 = uma rodada)
  INTERVALO_S       segundos entre rodadas (padrão: 60)
  TELEGRAM_TOKEN    token do bot (@BotFather)
  TELEGRAM_CHAT_ID  seu chat id
"""

import html as html_lib
import json
import random
import re
import sys
import time
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

DURACAO_MIN = float(os.getenv("DURACAO_MIN", "4"))
INTERVALO_S = float(os.getenv("INTERVALO_S", "60"))
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

PASTA = Path(__file__).parent
ARQUIVO_PRODUTOS = PASTA / "produtos.json"
ARQUIVO_ESTADO = PASTA / "estado.json"
FUSO_BR = timezone(timedelta(hours=-3))

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
}


def agora() -> str:
    return datetime.now(FUSO_BR).strftime("%Y-%m-%d %H:%M")


def preco_para_float(texto) -> float | None:
    if isinstance(texto, (int, float)):
        return float(texto)
    texto = str(texto or "")
    if "," in texto:  # formato brasileiro: 1.234,56
        texto = texto.replace(".", "").replace(",", ".")
    numeros = re.sub(r"[^\d.]", "", texto)
    try:
        return float(numeros)
    except ValueError:
        return None


def formatar_preco(valor: float | None) -> str:
    if valor is None:
        return "?"
    return "R$ " + f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def asin_da_url(url: str) -> str | None:
    m = re.search(r"/(?:dp|gp/product)/([A-Z0-9]{10})", url)
    return m.group(1) if m else None


def link_compra(produto: dict) -> str:
    url = produto["url"]
    if "amazon." in urlparse(url).netloc and (asin := asin_da_url(url)):
        return f"https://www.amazon.com.br/gp/aws/cart/add.html?ASIN.1={asin}&Quantity.1=1"
    return url


# ---------- leitura das páginas ----------

def checar_amazon(sopa: BeautifulSoup, produto: dict) -> dict:
    disponibilidade = (sopa.select_one("#availability") or sopa.new_tag("x")).get_text(" ", strip=True)
    tem_botao = bool(sopa.select_one("#add-to-cart-button, #buy-now-button"))
    preco_el = sopa.select_one(
        "#corePrice_feature_div .a-offscreen, #corePriceDisplay_desktop_feature_div .a-offscreen, "
        "#apex_desktop .a-offscreen, #price_inside_buybox"
    )
    vendedor_el = sopa.select_one(
        "#merchantInfoFeature_feature_div, #tabular-buybox, #merchant-info, #sellerProfileTriggerId"
    )
    vendedor = vendedor_el.get_text(" ", strip=True)[:80] if vendedor_el else ""

    disponivel = tem_botao and "indisponível" not in disponibilidade.lower()
    motivo = ""
    if disponivel and produto.get("so_amazon", True) and "amazon" not in vendedor.lower():
        disponivel, motivo = False, f"vendedor não é a Amazon ({vendedor[:40]})"
    return {
        "disponivel": disponivel,
        "preco": preco_para_float(preco_el.get_text(strip=True)) if preco_el else None,
        "vendedor": vendedor,
        "motivo": motivo,
    }


def ofertas_json_ld(sopa: BeautifulSoup) -> list[dict]:
    """Extrai as ofertas schema.org (Product → offers) que a maioria das lojas publica."""
    ofertas = []

    def visitar(no):
        if isinstance(no, list):
            for item in no:
                visitar(item)
        elif isinstance(no, dict):
            tipo = no.get("@type")
            tipos = tipo if isinstance(tipo, list) else [tipo]
            if any(t in ("Offer", "AggregateOffer") for t in tipos):
                ofertas.append(no)
            for valor in no.values():
                if isinstance(valor, (list, dict)):
                    visitar(valor)

    for script in sopa.select('script[type="application/ld+json"]'):
        try:
            visitar(json.loads(script.string or ""))
        except json.JSONDecodeError:
            continue
    return ofertas


def checar_generico(sopa: BeautifulSoup, html: str, produto: dict) -> dict:
    texto_esgotado = (produto.get("texto_esgotado") or "").strip().lower()
    ofertas = ofertas_json_ld(sopa)

    disponivel = None
    preco = None
    for oferta in ofertas:
        disp = str(oferta.get("availability", "")).lower()
        if "instock" in disp or "preorder" in disp or "limitedavailability" in disp:
            disponivel = True
        elif disp and disponivel is None:
            disponivel = False
        valor = preco_para_float(oferta.get("price") or oferta.get("lowPrice"))
        if valor and (preco is None or valor < preco):
            preco = valor

    if disponivel is None:
        meta = sopa.select_one('meta[property="product:availability"], meta[property="og:availability"]')
        if meta and meta.get("content"):
            disponivel = meta["content"].lower() in ("instock", "in stock", "preorder", "available for order")

    if preco is None:
        meta = sopa.select_one('meta[property="product:price:amount"], meta[itemprop="price"]')
        if meta and meta.get("content"):
            preco = preco_para_float(meta["content"])

    # o texto de esgotado definido pelo usuário vence o que a página declara
    if texto_esgotado:
        disponivel = texto_esgotado not in html_lib.unescape(html).lower()

    if disponivel is None:
        return {"disponivel": False, "preco": preco, "motivo": "não deu para saber; defina o texto de esgotado"}
    return {"disponivel": disponivel, "preco": preco, "motivo": ""}


def checar(sessao: requests.Session, produto: dict) -> dict:
    """Retorna {"status": "disponivel" | "indisponivel" | "bloqueado" | "erro", ...}."""
    url = produto["url"]
    try:
        resp = sessao.get(url, headers=HEADERS, timeout=30)
    except requests.RequestException as e:
        return {"status": "erro", "motivo": str(e)[:120]}

    html = resp.text
    if resp.status_code in (403, 429, 503) or "validateCaptcha" in html:
        return {"status": "bloqueado", "motivo": f"a loja bloqueou a leitura (HTTP {resp.status_code})"}
    if resp.status_code != 200:
        return {"status": "erro", "motivo": f"HTTP {resp.status_code}"}

    sopa = BeautifulSoup(html, "html.parser")
    if "amazon." in urlparse(url).netloc:
        r = checar_amazon(sopa, produto)
    else:
        r = checar_generico(sopa, html, produto)

    preco_min = produto.get("preco_min")
    preco_max = produto.get("preco_max")
    if r["disponivel"] and r["preco"] is not None:
        if preco_max and r["preco"] > preco_max:
            r["disponivel"], r["motivo"] = False, f"preço {formatar_preco(r['preco'])} acima do máximo"
        elif preco_min and r["preco"] < preco_min:
            r["disponivel"], r["motivo"] = False, f"preço {formatar_preco(r['preco'])} abaixo do mínimo"

    r["status"] = "disponivel" if r.pop("disponivel") else "indisponivel"
    return r


# ---------- telegram e arquivos ----------

def enviar_telegram(texto: str) -> None:
    if not (TELEGRAM_TOKEN and TELEGRAM_CHAT_ID):
        print("[telegram não configurado]", texto)
        return
    requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        json={"chat_id": TELEGRAM_CHAT_ID, "text": texto, "parse_mode": "HTML"},
        timeout=20,
    ).raise_for_status()


def mensagem_alerta(produto: dict, r: dict, teste: bool = False) -> str:
    topo = "🧪 <b>TESTE</b>\n\n" if teste else ""
    nome = html_lib.escape(produto.get("nome") or produto["url"])[:120]
    linhas = [f"{topo}🚨 <b>DISPONÍVEL!</b>", nome, f"Preço: {formatar_preco(r.get('preco'))}"]
    if r.get("vendedor"):
        linhas.append(f"Vendedor: {html_lib.escape(r['vendedor'])}")
    linhas += ["", f"👉 <a href=\"{link_compra(produto)}\">Comprar agora</a>"]
    if link_compra(produto) != produto["url"]:
        linhas.append(f"<a href=\"{produto['url']}\">Abrir página do produto</a>")
    return "\n".join(linhas)


def ler_json(arquivo: Path, padrao):
    try:
        return json.loads(arquivo.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return padrao


def salvar_json(arquivo: Path, dados) -> None:
    arquivo.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    produtos = ler_json(ARQUIVO_PRODUTOS, {"produtos": []})["produtos"]

    if "--teste-telegram" in sys.argv:
        alvo = os.getenv("PRODUTO_ID", "")
        produto = next((p for p in produtos if p["id"] == alvo), None)
        if produto:
            enviar_telegram(mensagem_alerta(produto, {"preco": produto.get("preco_max")}, teste=True))
        else:
            ativos = sum(1 for p in produtos if p.get("ativo", True))
            enviar_telegram(f"✅ Monitor funcionando.\n{ativos} produto(s) ativo(s) sendo monitorado(s).")
        return 0

    estado = ler_json(ARQUIVO_ESTADO, {})
    if "disponivel" in estado:  # formato antigo, de um produto só
        estado = {}
    ativos = [p for p in produtos if p.get("ativo", True)]
    if not ativos:
        print("Nenhum produto ativo.")
        return 0

    sessao = requests.Session()
    fim = time.time() + DURACAO_MIN * 60
    mudou = False

    while True:
        for produto in ativos:
            r = checar(sessao, produto)
            print(time.strftime("%H:%M:%S"), produto["id"], json.dumps(r, ensure_ascii=False))
            anterior = estado.get(produto["id"], {})

            # captcha/erro não mudam o status salvo: só ficam registrados como aviso
            if r["status"] in ("bloqueado", "erro"):
                if anterior.get("aviso") != r["motivo"]:
                    estado[produto["id"]] = {**anterior, "aviso": r["motivo"]}
                    mudou = True
                continue

            if r["status"] == "disponivel" and anterior.get("status") != "disponivel":
                enviar_telegram(mensagem_alerta(produto, r))

            novo = {
                "status": r["status"],
                "preco": r.get("preco"),
                "motivo": r.get("motivo", ""),
                "alterado_em": anterior.get("alterado_em", agora()),
            }
            if (novo["status"], novo["preco"]) != (anterior.get("status"), anterior.get("preco")):
                novo["alterado_em"] = agora()
            if novo != anterior:
                estado[produto["id"]] = novo
                mudou = True
            time.sleep(random.uniform(2, 5))

        if mudou:
            # remove produtos que saíram da lista
            ids = {p["id"] for p in produtos}
            estado = {k: v for k, v in estado.items() if k in ids}
            salvar_json(ARQUIVO_ESTADO, estado)
            mudou = False

        if time.time() + INTERVALO_S > fim:
            break
        time.sleep(INTERVALO_S + random.uniform(-10, 10))

    return 0


if __name__ == "__main__":
    sys.exit(main())
