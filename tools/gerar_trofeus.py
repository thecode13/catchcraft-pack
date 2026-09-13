# -*- coding: utf-8 -*-
"""
Gerador dos trofeus 3D do CatchCraft.

Cada trofeu e' um modelo de blocos (cuboides), nao um sprite extrudado: no chao
ele tem volume de verdade. A arte sai toda daqui:

  PALETAS   -> as 4 cores de cada trofeu
  EMBLEMAS  -> o simbolo 8x8 em ASCII estampado na frente da taca
  elementos_taca / elementos_tomo -> a geometria, em coordenadas de 0 a 16

Rode:

    python tools/gerar_trofeus.py

Saida: pack/ (texturas + modelos + item defs), CatchCraftPack.zip, e em preview/
uma folha isometrica pra conferir as proporcoes sem abrir o jogo.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
from PIL import Image, ImageDraw, ImageFont

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PACK = os.path.join(RAIZ, "pack")
NS = "catchcraft"
TEX_DIR = os.path.join(PACK, "assets", NS, "textures", "item")
MODEL_DIR = os.path.join(PACK, "assets", NS, "models", "item")
ITEM_DIR = os.path.join(PACK, "assets", NS, "items")
PREVIEW_DIR = os.path.join(RAIZ, "preview")

# Ver README: acima do formato 64 o jogo exige min_format/max_format tambem.
# O numero sai de version.json -> pack_version.resource_major do jar vanilla.
PACK_FORMAT = 88

ATLAS = 32  # textura 32x32 dividida em quatro tiles de 16x16


# ---------------------------------------------------------------- paletas ----
def paleta(contorno, escuro, medio, claro, brilho="#ffffff"):
    return {"o": contorno, "D": escuro, "M": medio, "L": claro, "s": brilho}


PALETAS = {
    "kraken": paleta("#0a1f33", "#12496b", "#1f7fa8", "#4fc3d9"),
    "boto": paleta("#3d1030", "#7a2259", "#c04a92", "#f08fc4"),
    "iara": paleta("#12280f", "#2f5a24", "#57933d", "#8fc96a"),
    "leviata": paleta("#123244", "#2a6f8f", "#59aecb", "#b6e9f7"),
    "cobra-grande": paleta("#1a2a0c", "#3d5c17", "#6e9128", "#b3c94a"),
    "serpente-abissal": paleta("#1a0f2b", "#3b2260", "#63409c", "#a279d9"),
    # Peixedex: cores mais separadas do que na 1a versao. Oceano/Geladas e
    # Pantano/Selva ficavam parecidos demais no tamanho de slot.
    "peixedex-default": paleta("#2b2b2f", "#55565e", "#8b8d97", "#c8cad3"),
    "peixedex-ocean": paleta("#071c38", "#10396b", "#1c5fa8", "#3f8fd9"),
    "peixedex-river": paleta("#0d3330", "#1a6159", "#2f9c8c", "#77dcc9"),
    "peixedex-swamp": paleta("#241d0d", "#4d3f18", "#7d6a24", "#b09a44"),
    "peixedex-frozen": paleta("#254a55", "#4d9fb5", "#8fd6e8", "#dff6fd"),
    "peixedex-jungle": paleta("#08260c", "#17601c", "#2ba332", "#63e06a"),
}

# Paleta so' dos PEIXES (nao do trofeu) do cardume "default": o cinza chapado
# de peixedex-default lia bem como livro de Peixedex, mas ficava sem graca
# como escama de peixe de verdade. Prata-azulado e' cor real de escama
# (sardinha/salmao/robalo), mais vivo que cinza sem perder o ar "neutro" do
# grupo que nao caiu em nenhum bioma especifico.
PALETA_PEIXE_DEFAULT = paleta("#101820", "#25455e", "#4f89a8", "#a9d8e6")

OURO = paleta("#3d2a06", "#8a6413", "#d8a52a", "#ffe07a")
PAPEL = "#efe6cf"  # corte das paginas do tomo


# --------------------------------------------------------------- emblemas ----
EMBLEMAS = {
    "kraken": ["...gg...", "..gGGg..", ".gGg.g..", ".gG..g..",
               ".gGg....", "..gGg...", "...gGg..", "....gg.."],
    "boto": [".....gg.", "....gGg.", "...gGGg.", ".ggGGg..",
             "gGGGGg..", ".gGGGg..", "..g.gg..", "........"],
    "iara": ["..gg....", ".gGg....", ".gGg....", "..gGg...",
             "..gGgg..", ".ggGGGg.", "gGg.gGg.", ".g...g.."],
    "leviata": ["...gg...", "..gGGg..", ".gGGGGg.", "gGGGGGGg",
                ".gGGGGg.", "..gGGg..", "...gg...", "........"],
    "cobra-grande": ["........", "..gggg..", ".gGoGGg.", "gGGoGGGg",
                     "gGGoGGGg", ".gGoGGg.", "..gggg..", "........"],
    "serpente-abissal": ["..gggg..", ".g....g.", "g..gg..g", "g.gGGg.g",
                         "g.gGg..g", ".g.gg.g.", "..g..g..", "...gg..."],
    "peixedex-default": ["........", "..ggg...", ".gGGGgg.", "gGoGGGGg",
                         "gGGGGGGg", ".gGGGgg.", "..ggg...", "........"],
    "peixedex-ocean": ["........", ".gg..gg.", "gGGggGGg", ".gGGGGg.",
                       "........", ".gg..gg.", "gGGggGGg", ".gGGGGg."],
    "peixedex-river": ["...gg...", "...gg...", "..gGGg..", ".gGGGGg.",
                       "gGGGGGGg", "gGGGGGGg", ".gGGGGg.", "..gggg.."],
    "peixedex-swamp": ["..gggg..", ".gGGGGg.", "gGGGgGGg", "gGGg.gGg",
                       "gGGGgGGg", ".gGGGGg.", "..gggg..", "........"],
    "peixedex-frozen": ["...gg...", ".g.gg.g.", ".gggggg.", "ggGGGGgg",
                        "ggGGGGgg", ".gggggg.", ".g.gg.g.", "...gg..."],
    "peixedex-jungle": ["....gg..", "...gGg..", ".g.gGg.g", "gGggGggG",
                        ".gGgGgGg", "..gGGGg.", "...gGg..", "...gg..."],
}


# ------------------------------------------------------------------ tiles ----
# O atlas 32x32 tem quatro tiles de 16x16. Em JSON o uv sempre vai de 0 a 16
# sobre a textura inteira, entao cada tile ocupa metade: 8 unidades.
UV = {
    "metal": [0, 0, 8, 8],
    "emblema": [8, 0, 16, 8],
    "topo": [0, 8, 8, 16],
    "base": [8, 8, 16, 16],
}


def rgb(hex_str):
    h = hex_str.lstrip("#")
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255)


def mistura(cor_a, cor_b, t):
    """Interpola duas cores da paleta. t=0 -> cor_a, t=1 -> cor_b."""
    a, b = rgb(cor_a), rgb(cor_b)
    return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,)


# Perfil de reflexo do metal, coluna a coluna (x=1..14) dentro do tile.
# (para, t): a cor e' a interpolacao entre 'de' e 'para' na fracao t, andando
# L -> M -> D. Antes eram 3 bandas chapadas (L/M/D) e a taca parecia recortada
# em papel colorido; com 14 degraus ela le' como metal curvo de verdade.
# O "repique" em x=11 e' o segundo brilho: a luz que volta da borda direita.
PERFIL_METAL = [
    ("L", "s", 0.45),   # x=1  quina iluminada
    ("L", "s", 0.85),   # x=2  risco especular principal
    ("L", "s", 0.30),
    ("L", "M", 0.15),
    ("L", "M", 0.45),
    ("L", "M", 0.75),
    ("M", "M", 0.00),   # x=7  barriga do cilindro
    ("M", "D", 0.20),
    ("M", "D", 0.50),
    ("M", "D", 0.80),
    ("D", "M", 0.35),   # x=11 segundo brilho (luz refletida da borda)
    ("D", "D", 0.00),
    ("D", "o", 0.35),   # x=13 sombra de contato antes do contorno
    ("D", "o", 0.65),
]


def pinta_atlas(pal, pal_emblema, glifo, papel=None):
    """Monta a textura 32x32 com os quatro tiles do trofeu."""
    img = Image.new("RGBA", (ATLAS, ATLAS), (0, 0, 0, 0))
    px = img.load()

    # metal: gradiente de 14 degraus da esquerda (luz) pra direita (sombra)
    for y in range(16):
        for x in range(16):
            if x <= 0 or x >= 15:
                px[x, y] = rgb(pal["o"])
            else:
                de, para, t = PERFIL_METAL[x - 1]
                px[x, y] = mistura(pal[de], pal[para], t)
    for y in range(2, 14):  # risco de brilho: da leitura de metal polido
        px[2, y] = rgb(pal["s"])

    # topo: tom claro chapado com contorno
    for y in range(16):
        for x in range(16):
            borda = x in (0, 15) or y in (0, 15)
            px[x, y + 16] = rgb(pal["o"] if borda else (papel or pal["L"]))

    # base: tom escuro chapado com contorno
    for y in range(16):
        for x in range(16):
            borda = x in (0, 15) or y in (0, 15)
            px[x + 16, y + 16] = rgb(pal["o"] if borda else pal["D"])

    # emblema: fundo de metal (mesmo gradiente da lateral, pra casar as faces)
    for y in range(16):
        for x in range(16):
            if x <= 0 or x >= 15:
                px[x + 16, y] = rgb(pal["o"])
            else:
                de, para, t = PERFIL_METAL[x - 1]
                px[x + 16, y] = mistura(pal[de], pal[para], t)

    # medalhao escondado: fundo escuro + bisel. A borda de cima/esquerda fica
    # mais escura que o fundo e a de baixo/direita mais clara - e' o que da' a
    # impressao de que o simbolo esta REBAIXADO no metal, e nao colado nele.
    for y in range(2, 14):
        for x in range(18, 30):
            px[x, y] = rgb(pal["D"])
    sombra = mistura(pal["D"], pal["o"], 0.6)
    luz = mistura(pal["D"], pal["L"], 0.35)
    for x in range(19, 29):
        px[x, 3] = sombra
        px[x, 12] = luz
    for y in range(3, 13):
        px[19, y] = sombra
        px[28, y] = luz
    px[19, 12] = rgb(pal["D"])
    px[28, 3] = rgb(pal["D"])
    for x in range(18, 30):
        px[x, 2] = rgb(pal["o"])
        px[x, 13] = rgb(pal["o"])
    for y in range(2, 14):
        px[18, y] = rgb(pal["o"])
        px[29, y] = rgb(pal["o"])

    # sombra projetada do glifo: 1px pra baixo/direita, so' onde ainda e' fundo.
    sombra_glifo = mistura(pal["D"], pal["o"], 0.85)
    for dy, linha in enumerate(glifo):
        for dx, ch in enumerate(linha):
            if ch == ".":
                continue
            sx, sy = 21 + dx, 5 + dy
            gx, gy = sx - 20, sy - 4
            dentro_glifo = 0 <= gx < 8 and 0 <= gy < 8 and glifo[gy][gx] != "."
            if not dentro_glifo:
                px[sx, sy] = sombra_glifo
    cores = {"g": pal_emblema["L"], "G": pal_emblema["M"], "o": pal_emblema["o"]}
    for dy, linha in enumerate(glifo):
        for dx, ch in enumerate(linha):
            if ch != ".":
                px[20 + dx, 4 + dy] = rgb(cores[ch])
    return img


# -------------------------------------------------------------- geometria ----
def caixa(de, ate, faces):
    el = {"from": list(de), "to": list(ate), "faces": {}}
    for lado in ("north", "south", "east", "west", "up", "down"):
        tile = faces.get(lado, faces["_"])
        el["faces"][lado] = {"uv": UV[tile], "texture": "#0"}
    return el


TODO_METAL = {"_": "metal", "up": "topo", "down": "base"}


def elementos_taca(coroa=False):
    """Taca: base, pedestal, haste, bojo com o emblema na frente, borda e alcas."""
    els = [
        caixa([4, 0, 4], [12, 1.5, 12], {"_": "base"}),
        caixa([5, 1.5, 5], [11, 2.5, 11], {"_": "base", "up": "topo"}),
        caixa([7, 2.5, 7], [9, 6.5, 9], TODO_METAL),
        # saia: degrau que afunila a haste ate o bojo, senao a taca vira um caixote
        caixa([5, 6.5, 5], [11, 8, 11], {"_": "metal", "up": "metal", "down": "base"}),
        caixa([3.5, 8, 3.5], [12.5, 14, 12.5],
              {"_": "metal", "north": "emblema", "up": "topo", "down": "base"}),
        caixa([3, 14, 3], [13, 15.5, 13], {"_": "topo", "down": "base"}),
        caixa([1.5, 9.5, 7], [3.5, 13.5, 9], TODO_METAL),
        caixa([12.5, 9.5, 7], [14.5, 13.5, 9], TODO_METAL),
    ]
    if coroa:
        els.append(caixa([4, 15.5, 4], [12, 17, 12], {"_": "topo", "down": "base"}))
        for x0 in (4.5, 7.25, 10.0):
            els.append(caixa([x0, 17, 7], [x0 + 1.5, 18.5, 9], TODO_METAL))
    return els


def elementos_tomo():
    """Tomo: capa da frente com o emblema, lombada, miolo de paginas e contracapa."""
    return [
        caixa([3, 0.5, 3], [13, 14.5, 4.5],
              {"_": "metal", "north": "emblema", "up": "topo", "down": "base"}),
        caixa([3, 0.5, 4.5], [4.5, 14.5, 7.5], {"_": "base"}),
        caixa([4.5, 1, 4.5], [13, 14, 7.5], {"_": "topo"}),
        caixa([3, 0.5, 7.5], [13, 14.5, 9], TODO_METAL),
    ]


# O trofeu tem que ler no inventario E no chao. 'ground' e' o transform que o
# plugin usa no ItemDisplay dos trofeus exibidos, entao vale mais escala que o
# padrao vanilla (0.25), senao a peca fica minuscula no chao.
DISPLAY = {
    "gui": {"rotation": [22, -32, 0], "translation": [0, -1, 0], "scale": [0.72, 0.72, 0.72]},
    # O ItemDisplay centraliza o modelo na posicao da entidade, e o plugin a
    # coloca na superficie do bloco: sem correcao, meio trofeu fica enterrado.
    # O translation e' aplicado DEPOIS da escala (1 unidade = 1/16 de bloco,
    # independente do scale). Com scale 0.5 o modelo tem meio bloco de altura,
    # entao subir 4 unidades (= 1/4 de bloco) poe a base rente ao chao.
    # Calibrado na tentativa: 2 afundava, 8 flutuava.
    "ground": {"rotation": [0, 0, 0], "translation": [0, 4, 0], "scale": [0.5, 0.5, 0.5]},
    "fixed": {"rotation": [0, 180, 0], "translation": [0, 0, 0], "scale": [0.6, 0.6, 0.6]},
    "head": {"rotation": [0, 0, 0], "translation": [0, 14, 0], "scale": [1, 1, 1]},
    "thirdperson_righthand": {"rotation": [70, 45, 0], "translation": [0, 3, 1],
                              "scale": [0.4, 0.4, 0.4]},
    "firstperson_righthand": {"rotation": [0, 45, 0], "translation": [0, 2, 0],
                              "scale": [0.45, 0.45, 0.45]},
}


def modelo(nome, elementos):
    return {
        "textures": {"0": f"{NS}:item/{nome}", "particle": f"{NS}:item/{nome}"},
        "elements": elementos,
        "display": DISPLAY,
        # "side" ilumina como bloco (faces com sombra propria). "front" chapa a
        # luz e e' pra item plano - num modelo 3D ele mata o volume.
        "gui_light": "side",
    }


# ---------------------------------------------------------------- catalogo ---
BOSSES = ["kraken", "boto", "iara", "leviata", "cobra-grande", "serpente-abissal"]
CARDUMES = ["default", "ocean", "river", "swamp", "frozen", "jungle"]

ROTULOS = {
    "kraken": "Kraken", "boto": "Boto", "iara": "Iara", "leviata": "Leviata",
    "cobra-grande": "Cobra Grande", "serpente-abissal": "Serpente",
    "default": "Comuns", "ocean": "Oceano", "river": "Rio",
    "swamp": "Pantano", "frozen": "Geladas", "jungle": "Selva",
}


def catalogo():
    """(nome, textura, elementos, rotulo) de cada uma das 18 pecas."""
    itens = []
    for b in BOSSES:
        pal = PALETAS[b]
        itens.append((f"trofeu_{b}", pinta_atlas(pal, pal, EMBLEMAS[b]),
                      elementos_taca(), ROTULOS[b]))
    for b in BOSSES:
        pal = PALETAS[b]
        itens.append((f"trofeu_ouro_{b}", pinta_atlas(OURO, pal, EMBLEMAS[b]),
                      elementos_taca(coroa=True), ROTULOS[b] + " 1o"))
    for c in CARDUMES:
        chave = f"peixedex-{c}"
        pal = PALETAS[chave]
        itens.append((f"trofeu_peixedex_{c}",
                      pinta_atlas(pal, pal, EMBLEMAS[chave], papel=PAPEL),
                      elementos_tomo(), "Pdex " + ROTULOS[c]))
    return itens


def escreve_json(caminho, dados):
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, indent=2)
        f.write("\n")


# ----------------------------------------------------------------- preview ---
# Projecao isometrica simples, so pra conferir proporcao e leitura das pecas
# antes de abrir o jogo. Nao tenta imitar a iluminacao do Minecraft.
SOMBRA = {"up": 1.0, "north": 0.82, "west": 0.62}


def cor_media(img, tile):
    u0, v0, u1, v1 = [int(v * ATLAS / 16) for v in UV[tile]]
    recorte = img.crop((u0, v0, u1, v1)).convert("RGB")
    px = list(recorte.getdata())
    n = len(px)
    return tuple(sum(c[i] for c in px) // n for i in range(3))


def nome_do_tile(uv):
    return next(k for k, v in UV.items() if v == uv)


def render_iso(img, elementos, lado=140):
    tela = Image.new("RGBA", (lado, lado), (0, 0, 0, 0))
    draw = ImageDraw.Draw(tela)
    esc = lado / 30.0
    cx, cy = lado / 2, lado * 0.86

    def proj(x, y, z):
        return (cx + ((x - 8) - (z - 8)) * 0.87 * esc,
                cy + ((x - 8) + (z - 8)) * 0.5 * esc - y * esc)

    # painter's algorithm pelo CENTRO da peca: usar o canto errava a ordem entre
    # pecas que se encaixam (a borda saia por cima do bojo).
    def profundidade(e):
        cx_ = (e["from"][0] + e["to"][0]) / 2
        cz_ = (e["from"][2] + e["to"][2]) / 2
        cy_ = (e["from"][1] + e["to"][1]) / 2
        return (cx_ + cz_, cy_)

    for el in sorted(elementos, key=profundidade):
        x0, y0, z0 = el["from"]
        x1, y1, z1 = el["to"]
        quads = {
            "up": [(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)],
            "north": [(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)],
            "west": [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)],
        }
        for face, pts in quads.items():
            base = cor_media(img, nome_do_tile(el["faces"][face]["uv"]))
            f = SOMBRA[face]
            cor = tuple(min(255, int(c * f)) for c in base) + (255,)
            draw.polygon([proj(*p) for p in pts], fill=cor, outline=(0, 0, 0, 110))
    return tela


def folha_iso(itens):
    cols, cel = 6, 150
    linhas = (len(itens) + cols - 1) // cols
    sheet = Image.new("RGBA", (cel * cols, (cel + 20) * linhas), (30, 32, 38, 255))
    draw = ImageDraw.Draw(sheet)
    fonte = ImageFont.load_default()
    for i, (nome, img, els, rotulo) in enumerate(itens):
        cx, cy = (i % cols) * cel, (i // cols) * (cel + 20)
        sheet.alpha_composite(render_iso(img, els, cel - 10), (cx + 5, cy + 5))
        draw.text((cx + 8, cy + cel + 2), rotulo, font=fonte, fill=(225, 227, 233, 255))
    sheet.save(os.path.join(PREVIEW_DIR, "iso.png"))


def folha_texturas(itens):
    """Os atlas 32x32 ampliados. A folha iso achata cada face numa cor media,
    entao o acabamento do metal (gradiente, 2o brilho, bisel do medalhao) so'
    se confere aqui."""
    cols, cel, zoom = 6, 210, 6
    linhas = (len(itens) + cols - 1) // cols
    sheet = Image.new("RGBA", (cel * cols, (cel + 18) * linhas), (30, 32, 38, 255))
    draw = ImageDraw.Draw(sheet)
    fonte = ImageFont.load_default()
    for i, (nome, img, _, rotulo) in enumerate(itens):
        cx, cy = (i % cols) * cel, (i // cols) * (cel + 18)
        grande = img.resize((ATLAS * zoom, ATLAS * zoom), Image.NEAREST)
        sheet.alpha_composite(grande, (cx + (cel - ATLAS * zoom) // 2, cy + 6))
        draw.text((cx + 8, cy + cel + 2), rotulo, font=fonte, fill=(225, 227, 233, 255))
    sheet.save(os.path.join(PREVIEW_DIR, "texturas.png"))


def comandos_give(itens, peixes=(), tickets=(), varas=()):
    linhas = ["# Cole no chat pra ver cada peca. Nao precisa do plugin nem da flag.",
              "", "# --- trofeus ---"]
    for nome, _, _, _ in itens:
        linhas.append(f'/give @s minecraft:paper[minecraft:item_model="{NS}:{nome}"]')
    if peixes:
        linhas += ["", "# --- peixes (1 por especie + 1 por boss) ---"]
        for nome, _, _ in peixes:
            linhas.append(f'/give @s minecraft:paper[minecraft:item_model="{NS}:{nome}"]')
    if tickets:
        linhas += ["", "# --- ticket de recompensa (NAME_TAG no jogo, aqui via paper) ---"]
        for nome, _, _ in tickets:
            linhas.append(f'/give @s minecraft:paper[minecraft:item_model="{NS}:{nome}"]')
    if varas:
        linhas += ["", "# --- varas de marco (FISHING_ROD no jogo, aqui via paper) ---"]
        for nome, _, _ in varas:
            linhas.append(f'/give @s minecraft:paper[minecraft:item_model="{NS}:{nome}"]')
    with open(os.path.join(PREVIEW_DIR, "comandos_give.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(linhas) + "\n")


def empacota():
    destino = shutil.make_archive(os.path.join(RAIZ, "CatchCraftPack"), "zip", PACK)
    with open(destino, "rb") as f:
        sha1 = hashlib.sha1(f.read()).hexdigest()
    print(f"tamanho: {os.path.getsize(destino)} bytes")
    print(f"resource-pack-sha1={sha1}")
    return destino


def main():
    # Import tardio de proposito: gerar_peixes e gerar_ticket importam ESTE
    # modulo (pelas PALETAS/OURO), entao importar la' em cima fecharia um ciclo.
    import gerar_peixes
    import gerar_ticket
    import gerar_varas
    import gerar_bolsa

    for d in (TEX_DIR, MODEL_DIR, ITEM_DIR, PREVIEW_DIR):
        os.makedirs(d, exist_ok=True)
    for glifo in EMBLEMAS.values():
        assert len(glifo) == 8 and all(len(l) == 8 for l in glifo), "emblema fora de 8x8"

    itens = catalogo()
    for nome, img, elementos, _ in itens:
        img.save(os.path.join(TEX_DIR, nome + ".png"))
        escreve_json(os.path.join(MODEL_DIR, nome + ".json"), modelo(nome, elementos))
        escreve_json(os.path.join(ITEM_DIR, nome + ".json"), {
            "model": {"type": "minecraft:model", "model": f"{NS}:item/{nome}"}
        })

    escreve_json(os.path.join(PACK, "pack.mcmeta"), {
        "pack": {
            "description": "CatchCraft - trofeus e peixes",
            "pack_format": PACK_FORMAT,
            "min_format": PACK_FORMAT,
            "max_format": PACK_FORMAT,
        }
    })

    gerar_peixes.valida()
    peixes = gerar_peixes.catalogo_peixes()
    gerar_peixes.gera(peixes)

    tickets = gerar_ticket.catalogo_ticket()
    gerar_ticket.gera(tickets)

    varas = gerar_varas.catalogo_varas()
    gerar_varas.gera(varas)

    bolsa = gerar_bolsa.catalogo_bolsa()
    gerar_bolsa.gera(bolsa)

    folha_iso(itens)
    folha_texturas(itens)
    comandos_give(itens, peixes, tickets, varas)
    zipe = empacota()
    print(f"{len(itens)} trofeus 3D gerados em {MODEL_DIR}")
    print(f"{len(peixes)} peixes 2D gerados em {MODEL_DIR}")
    print(f"{len(tickets)} ticket(s) gerado(s) em {MODEL_DIR}")
    print(f"{len(varas)} vara(s) gerada(s) em {MODEL_DIR}")
    print(f"{len(bolsa)} bolsa(s) gerada(s) em {MODEL_DIR}")
    print(f"zip: {zipe}")


if __name__ == "__main__":
    main()
