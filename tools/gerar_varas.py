# -*- coding: utf-8 -*-
"""
Gerador das texturas das 5 VARAS DE MARCO do CatchCraft (niveis 5/10/20/30/40:
Aprendiz/Veterana/Experiente/Mestra/Especialista - ver LevelRewardService.java
e CatchCraftCommand.java no plugin).

Item PLANO (minecraft:item/handheld_rod - mesmo parent da vara de pesca
vanilla, NAO minecraft:item/generated que e' usado por peixes/ticket): e'
segurado e visto no inventario/hotbar, nunca cai no chao com volume proprio
(a vara em si ja e' vanilla FISHING_ROD - so' a textura muda). O parent
handheld_rod da' o perfil fino correto na mao (generated fica largo/chapado,
como se fosse espada) e a animacao de "arco" ao lancar o anzol, igual vanilla.

RESOLUCAO: 32x32, mesma dos peixes/ticket - a vara e' um sprite diagonal fino
(cabo + vareta + linha), 16x16 nao daria espaco pra progressao de detalhe
(entalhes/aneis/brilho) entre os 5 tiers sem virar borrao.

PROGRESSAO POR TIER (madeira -> osso/prata -> ouro):
  aprendiz     -> madeira crua, cordao simples, sem guias na vareta.
  veterana     -> madeira reforcada + aneis de ferro na vareta.
  experiente   -> vareta de osso/prata, guias polidas, anzol visivel.
  mestra       -> prata encantada, brilho azulado, guias douradas.
  especialista -> ouro entalhado de ponta a ponta, brilho dourado (paleta
                  OURO, a mesma dos trofeus "Primeiro Domador" e do ticket).

Rode indiretamente:

    python tools/gerar_trofeus.py    # gera trofeus + peixes + ticket + varas + zip
"""
from __future__ import annotations

import os

from PIL import Image

import gerar_trofeus as T

SIZE = 32
TRANSPARENTE = (0, 0, 0, 0)

# Paletas proprias das varas (contorno, escuro, medio, claro, brilho).
# Madeira crua -> madeira reforcada -> osso/prata -> prata encantada -> OURO
# (a paleta OURO ja existe em gerar_trofeus.py, reaproveitada aqui de proposito
# pra bater com a cor de prestigio que o jogador ja associa ao pack).
PALETAS_VARA = {
    "aprendiz": T.paleta("#2b1c10", "#4d3319", "#7a5327", "#a9793f"),
    "veterana": T.paleta("#241a12", "#5a3f22", "#8a6033", "#b98a4c"),
    "experiente": T.paleta("#1c2226", "#4a555c", "#8b9aa3", "#d8e2e6"),
    "mestra": T.paleta("#151b2e", "#2f3f66", "#5a76ad", "#9fc1f2", brilho="#dff0ff"),
    "especialista": T.OURO,
}

# Cor da linha de pesca e do anzol - cinza-azulado neutro, igual em todo tier
# (a linha nao e' "material" da vara, entao nao progride com o resto).
LINHA = "#c9d3d8"
LINHA_SOMBRA = "#7d8a90"


def _linha(px, x0, y0, x1, y1, cor):
    """Bresenham simples: usado pra vareta/cabo/linha, tudo reto."""
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    x, y = x0, y0
    pontos = []
    while True:
        pontos.append((x, y))
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
    for px_, py_ in pontos:
        if 0 <= px_ < SIZE and 0 <= py_ < SIZE:
            px[px_, py_] = cor
    return pontos


def _espessa(px, pontos, cor, lado=(1, 0)):
    """Engorda uma linha 1px pro lado indicado, pra vareta nao ficar fiapo."""
    dx, dy = lado
    for x, y in pontos:
        nx, ny = x + dx, y + dy
        if 0 <= nx < SIZE and 0 <= ny < SIZE:
            px[nx, ny] = cor


