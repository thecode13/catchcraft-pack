# -*- coding: utf-8 -*-
"""
Gerador da textura da "Bolsa do Pescador" (armazenamento portatil de 54
slots, ver FishermanBag.java). Item continua Material.CHEST 100% vanilla -
so' a textura muda, via item_model opt-in (mesmo padrao de peixes/ticket/varas).

Item PLANO (minecraft:item/generated): e' segurado/visto no inventario e no
chao como um item comum (bau nao dropa como bloco 3D quando serializado desse
jeito), nunca cai como o baú vanilla com abertura animada.

Desenho: bolsa/mochila de couro de pescador - corpo arredondado castanho,
aba de fecho por cima presa com uma corda cruzada em X, e um pequeno anzol
pendurado na alca como detalhe de identidade (associacao imediata com pesca,
distinguindo de um bau ou bundle vanilla generico).

Paleta propria (couro cru -> couro escuro -> costura), coerente com o resto
do pack (contorno/escuro/medio/claro) mas sem reaproveitar nenhuma paleta de
trofeu, pra nao ser confundida com um trofeu no inventario.

Rode indiretamente:

    python tools/gerar_trofeus.py    # gera trofeus + peixes + ticket + varas + bolsa + zip
"""
from __future__ import annotations

import os

from PIL import Image

import gerar_trofeus as T

SIZE = 32
NOME = "bolsa_pescador"

TRANSPARENTE = (0, 0, 0, 0)

# Couro cru -> couro escuro -> costura/metal, tom marrom, propria da bolsa
# (nao reaproveita paleta de trofeu de proposito - ver docstring do modulo).
PALETA_BOLSA = T.paleta("#2a180c", "#5c3820", "#8a5a34", "#c08a52", brilho="#e8c391")
COR_CORDA = "#d9c79a"
COR_CORDA_SOMBRA = "#a89568"
COR_ANZOL = "#8f9aa1"
COR_ANZOL_BRILHO = "#d9e2e6"


def desenha(pal):
    o, D, M, L, s = (T.rgb(pal[k]) for k in ("o", "D", "M", "L", "s"))
    corda = T.rgb(COR_CORDA)
    corda_sombra = T.rgb(COR_CORDA_SOMBRA)
    anzol = T.rgb(COR_ANZOL)
    anzol_brilho = T.rgb(COR_ANZOL_BRILHO)

    img = Image.new("RGBA", (SIZE, SIZE), TRANSPARENTE)
    px = img.load()

    # --- corpo da bolsa: saco arredondado, mais largo embaixo (trapezio com
    # cantos cortados), ocupando o centro do canvas 32x32 -----------------
    x0, x1 = 8, 23
    y_top, y_bot = 12, 27

    for y in range(y_top, y_bot + 1):
        # afunila um pouco perto do topo (gargalo da bolsa) e arredonda
        # os cantos inferiores cortando 1-2px nas quinas.
        left, right = x0, x1
        if y < y_top + 3:
            left, right = x0 + 2, x1 - 2
        if y > y_bot - 2:
            left, right = x0 + 2, x1 - 2
        for x in range(left, right + 1):
            corte = (y == y_bot and (x == left or x == right))
            px[x, y] = D if corte else M

    # sombreado: metade direita mais escura, metade esquerda com luz (mesmo
    # truque de "atlas metal" usado nos troféus, so' que pintado direto).
    for y in range(y_top, y_bot + 1):
        for x in range(x0, (x0 + x1) // 2):
            if px[x, y] == M:
                px[x, y] = L

    # contorno da bolsa
    for y in range(y_top, y_bot + 1):
        left, right = x0, x1
        if y < y_top + 3 or y > y_bot - 2:
            left, right = x0 + 2, x1 - 2
        px[left, y] = o
        px[right, y] = o
    for x in range(x0 + 2, x1 - 1):
        px[x, y_top] = o

    # --- aba de fecho: faixa horizontal escura perto do topo, com costura
    # em X por cima (leitura clara de "fivela/nó", nao um bau) ------------
    aba_y0, aba_y1 = y_top + 4, y_top + 7
    for y in range(aba_y0, aba_y1 + 1):
        for x in range(x0 + 1, x1):
            px[x, y] = D
    for x in range(x0 + 1, x1):
        px[x, aba_y0] = o
        px[x, aba_y1] = o

    # corda cruzada em X sobre a aba
    cx0, cx1 = x0 + 3, x1 - 3
    for i, x in enumerate(range(cx0, cx1 + 1)):
        t = i / max(1, (cx1 - cx0))
        y_desc = round(aba_y0 + t * (aba_y1 - aba_y0))
        y_asc = round(aba_y1 - t * (aba_y1 - aba_y0))
        px[x, y_desc] = corda
        px[x, y_asc] = corda_sombra if y_asc != y_desc else corda

    # --- alca superior: arco fino de corda ligando os dois lados, com o
    # anzol pendurado no meio como assinatura visual do item --------------
    alca_y = y_top - 4
    for x in range(x0 + 3, x1 - 2):
        px[x, alca_y] = corda
    px[x0 + 3, alca_y + 1] = corda
    px[x0 + 3, alca_y + 2] = corda_sombra
    px[x1 - 3, alca_y + 1] = corda
    px[x1 - 3, alca_y + 2] = corda_sombra
    for x in range(x0 + 3, x1 - 2):
        px[x, y_top - 1] = TRANSPARENTE if px[x, y_top - 1] == TRANSPARENTE else px[x, y_top - 1]

    # anzol pequeno pendurado no centro da alca
    hx, hy = (x0 + x1) // 2, alca_y + 3
    for dy in range(0, 3):
        px[hx, hy + dy] = anzol
    for dx, dy in ((0, 3), (1, 3), (1, 2), (1, 1)):
        px[hx + dx, hy + dy] = anzol
    px[hx, hy] = anzol_brilho

    # --- costura decorativa nas laterais do corpo (pontos claros) --------
    for y in range(aba_y1 + 2, y_bot - 2, 2):
        px[x0 + 1, y] = s
        px[x1 - 1, y] = s

    return img


def catalogo_bolsa():
    """Um unico item: (nome, imagem, rotulo)."""
    return [(NOME, desenha(PALETA_BOLSA), "Bolsa do Pescador")]


def gera(itens):
    for nome, img, _ in itens:
        img.save(os.path.join(T.TEX_DIR, nome + ".png"))
        T.escreve_json(os.path.join(T.MODEL_DIR, nome + ".json"), {
            "parent": "minecraft:item/generated",
            "textures": {"layer0": f"{T.NS}:item/{nome}"},
        })
        T.escreve_json(os.path.join(T.ITEM_DIR, nome + ".json"), {
            "model": {"type": "minecraft:model", "model": f"{T.NS}:item/{nome}"}
        })


if __name__ == "__main__":
    for d in (T.TEX_DIR, T.MODEL_DIR, T.ITEM_DIR):
        os.makedirs(d, exist_ok=True)
    itens = catalogo_bolsa()
    gera(itens)
    print(f"{len(itens)} bolsa(s) gerada(s) em", T.TEX_DIR)
