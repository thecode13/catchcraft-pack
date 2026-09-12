# -*- coding: utf-8 -*-
"""
Gerador da textura do Reward Ticket (vale de nivel de XP do Minecraft).

E' um item generico: nao varia por boss nem por nivel, so' um "vale +N
niveis" (ver RewardTicket.java). Entregue em duas situacoes - captura de
peixe-boss e level-up do jogador - por isso o desenho e' neutro (nenhum
peixe especifico estampado), so' um selo de autenticidade.

Item PLANO (minecraft:item/generated), igual aos peixes: e' segurado e visto
no inventario, nunca cai no chao com volume proprio.

Paleta: OURO (a mesma dos trofeus "Primeiro Domador", ja definida em
gerar_trofeus.py) - o ticket e' recompensa de prestigio, entao usa a cor que
o jogador ja associa a conquista rara no pack.

Rode indiretamente:

    python tools/gerar_trofeus.py    # gera trofeus + peixes + ticket + zip
"""
from __future__ import annotations

import os

from PIL import Image

import gerar_trofeus as T

SIZE = 32
NOME = "ticket_recompensa"

TRANSPARENTE = (0, 0, 0, 0)


def desenha(pal):
    """Vale dourado com bordas denteadas (selo/cupom), canhoto destacado por
    uma linha de perfuracao e um selo circular com marca de "aprovado" - a
    leitura que separa este item de um pedaco de papel qualquer."""
    o = T.rgb(pal["o"])
    D = T.rgb(pal["D"])
    M = T.rgb(pal["M"])
    L = T.rgb(pal["L"])
    s = T.rgb(pal["s"])

    img = Image.new("RGBA", (SIZE, SIZE), TRANSPARENTE)
    px = img.load()

    x0, x1 = 2, 29
    y0, y1 = 9, 22
    ymid = (y0 + y1) // 2

    # corpo solido do vale
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            px[x, y] = M

    # borda
    for x in range(x0, x1 + 1):
        px[x, y0] = D
        px[x, y1] = D
    for y in range(y0, y1 + 1):
        px[x0, y] = D
        px[x1, y] = D

    # denteado tipo selo postal: perfura a borda de cima/baixo a cada 3px
    for x in range(x0 + 1, x1, 3):
        px[x, y0] = o
        px[x, y1] = o

    # entalhe semicircular nas pontas (ticket "arrancado" do talao)
    for dx, dy in ((0, 0), (1, 0), (0, 1), (0, -1)):
        px[x0 + dx, ymid + dy] = TRANSPARENTE
        px[x1 - dx, ymid + dy] = TRANSPARENTE

    # linha de perfuracao vertical: separa um canhoto estreito a esquerda
    xp = x0 + 8
    for y in range(y0, y1 + 1):
        if y % 2 == 0:
            px[xp, y] = o
    px[xp, y0] = TRANSPARENTE
    px[xp, y1] = TRANSPARENTE

    # estrela no canhoto
    cx, cy = x0 + 4, ymid
    for dx, dy in ((0, -2), (0, 2), (-2, 0), (2, 0), (0, 0),
                   (-1, -1), (1, -1), (-1, 1), (1, 1)):
        px[cx + dx, cy + dy] = s

    # selo circular ("aprovado") no corpo principal, a direita do canhoto
    sx, sy, r = 20, ymid, 5
    for y in range(sy - r, sy + r + 1):
        for x in range(sx - r, sx + r + 1):
            d2 = (x - sx) ** 2 + (y - sy) ** 2
            if d2 <= r * r:
                px[x, y] = L if d2 <= (r - 1) ** 2 else D

    # marca de verificacao ("check") dentro do selo
    check = ((-2, 0), (-1, 1), (0, 2), (1, 1), (2, -1), (3, -2))
    for dx, dy in check:
        px[sx + dx, sy + dy] = o

    # brilho especular no selo
    px[sx - 2, sy - 3] = s
    px[sx - 1, sy - 3] = s

    return img


def catalogo_ticket():
    """Um unico item: (nome, imagem, rotulo)."""
    return [(NOME, desenha(T.OURO), "Ticket")]


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
    itens = catalogo_ticket()
    gera(itens)
    print(f"{len(itens)} ticket(s) gerado(s) em", T.TEX_DIR)