def desenha(chave, pal):
    """Vara diagonal (canto inferior-esquerdo = cabo, superior-direito = ponta),
    no mesmo angulo do item vanilla, com progressao de acabamento por tier."""
    o, D, M, L, s = (T.rgb(pal[k]) for k in ("o", "D", "M", "L", "s"))

    img = Image.new("RGBA", (SIZE, SIZE), TRANSPARENTE)
    px = img.load()

    # cabo: grosso, canto inferior-esquerdo
    cabo = _linha(px, 3, 29, 11, 21, D)
    _espessa(px, cabo, D, (1, 0))
    _espessa(px, cabo, o, (-1, 0))
    # cordao/wraps no cabo: 3 aneis (aprendiz = corda simples, resto = metal)
    cor_wrap = M if chave == "aprendiz" else (L if chave != "especialista" else s)
    for i, (x, y) in enumerate(cabo):
        if i % 3 == 0:
            _p = (x - 1, y + 1)
            if 0 <= _p[0] < SIZE and 0 <= _p[1] < SIZE:
                px[_p] = cor_wrap

    # vareta: fina, do cabo ate a ponta no canto superior-direito
    vareta = _linha(px, 11, 21, 28, 4, M)
    _espessa(px, vareta, L, (1, -1) if chave != "especialista" else (1, 0))

    # guias (aneis) na vareta: aprendiz nao tem, os demais ganham mais conforme
    # o tier sobe - e' a leitura mais direta de "vara mais trabalhada".
    n_guias = {"aprendiz": 0, "veterana": 2, "experiente": 3,
               "mestra": 4, "especialista": 5}[chave]
    if n_guias:
        passo = len(vareta) // (n_guias + 1)
        cor_guia = o if chave == "veterana" else (s if chave in ("mestra", "especialista") else L)
        for g in range(1, n_guias + 1):
            x, y = vareta[g * passo]
            for dx, dy in ((0, -1), (0, 1), (-1, 0), (1, 0)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < SIZE and 0 <= ny < SIZE:
                    px[nx, ny] = cor_guia

    # entalhes dourados na vareta inteira, so' no Especialista - e' o item mais
    # "trabalhado" do lote, tem que se destacar mesmo em miniatura de slot.
    if chave == "especialista":
        for i, (x, y) in enumerate(vareta):
            if i % 2 == 0:
                for dx, dy in ((0, -1), (0, 1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < SIZE and 0 <= ny < SIZE and px[nx, ny] == TRANSPARENTE:
                        px[nx, ny] = s

    # linha de pesca: sai da ponta da vareta, cai numa curva simples ate um
    # anzol pequeno. Mesma pra todo tier (nao e' "material" da vara).
    tip_x, tip_y = vareta[-1]
    ganho = _linha(px, tip_x, tip_y, tip_x - 6, tip_y + 16, T.rgb(LINHA))
    _linha(px, tip_x + 1, tip_y + 1, tip_x - 5, tip_y + 17, T.rgb(LINHA_SOMBRA))
    hx, hy = ganho[-1]
    for dx, dy in ((0, 1), (1, 1), (1, 0), (0, 2)):
        nx, ny = hx + dx, hy + dy
        if 0 <= nx < SIZE and 0 <= ny < SIZE:
            px[nx, ny] = T.rgb(LINHA_SOMBRA)

    # brilho especular: mestra ganha halo azulado na vareta, especialista
    # ganha "faisca" dupla perto da ponta (leitura de item de prestigio).
    if chave == "mestra":
        for i, (x, y) in enumerate(vareta):
            if i % 4 == 1:
                nx, ny = x, y - 2
                if 0 <= nx < SIZE and 0 <= ny < SIZE:
                    px[nx, ny] = s
    if chave == "especialista":
        for dx, dy in ((0, 0), (1, -1), (-1, 1)):
            nx, ny = tip_x + dx - 2, tip_y + dy - 2
            if 0 <= nx < SIZE and 0 <= ny < SIZE:
                px[nx, ny] = (255, 255, 255, 255)

    return img


ORDEM = ["aprendiz", "veterana", "experiente", "mestra", "especialista"]
ROTULOS = {
    "aprendiz": "Vara Aprendiz", "veterana": "Vara Veterana",
    "experiente": "Vara Experiente", "mestra": "Vara Mestra",
    "especialista": "Vara Especialista",
}


def catalogo_varas():
    """(nome, imagem, rotulo) de cada uma das 5 varas de marco."""
    return [(f"vara_{chave}", desenha(chave, PALETAS_VARA[chave]), ROTULOS[chave])
            for chave in ORDEM]


def gera(itens):
    for nome, img, _ in itens:
        img.save(os.path.join(T.TEX_DIR, nome + ".png"))
        T.escreve_json(os.path.join(T.MODEL_DIR, nome + ".json"), {
            "parent": "minecraft:item/handheld_rod",
            "textures": {"layer0": f"{T.NS}:item/{nome}"},
        })
        T.escreve_json(os.path.join(T.ITEM_DIR, nome + ".json"), {
            "model": {"type": "minecraft:model", "model": f"{T.NS}:item/{nome}"}
        })


if __name__ == "__main__":
    for d in (T.TEX_DIR, T.MODEL_DIR, T.ITEM_DIR):
        os.makedirs(d, exist_ok=True)
    itens = catalogo_varas()
    gera(itens)
    print(f"{len(itens)} vara(s) gerada(s) em", T.TEX_DIR)
