# -*- coding: utf-8 -*-
"""
Gerador das texturas de PEIXE do CatchCraft (uma por ESPECIE).

Peixe nao vai pro chao: e' um item que o jogador segura e ve no inventario.
Entao o modelo e' PLANO (minecraft:item/generated, uma camada layer0) - mais
barato e mais legivel no slot que um modelo 3D.

RESOLUCAO: 32x32 (era 16x16).
  A troca foi necessaria pra este passo: em 16x16 nao cabe tentaculo de kraken,
  casco de tartaruga com patas, bigode de bagre ou torso de sereia - tudo virava
  a mesma bolha oval. 32x32 continua sendo textura de item vanilla (qualquer
  potencia de 2 serve pra item/generated) e custa ~4x o pixel, o que e' nada:
  47 itens minusculos. As mascaras de IA continuam 16x16 e sao amostradas em
  blocos 2x2 (x//2, y//2) - elas sao malha de fundo, nao precisam de detalhe.

A arte sai de cinco coisas:

  ARQUETIPOS      -> geradores de FORMA (13 familias: peixe, serpente,
                     cefalopode, quelonio, anfibio, raia, golfinho, sereia,
                     lodo, cristal, tesouro, bota, cipo)
  PALETAS         -> as cores, reaproveitadas de gerar_trofeus (peixedex-<cardume>)
  MASCARA_ESCAMA  -> um padrao de brilho 16x16, 0..9, que malha o corpo
  MASCARA_BOSS    -> segunda mascara de IA, so' nos 6 peixes-boss
  VARIACAO        -> padrao/cauda/dorsal/brilho escolhidos pelo HASH DO ID

FORMA POR ESPECIE
  Antes toda especie usava UMA silhueta oval de peixe generico e so' a pintura
  mudava. Agora cada id do config.yml aponta pra um ARQUETIPO + parametros de
  proporcao (ver CATALOGO_FORMA): o atum e' fusiforme, a sardinha e' fina, a
  garoupa e' bojuda, a enguia serpenteia, o kraken tem manto e tentaculos, a
  tartaruga tem casco e patas. O nome do item e a silhueta finalmente batem.

VARIACAO POR ESPECIE
  O sorteio continua deterministico: md5(id) -> padrao/cauda/dorsal/brilho.
  Rodar o script duas vezes da' exatamente o mesmo PNG. A forma pode FIXAR
  cauda/dorsal quando a especie real exige (atum tem cauda lunada, ponto final);
  no resto o hash manda. A paleta continua sendo a do CARDUME, entao o jogador
  le' "isto e' um peixe de rio" pela cor e "isto e' um pirarucu" pela forma.

Sobre as MASCARAS: vieram de texturas geradas por IA (Stable Diffusion, modelo
minecraft-item-16px). Aproveitamos so' a LUMINANCIA: reduzida pra 16x16,
normalizada em 0..9 e congelada aqui em ASCII.
  MASCARA_ESCAMA  <- prompt "a shiny golden fish"     (todos os peixes)
  MASCARA_BOSS    <- prompt "a magic fishing lure"    (so' os bosses)

Rode indiretamente:

    python tools/gerar_trofeus.py    # gera trofeus + peixes + zip + preview
"""
from __future__ import annotations

import hashlib
import math
import os

from PIL import Image, ImageDraw, ImageFont

import gerar_trofeus as T

SIZE = 32  # lado da textura de peixe

# --------------------------------------------------------------- mascaras ---
# Luminancia normalizada 0..9 (0 = mais escuro, 9 = mais brilhante).
MASCARA_ESCAMA = [
    "0080324548404520",
    "0321340210610250",
    "2200056964200027",
    "4162024002440081",
    "0527324380005022",
    "0404947332482232",
    "0202432162430350",
    "3523223621522501",
    "8402606320010223",
    "2421420710584422",
    "0025233402553653",
    "2331414228700240",
    "2901421152240407",
    "3106042003041105",
    "5505604022032462",
    "4001240242107324",
]

# Segunda mascara de IA ("a magic fishing lure"). Usada SO' nos peixes-boss,
# somada por cima da malha normal: o boss fica com um brilho irregular que
# nenhum peixe comum do mesmo cardume tem.
MASCARA_BOSS = [
    "1344255104534632",
    "4953454100103742",
    "4745353310313754",
    "0145222110120373",
    "0252313330162355",
    "1243145520310565",
    "0161114403003662",
    "1342758403665642",
    "2542666303534344",
    "5640245110312375",
    "2212057330444442",
    "4521047311345622",
    "2720242055265354",
    "3643333023045475",
    "2441253636445662",
    "1201567736755422",
]

# Acima de CLARO o pixel sobe um degrau na rampa; abaixo de ESCURO, desce um.
# Faixa estreita de proposito: a mascara e' pra dar malha, nao pra virar ruido.
MASCARA_CLARO = 9
MASCARA_ESCURO = 0

# No boss a faixa e' mais larga (7/1): queremos justamente que ele cintile.
BOSS_CLARO = 7
BOSS_ESCURO = 1

# ------------------------------------------------------------------ zonas ---
# o = contorno   k = dorso   B = corpo   b = ventre
# T = cauda      f = nadadeira   w = dente/presa (branco)
# e = olho (brilho)   E = pupila
RAMPA = ["o", "D", "M", "L", "s"]

# (tom base, recebe mascara). Cauda e nadadeiras ficam chapadas: sao as pecas
# que definem a silhueta, e malhar elas embaralha o contorno do bicho.
ZONAS = {
    "o": ("o", False),   # contorno
    "k": ("D", True),    # dorso
    "B": ("M", True),    # corpo
    "b": ("L", False),   # ventre (ja e' o tom mais claro)
    "T": ("M", False),   # cauda
    "f": ("D", False),   # nadadeiras / membros
    "w": ("s", False),   # dente, presa, casco claro
    "e": ("s", False),   # olho
    "E": ("o", False),   # pupila
}

# Zonas de carne: sao as que recebem o PADRAO da especie.
ZONAS_CORPO = ("k", "B", "b")
# Zonas que ganham contorno automatico quando encostam no vazio.
ZONAS_SOLIDAS = ("B", "T")


# ------------------------------------------------------- toolkit de desenho --
def nova_grade():
    return [["." for _ in range(SIZE)] for _ in range(SIZE)]


def _p(g, x, y, ch):
    x, y = int(round(x)), int(round(y))
    if 0 <= x < SIZE and 0 <= y < SIZE:
        g[y][x] = ch


def _coluna(g, x, y0, y1, ch="B"):
    for y in range(int(round(y0)), int(round(y1)) + 1):
        _p(g, x, y, ch)


def _elipse(g, cx, cy, rx, ry, ch="B", y_min=None, y_max=None):
    for y in range(SIZE):
        if y_min is not None and y < y_min:
            continue
        if y_max is not None and y > y_max:
            continue
        for x in range(SIZE):
            if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0:
                _p(g, x, y, ch)


def contorna(g):
    """Toda carne que encosta no vazio vira contorno. Isso poupa desenhar borda
    a mao em 13 arquetipos - e garante que forma nenhuma fique 'flutuando' sem
    linha, que e' o que separa item legivel de borrao no slot."""
    marca = []
    for y in range(SIZE):
        for x in range(SIZE):
            if g[y][x] not in ZONAS_SOLIDAS:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if not (0 <= nx < SIZE and 0 <= ny < SIZE) or g[ny][nx] == ".":
                    marca.append((x, y))
                    break
    for x, y in marca:
        g[y][x] = "o"


def zonear(g):
    """Converte a carne 'B' em dorso/corpo/ventre pela altura dentro da coluna.
    E' o que da' volume: escuro em cima, claro na barriga."""
    for x in range(SIZE):
        ys = [y for y in range(SIZE) if g[y][x] == "B"]
        if not ys:
            continue
        topo, base = min(ys), max(ys)
        alt = base - topo + 1
        for y in ys:
            f = (y - topo) / alt
            if f < 0.34:
                g[y][x] = "k"
            elif f > 0.72:
                g[y][x] = "b"


def olho(g, x, y):
    """Olho 2x2 com pupila. Desenhado por ultimo: se passasse antes do contorno
    o proprio contorno comia a pupila nas cabecas finas."""
    _p(g, x, y, "e")
    _p(g, x + 1, y, "e")
    _p(g, x, y + 1, "E")
    _p(g, x + 1, y + 1, "e")


# -------------------------------------------------------------- variacoes ---
CAUDAS = ("bifurcada", "leque", "lanceta")
DORSAIS = ("alta", "baixa", "espinhosa")
BRILHOS = ("alto", "meio", "baixo")
PADROES = ["malha", "listras_v", "listras_h", "manchas", "gradiente", "diamante"]


def _delta_padrao(padrao, x, y, semente):
    """Quanto o pixel anda na RAMPA por causa do padrao da especie (-1, 0, +1).
    As coordenadas entram divididas por 2 (x//2): assim a listra continua com a
    MESMA largura visual que tinha na textura 16x16 aprovada pelo usuario."""
    x, y = x // 2, y // 2
    if padrao == "malha":
        return 0
    if padrao == "listras_v":                    # barras verticais (tipo perca)
        return -1 if (x + semente) % 3 == 0 else 0
    if padrao == "listras_h":                    # faixas laterais (tipo cavala)
        return 1 if (y + semente) % 3 == 0 else 0
    if padrao == "manchas":                      # pintas fixas (tipo truta)
        return 1 if ((x * 5 + y * 3 + semente) % 7) < 2 else 0
    if padrao == "gradiente":                    # cabeca escura -> cauda clara
        return 1 if x >= 9 else (-1 if x <= 4 else 0)
    if padrao == "diamante":                     # escama losangular
        return 1 if (x + y) % 4 == 0 else (-1 if (x - y) % 4 == 0 else 0)
    return 0


def variacao(especie_id):
    """md5(id) -> a combinacao de padrao/cauda/dorsal/brilho. Deterministico."""
    h = hashlib.md5(especie_id.encode("utf-8")).digest()
    return {
        "padrao": PADROES[h[0] % len(PADROES)],
        "cauda": CAUDAS[h[1] % len(CAUDAS)],
        "dorsal": DORSAIS[h[2] % len(DORSAIS)],
        "brilho": BRILHOS[h[3] % len(BRILHOS)],
        "semente": h[4] % 5,
    }


# ================================================================ ARQUETIPOS =
# Cada arquetipo e' uma funcao (params, variacao) -> grade 32x32 ja zoneada.
# Todos desenham a carne em 'B'/'T'/'f', chamam contorna() e zonear(), e so'
# entao pousam olho e dentes.

def _perfil(t, tp, a, b):
    """Altura relativa do corpo na fracao t do comprimento (0 = focinho)."""
    if t <= tp:
        return (t / tp) ** a if tp > 0 else 1.0
    return ((1.0 - t) / (1.0 - tp)) ** b


def _cauda(g, xped, cy, hped, estilo, tlen, thmax):
    """Cauda colada no pedunculo. 'lanceta' = lunada (atum), 'bifurcada' =
    forquilha classica, 'leque' = arredondada (carpa, garoupa).

    Duas regras aprendidas no primeiro preview em 32px:
      1) o entalhe NUNCA pode comecar na primeira coluna, senao a cauda se
         descola do corpo e vira uma setinha solta no slot;
      2) cada lobo precisa de >=3px de altura, senao o contorno automatico come
         o miolo inteiro e a cauda fica so' um risco escuro."""
    hped = max(hped, 2.0)
    thmax = max(thmax, hped + 3.0)
    for i in range(tlen):
        f = (i + 1) / tlen
        recorte = max(0.0, (i - 0.5) / tlen)      # nada de entalhe na raiz
        if estilo == "leque":
            # abre em seno e arredonda as quinas de tras: crescer em sqrt fazia
            # a cauda virar um TIJOLO colado no peixe.
            h = hped + (thmax - hped) * math.sin(math.pi * 0.5 * f)
            if f > 0.70:
                h *= 0.82
            entalhe = 0.0
        elif estilo == "lanceta":
            h = hped + (thmax - hped) * (f ** 0.55)
            entalhe = (h - 2.5) * recorte
        else:  # bifurcada
            h = hped + (thmax - hped) * f
            entalhe = (h - 3.0) * recorte
        x = xped + 1 + i
        _coluna(g, x, cy - h, cy + h, "T")
        if entalhe >= 1.0:
            for y in range(int(round(cy - entalhe)), int(round(cy + entalhe)) + 1):
                _p(g, x, y, ".")


def forma_peixe(p, v):
    """Familia peixe: uma so' equacao de perfil, proporcoes por especie.

    Isso cobre 26 das 47 especies - o truque e' que os PARAMETROS mudam o
    bicho de verdade: atum (hmax 6, corpo pra frente, cauda lunada) nao se
    confunde com sardinha (hmax 3, longa) nem com acara-disco (hmax 10,
    quase redondo)."""
    g = nova_grade()
    x0, x1 = p.get("x0", 3), p.get("x1", 21)
    cy = p.get("cy", 16)
    hmax = p.get("hmax", 6.0)
    tp, a, b = p.get("tp", 0.40), p.get("a", 0.55), p.get("b", 0.80)
    ventre = p.get("ventre", 1.0)
    L = x1 - x0

    topos, bases = {}, {}
    for x in range(x0, x1 + 1):
        t = (x - x0) / L
        # piso de 1.8 (=4px): com pedunculo de 2px o contorno automatico
        # deixava a juncao corpo-cauda toda escura e a cauda parecia solta.
        h = max(1.8, hmax * _perfil(t, tp, a, b))
        yt, yb = cy - h, cy + h * ventre
        _coluna(g, x, yt, yb, "B")
        topos[x], bases[x] = int(round(yt)), int(round(yb))

    hped = max(2.0, hmax * _perfil(0.94, tp, a, b))
    _cauda(g, x1, cy, hped, p.get("cauda") or v["cauda"],
           p.get("tlen", 5), p.get("thmax", hmax * 1.15))

    # dorsal
    dorsal = p.get("dorsal") or v["dorsal"]
    da, db = int(x0 + L * p.get("dorsal_ini", 0.34)), int(x0 + L * p.get("dorsal_fim", 0.68))
    for x in range(da, db + 1):
        if dorsal == "baixa":
            alt = 1
        elif dorsal == "espinhosa":
            alt = 3 if (x - da) % 2 == 0 else 1
        else:
            alt = 2 + int(3 * math.sin(math.pi * (x - da + 0.5) / (db - da + 1)))
        for k in range(1, alt + 1):
            _p(g, x, topos.get(x, cy) - k, "f")

    # anal + peitoral
    aa, ab = int(x0 + L * 0.62), int(x0 + L * 0.80)
    for x in range(aa, ab + 1):
        for k in range(1, 3):
            _p(g, x, bases.get(x, cy) + k, "f")
    pxx = int(x0 + L * 0.30)
    for dx in range(3):
        for dy in range(2):
            _p(g, pxx + dx, cy + int(hmax * 0.45) + dy, "f")

    _boca(g, p, x0, cy, hmax)
    contorna(g)
    zonear(g)
    _acessorios(g, p, x0, cy, hmax)
    olho(g, x0 + p.get("olho_dx", 3), cy - p.get("olho_dy", 2))
    return g


def _boca(g, p, x0, cy, hmax):
    """Apendices de focinho desenhados ANTES do contorno (viram parte do corpo)."""
    boca = p.get("boca")
    if boca == "espada":                    # espadarte / peixe-espada
        for i in range(1, 10):
            _p(g, x0 - i, cy - 1, "B")
            if i <= 5:                      # base do rostro mais grossa
                _p(g, x0 - i, cy, "B")
    elif boca == "bico":                    # golfinho / boto
        for i in range(1, 6):
            _p(g, x0 - i, cy, "B")
            _p(g, x0 - i, cy + 1, "B")


def _acessorios(g, p, x0, cy, hmax):
    """Detalhes DEPOIS do contorno: dentes e bigodes precisam ficar por cima."""
    boca = p.get("boca")
    if boca == "dentes":                    # piranha: a mandibula e' a identidade
        for i in range(4):
            _p(g, x0 + i, cy + int(hmax * 0.42), "w")
        _p(g, x0, cy + int(hmax * 0.42) - 1, "w")
        _p(g, x0 + 2, cy + int(hmax * 0.42) + 1, "w")
    elif boca == "bigode":                  # bagre, piraiba, bacalhau
        for i in range(1, 6):
            _p(g, x0 - i + 1, cy + 1 + i, "f")
            _p(g, x0 - i + 2, cy - 1 + int(i * 0.4), "f")
    elif boca == "grande":                  # garoupa: bocarra escura
        for i in range(4):
            _p(g, x0 + i, cy + 1 + (i // 3), "o")


def forma_serpente(p, v):
    """Corpo em onda senoidal: enguia, serpente abissal, cobra-grande, leviata.
    Nao tem pedunculo nem cauda em leque - e' fita continua que afina."""
    g = nova_grade()
    x0, x1 = p.get("x0", 2), p.get("x1", 29)
    cy, amp = p.get("cy", 16), p.get("amp", 5.0)
    ondas = p.get("ondas", 1.6)
    esp = p.get("espessura", 2.2)
    fase = p.get("fase", 0.0)
    L = x1 - x0

    def yc(x):
        t = (x - x0) / L
        return cy + amp * math.sin(2 * math.pi * ondas * t + fase)

    for x in range(x0, x1 + 1):
        t = (x - x0) / L
        r = esp * (1.0 - 0.72 * max(0.0, (t - 0.45)) / 0.55)   # afina pra cauda
        if t < 0.10:
            r = esp * (1.0 + 0.55 * (0.10 - t) / 0.10)         # cabeca mais grossa
        y_a, y_b = yc(x), yc(min(x + 1, x1))
        _coluna(g, x, min(y_a, y_b) - r, max(y_a, y_b) + r, "B")

    if p.get("espinhos"):                   # leviata / cobra-grande: crista
        for x in range(x0 + 2, x1 - 4, 2):
            t = (x - x0) / L
            r = esp * (1.0 - 0.6 * max(0.0, t - 0.45))
            _p(g, x, yc(x) - r - 1, "f")
    if p.get("barbatana"):                  # enguia: franja continua no dorso
        for x in range(x0 + 5, x1 - 2):
            _p(g, x, yc(x) - esp - 1, "f")

    _boca(g, p, x0, yc(x0), esp)
    contorna(g)
    zonear(g)
    _acessorios(g, p, x0, yc(x0), esp)
    if p.get("mandibula"):                  # leviata: fileira de dentes
        for i in range(4):
            _p(g, x0 + i, yc(x0) + esp * 0.9, "w")
    olho(g, x0 + 2, yc(x0) - 2)
    return g


def forma_cefalopode(p, v):
    """Kraken: manto (cabeca-saco) em cima, olho enorme, e OITO bracos caindo.
    Nenhum peixe do pack tem nada parecido - e' o item mais reconhecivel."""
    g = nova_grade()
    cx, cy = 16, 11
    rx, ry = p.get("rx", 7.0), p.get("ry", 7.0)
    _elipse(g, cx, cy, rx, ry, "B")
    for i in range(4):                       # topo afunilado do manto
        _coluna(g, cx - 2 + i, cy - ry - 1.5, cy - ry, "B")

    # Bracos em LEQUE: cada um abre pro seu lado conforme desce (quanto maior o
    # t, maior o afastamento). A 1a versao mandava metade dos bracos pra
    # esquerda e metade pra direita com a mesma curva - eles se fundiam em dois
    # blocos e o kraken virava um caranguejo.
    bracos = p.get("bracos", 6)
    for i in range(bracos):
        f = (i / (bracos - 1)) - 0.5                 # -0.5 (esq) .. +0.5 (dir)
        comp = 13 - int(5 * abs(f))                  # os das pontas sao curtos
        for j in range(comp):
            t = j / comp
            x = cx + f * (rx * 1.5) * (1.0 + 1.35 * t) + math.sin(t * 4 + i) * 0.8
            y = cy + ry * 0.62 + j * 1.05
            # braco grosso de proposito: com 1px de raio o contorno automatico
            # comia o miolo e os oito bracos viravam poeira escura no slot.
            r = 1.9 * (1.0 - 0.55 * t)
            _coluna(g, x, y - r, y + r, "T")

    contorna(g)
    zonear(g)
    olho(g, cx - 5, cy + 1)
    olho(g, cx + 3, cy + 1)
    return g


def forma_quelonio(p, v):
    """Tartaruga-cascuda: casco em domo + plastrao + 4 patas + cabeca e cauda.
    Tem 'peixe' na lista mas nunca teve nada de peixe."""
    g = nova_grade()
    cx, cy = 16, 17
    rx, ry = 9.0, 6.5
    _elipse(g, cx, cy, rx, ry, "B", y_max=cy)             # domo do casco
    for y in range(cy + 1, cy + 4):                       # plastrao reto
        for x in range(cx - int(rx * 0.92), cx + int(rx * 0.92) + 1):
            _p(g, x, y, "B")
    # placas do casco: linhas escuras que fazem o domo ler como CASCO
    for x in range(cx - 7, cx + 8, 4):
        for y in range(cy - 6, cy + 1):
            if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 0.85:
                _p(g, x, y, "f")
    for x in range(cx - 8, cx + 9):
        if ((x - cx) / rx) ** 2 + ((cy - 3.0 - cy) / ry) ** 2 <= 0.9:
            _p(g, x, cy - 3, "f")
    # cabeca (esquerda) e cauda (direita)
    _elipse(g, cx - rx - 2, cy - 1, 3.0, 2.6, "B")
    for i in range(3):
        _p(g, cx + rx + i, cy, "B")
    # patas / nadadeiras
    for sx in (cx - 7, cx + 4):
        for dx in range(4):
            for dy in range(3):
                _p(g, sx + dx, cy + 3 + dy - (dx // 3), "f")
    contorna(g)
    zonear(g)
    olho(g, cx - rx - 3, cy - 2)
    return g


def forma_anfibio(p, v):
    """Sapo-touro: corpo baixo e largo, olhos esbugalhados EM CIMA da cabeca,
    pernas traseiras dobradas. Le' como sapo mesmo em 32px."""
    g = nova_grade()
    cx, cy = 16, 19
    _elipse(g, cx, cy, 9.0, 5.5, "B")
    _elipse(g, cx - 6, cy - 4, 5.5, 3.8, "B")             # cabeca
    for sx, sy in ((cx - 9, cy - 7), (cx - 3, cy - 8)):   # bolhas dos olhos
        _elipse(g, sx, sy, 2.4, 2.2, "B")
    # Pernas em 'B' (carne, nao nadadeira): assim o contorno automatico as
    # recorta e a perna dobrada aparece de verdade - com 'f' elas sumiam
    # dentro da silhueta e o sapo virava uma bolha marrom.
    _elipse(g, cx + 6, cy + 1, 3.6, 3.0, "B")             # coxa
    for dx in range(6):                                   # canela + pe
        _coluna(g, cx + 4 + dx, cy + 4, cy + 5, "B")
    for dx in range(5):
        _coluna(g, cx + 7 + dx, cy + 5, cy + 6, "B")
    for dx in range(4):                                   # pata dianteira
        _coluna(g, cx - 9 + dx, cy + 4, cy + 5, "B")
    contorna(g)
    zonear(g)
    olho(g, cx - 10, cy - 8)
    olho(g, cx - 4, cy - 9)
    return g


def forma_raia(p, v):
    """Arraia-de-rio: disco losangular achatado + chicote com ferrao.
    Nada de perfil lateral - a arraia so' e' arraia vista DE CIMA."""
    g = nova_grade()
    cx, cy = 13, 16
    rx, ry = 10.0, 9.0
    for y in range(cy - int(ry), cy + int(ry) + 1):
        f = 1.0 - abs(y - cy) / ry
        w = rx * (f ** 0.55)
        if w >= 0.5:
            for x in range(int(round(cx - w)), int(round(cx + w)) + 1):
                _p(g, x, y, "B")
    for i in range(13):                                   # chicote
        x = cx + rx * 0.72 + i
        r = 2.0 - i * 0.11
        _coluna(g, x, cy - r, cy + r, "T")
    for i in range(4):                                    # ferrao
        _p(g, cx + rx * 0.72 + 6 + i, cy - 2 - i * 0.4, "f")
    contorna(g)
    zonear(g)
    olho(g, cx - 5, cy - 3)
    olho(g, cx - 5, cy + 2)
    return g


def forma_golfinho(p, v):
    """Boto (e narval): corpo fusiforme com BICO, dorsal falcada e cauda
    HORIZONTAL. A cauda deitada e' o que o olho usa pra dizer 'mamifero'."""
    g = nova_grade()
    x0, x1 = p.get("x0", 6), p.get("x1", 22)
    cy, hmax = 15, p.get("hmax", 4.6)
    L = x1 - x0
    topos, bases = {}, {}
    for x in range(x0, x1 + 1):
        t = (x - x0) / L
        h = max(1.0, hmax * _perfil(t, 0.34, 0.45, 0.95))
        _coluna(g, x, cy - h, cy + h, "B")
        topos[x], bases[x] = int(round(cy - h)), int(round(cy + h))
    _boca(g, p, x0, cy, hmax)
    # dorsal falcada (curva pra tras)
    dx0 = int(x0 + L * 0.40)
    for i in range(5):
        for k in range(1, 4 - abs(i - 2) // 2):
            _p(g, dx0 + i, topos.get(dx0 + i, cy) - k - (i // 3), "f")
    # nadadeira peitoral apontando pra baixo-tras
    for i in range(4):
        _p(g, x0 + 5 + i, cy + hmax * 0.8 + i * 0.8, "f")
        _p(g, x0 + 6 + i, cy + hmax * 0.8 + i * 0.8, "f")
    # cauda horizontal (fluke): elipse ACHATADA com entalhe atras. A cauda
    # deitada (e nao em pe como a de peixe) e' o sinal de "mamifero aquatico".
    _elipse(g, x1 + 3, cy, 3.6, 2.4, "T")
    for dy in (-1, 0, 1):                                # entalhe central
        _p(g, x1 + 6, cy + dy, ".")
    _p(g, x1 + 5, cy, ".")
    if p.get("presa"):                                   # narval: a presa
        for i in range(1, 12):
            _p(g, x0 - 5 - i, cy - 3, "B")
            if i < 8:
                _p(g, x0 - 5 - i, cy - 2, "B")
    contorna(g)
    zonear(g)
    olho(g, x0 + 3, cy - 2)
    return g


def forma_sereia(p, v):
    """Iara: folclore brasileiro. Cabeca com cabelo longo, torso e bracos, e do
    quadril pra baixo cauda de peixe curvando ate a barbatana."""
    g = nova_grade()
    cx = 14
    _elipse(g, cx, 6, 3.2, 3.4, "B")                      # cabeca
    for y in range(3, 16):                                # cabelo (vira dorso)
        larg = 5 + (y - 3) // 3
        _p(g, cx - larg, y, "f")
        _p(g, cx - larg + 1, y, "f")
        _p(g, cx + larg - 1, y, "f")
    for y in range(10, 17):                               # torso
        w = 3.4 - (y - 10) * 0.12
        for x in range(int(cx - w), int(cx + w) + 1):
            _p(g, x, y, "B")
    for i in range(6):                                    # bracos
        _p(g, cx - 4 - i * 0.5, 11 + i, "f")
        _p(g, cx + 4 + i * 0.5, 11 + i, "f")
    for i in range(11):                                   # cauda curvando
        y = 17 + i
        xo = cx + 2.6 * math.sin(math.pi * i / 13)
        w = 3.1 - i * 0.19
        _coluna(g, xo, y, y, "B")
        for dx in range(int(-w), int(w) + 1):
            _p(g, xo + dx, y, "B")
    for i in range(4):                                    # barbatana caudal
        _coluna(g, cx + 1 - 3 + i * 2, 27 + i * 0.2, 29 + i * 0.2, "T")
        _p(g, cx - 3 + i * 2, 30, "T")
    contorna(g)
    zonear(g)
    olho(g, cx - 1, 5)
    return g


def forma_lodo(p, v):
    """Lodo-ancestral: bolha viscosa com pingos escorrendo. Nao e' bicho."""
    g = nova_grade()
    cx, cy = 16, 15
    _elipse(g, cx, cy, 8.5, 7.0, "B")
    for x, alt in ((cx - 6, 6), (cx - 1, 9), (cx + 5, 5), (cx + 8, 3)):
        for i in range(alt):
            _coluna(g, x, cy + 6 + i, cy + 6 + i, "B")
            _p(g, x + 1, cy + 6 + i, "B" if i < alt - 2 else ".")
    for x in range(cx - 7, cx + 8, 3):                    # bolhas internas
        _p(g, x, cy - 4, "f")
    contorna(g)
    zonear(g)
    return g


def forma_cristal(p, v):
    """Cristal-de-gelo: cacho de tres prismas. Achado, nao criatura."""
    g = nova_grade()
    for bx, base, alt, larg in ((11, 26, 14, 3), (16, 28, 20, 4), (22, 25, 11, 2)):
        for i in range(alt):
            y = base - i
            w = larg * (1.0 - i / alt) ** 0.5
            for x in range(int(round(bx - w)), int(round(bx + w)) + 1):
                _p(g, x, y, "B")
        _p(g, bx, base - alt, "w")
    contorna(g)
    zonear(g)
    return g


def forma_tesouro(p, v):
    """Tesouro-afundado: bau com tampa abaulada, fecho e moedas saindo."""
    g = nova_grade()
    for y in range(16, 26):
        for x in range(6, 27):
            _p(g, x, y, "B")
    _elipse(g, 16, 16, 10.5, 5.5, "B", y_max=16)
    for x in range(6, 27):                                # aro da tampa
        _p(g, x, 16, "f")
    for y in range(18, 23):                               # fecho
        for x in range(14, 19):
            _p(g, x, y, "f")
    for x, y in ((9, 13), (12, 11), (20, 11), (23, 13)):  # moedas escapando
        _p(g, x, y, "w")
        _p(g, x + 1, y, "w")
    contorna(g)
    zonear(g)
    return g


def forma_bota(p, v):
    """Bota velha: cano em pe + pe pra frente. O item mais honesto do pack."""
    g = nova_grade()
    for y in range(5, 22):                                # cano
        for x in range(11, 20):
            _p(g, x, y, "B")
    for y in range(22, 28):                               # pe
        for x in range(5, 20):
            _p(g, x, y, "B")
    for x in range(5, 21):                                # solado
        _p(g, x, 28, "f")
        _p(g, x, 27, "f")
    for y in range(7, 18, 3):                             # cadarcos
        for x in range(12, 19, 2):
            _p(g, x, y, "f")
    contorna(g)
    zonear(g)
    return g


def forma_cipo(p, v):
    """Cipo-afogado: trepadeira serpenteante COM FOLHAS - sem cabeca e sem
    olho, e' o que o separa da enguia, que usa a mesma onda."""
    g = nova_grade()
    x0, x1, cy = 2, 29, 16
    L = x1 - x0
    for x in range(x0, x1 + 1):
        t = (x - x0) / L
        y = cy + 7.5 * math.sin(2 * math.pi * 1.35 * t)
        y2 = cy + 7.5 * math.sin(2 * math.pi * 1.35 * min(t + 1 / L, 1))
        _coluna(g, x, min(y, y2) - 1.1, max(y, y2) + 1.1, "B")
    for i, x in enumerate(range(x0 + 3, x1 - 1, 4)):      # folhas
        t = (x - x0) / L
        y = cy + 7.5 * math.sin(2 * math.pi * 1.35 * t)
        lado = -1 if i % 2 == 0 else 1
        for j in range(1, 4):
            _p(g, x + j - 1, y + lado * (2 + j), "f")
            _p(g, x + j, y + lado * (2 + j), "f")
    contorna(g)
    zonear(g)
    return g


ARQUETIPOS = {
    "peixe": forma_peixe,
    "serpente": forma_serpente,
    "cefalopode": forma_cefalopode,
    "quelonio": forma_quelonio,
    "anfibio": forma_anfibio,
    "raia": forma_raia,
    "golfinho": forma_golfinho,
    "sereia": forma_sereia,
    "lodo": forma_lodo,
    "cristal": forma_cristal,
    "tesouro": forma_tesouro,
    "bota": forma_bota,
    "cipo": forma_cipo,
}


# ====================================================== CATALOGO DE FORMAS ===
# id do config.yml -> (arquetipo, parametros).
# Proporcoes escolhidas pelo bicho REAL: hmax alto = corpo alto/robusto,
# x0..x1 longo = corpo alongado, 'cauda'/'dorsal' fixos quando a especie exige.
def P(arq, **kw):
    return (arq, kw)


CATALOGO_FORMA = {
    # ---- default (comuns) ----
    "sardinha": P("peixe", hmax=3.4, x0=2, x1=23, tp=0.42, cauda="bifurcada",
                  dorsal="baixa", thmax=4.2),
    "salmao": P("peixe", hmax=5.0, x0=2, x1=23, tp=0.44, cauda="bifurcada"),
    "robalo": P("peixe", hmax=5.2, x0=3, x1=22, tp=0.38, dorsal="espinhosa"),
    "peixe-lendario": P("peixe", hmax=7.0, x0=4, x1=21, tp=0.40, cauda="leque",
                        dorsal="alta", thmax=8.5),
    "carpa": P("peixe", hmax=7.2, x0=4, x1=21, tp=0.46, cauda="leque",
               boca="bigode"),
    "perca-gigante": P("peixe", hmax=7.4, x0=3, x1=22, tp=0.36,
                       dorsal="espinhosa", cauda="leque"),
    "bota-velha": P("bota"),

    # ---- ocean ----
    "atum": P("peixe", hmax=6.2, x0=3, x1=21, tp=0.36, a=0.42, b=1.35,
              cauda="lanceta", dorsal="baixa", thmax=8.0, tlen=7),
    "garoupa": P("peixe", hmax=7.6, x0=3, x1=22, tp=0.30, a=0.40,
                 cauda="leque", boca="grande"),
    "cavala-real": P("peixe", hmax=4.2, x0=2, x1=23, tp=0.38, a=0.45, b=1.3,
                     cauda="lanceta", dorsal="baixa"),
    "tubarao-abissal": P("peixe", hmax=6.0, x0=2, x1=22, tp=0.33, a=0.5, b=1.1,
                         cauda="lanceta", dorsal="alta", thmax=9.0, tlen=7,
                         boca="dentes", olho_dx=4),
    "sardinha-prateada": P("peixe", hmax=3.2, x0=2, x1=24, tp=0.44,
                           cauda="bifurcada", dorsal="baixa"),
    "espadarte": P("peixe", hmax=5.0, x0=11, x1=25, tp=0.34, a=0.45, b=1.2,
                   cauda="lanceta", dorsal="alta", boca="espada", thmax=7.0),
    "tesouro-afundado": P("tesouro"),

    # ---- river ----
    "truta": P("peixe", hmax=4.8, x0=3, x1=23, tp=0.42, cauda="bifurcada"),
    "piapara": P("peixe", hmax=6.0, x0=3, x1=22, tp=0.40, cauda="bifurcada"),
    "dourado": P("peixe", hmax=7.0, x0=3, x1=22, tp=0.28, a=0.35,
                 cauda="bifurcada", dorsal="alta"),
    "bagre-gigante": P("peixe", hmax=5.6, x0=4, x1=24, tp=0.22, a=0.30, b=1.0,
                       cauda="leque", dorsal="baixa", boca="bigode",
                       olho_dx=2, olho_dy=2),
    "carpa-do-rio": P("peixe", hmax=7.0, x0=4, x1=21, tp=0.46, cauda="leque",
                      boca="bigode"),
    # Pirarucu: longo, cilindrico, cauda arredondada bem atras e escamas
    # grandes no terco final - por isso o padrao de losango e' FORCADO.
    "pirarucu": P("peixe", hmax=5.4, x0=1, x1=25, tp=0.55, a=0.35, b=0.55,
                  cauda="leque", dorsal="baixa", dorsal_ini=0.70,
                  dorsal_fim=0.92, tlen=4, thmax=6.5, padrao="diamante"),
    "bota-velha-rio": P("bota"),

    # ---- swamp ----
    "perca-do-pantano": P("peixe", hmax=6.4, x0=3, x1=22, tp=0.36,
                          dorsal="espinhosa"),
    "sapo-touro": P("anfibio"),
    "piraiba": P("peixe", hmax=6.2, x0=4, x1=25, tp=0.20, a=0.28, b=1.0,
                 cauda="bifurcada", dorsal="baixa", boca="bigode",
                 olho_dx=2, olho_dy=2),
    "lodo-ancestral": P("lodo"),
    "enguia-do-lodo": P("serpente", amp=5.5, ondas=1.5, espessura=2.0,
                        barbatana=True),
    "tartaruga-cascuda": P("quelonio"),
    "bota-podre": P("bota"),

    # ---- frozen ----
    "bacalhau-congelado": P("peixe", hmax=5.4, x0=3, x1=23, tp=0.30, a=0.40,
                            cauda="leque", dorsal="baixa", boca="bigode"),
    "salmao-artico": P("peixe", hmax=5.0, x0=2, x1=23, tp=0.44,
                       cauda="bifurcada"),
    "cristal-de-gelo": P("cristal"),
    # Linguado: disco achatado e OS DOIS OLHOS do mesmo lado - a excentricidade
    # real do bicho vira a leitura do item.
    "linguado-polar": P("peixe", hmax=9.0, x0=4, x1=22, tp=0.48, a=0.85, b=0.85,
                        cauda="leque", dorsal="baixa", dorsal_ini=0.12,
                        dorsal_fim=0.90, tlen=4, thmax=8.0, olho_dx=4,
                        olho_dy=4, olho_extra=(7, -6)),
    "narval-fantasma": P("golfinho", presa=True, boca="bico", hmax=4.4),
    "arenque-polar": P("peixe", hmax=3.6, x0=2, x1=24, tp=0.45,
                       cauda="bifurcada", dorsal="baixa"),
    "esturjao-glacial": P("peixe", hmax=4.6, x0=1, x1=24, tp=0.26, a=0.30,
                          b=1.25, cauda="lanceta", dorsal="espinhosa",
                          thmax=7.0, padrao="diamante"),

    # ---- jungle ----
    # Piranha: corpo curto e ALTO, testa em degrau, mandibula com dentes.
    "piranha": P("peixe", hmax=8.6, x0=5, x1=21, tp=0.26, a=0.32, b=0.95,
                 cauda="bifurcada", dorsal="alta", boca="dentes",
                 olho_dx=2, olho_dy=3, thmax=7.0),
    "acara-disco": P("peixe", hmax=9.6, x0=5, x1=20, tp=0.50, a=0.75, b=0.75,
                     cauda="leque", dorsal="alta", dorsal_ini=0.15,
                     dorsal_fim=0.85, tlen=4, thmax=7.0),
    "tucunare": P("peixe", hmax=5.6, x0=2, x1=23, tp=0.34, a=0.42,
                  dorsal="espinhosa", cauda="leque"),
    "cipo-afogado": P("cipo"),
    "arraia-de-rio": P("raia"),
    "matrinxa-ancestral": P("peixe", hmax=6.6, x0=3, x1=22, tp=0.40,
                            cauda="bifurcada"),

    # ---- bosses ----
    "kraken": P("cefalopode", bracos=7),
    "boto": P("golfinho", boca="bico", hmax=5.2, x0=6, x1=21),
    "iara": P("sereia"),
    "leviata": P("serpente", amp=6.5, ondas=1.15, espessura=3.4, espinhos=True,
                 mandibula=True),
    "cobra-grande": P("serpente", amp=7.0, ondas=1.85, espessura=2.8,
                      espinhos=True),
    "serpente-abissal": P("serpente", amp=6.0, ondas=2.25, espessura=1.9,
                          fase=0.6),
}


# ----------------------------------------------------------------- pintura --
def grade(especie_id, v):
    """Silhueta 32x32 da especie: arquetipo + parametros do catalogo."""
    arq, params = CATALOGO_FORMA[especie_id]
    g = ARQUETIPOS[arq](params, v)
    extra = params.get("olho_extra")
    if extra:                                # linguado: segundo olho do lado
        olho(g, params.get("x0", 3) + extra[0], 16 + extra[1])
    return g


def pinta_peixe(pal, v, especie_id, boss=False):
    """Desenha a especie 32x32: forma do arquetipo + mascara + padrao + brilho."""
    g = grade(especie_id, v)
    _, params = CATALOGO_FORMA[especie_id]
    padrao = params.get("padrao", v["padrao"])
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    px = img.load()
    for y, linha in enumerate(g):
        for x, ch in enumerate(linha):
            if ch == ".":
                continue
            tom, aceita_mascara = ZONAS[ch]
            i = RAMPA.index(tom)
            if aceita_mascara:
                m = int(MASCARA_ESCAMA[y // 2][x // 2])
                if m >= MASCARA_CLARO:
                    i += 1
                elif m <= MASCARA_ESCURO:
                    i -= 1
            if boss and ch in ZONAS_CORPO:
                mb = int(MASCARA_BOSS[y // 2][x // 2])
                if mb >= BOSS_CLARO:
                    i += 1
                elif mb <= BOSS_ESCURO:
                    i -= 1
            if ch in ZONAS_CORPO:
                i += _delta_padrao(padrao, x, y, v["semente"])
            i = max(0, min(len(RAMPA) - 1, i))
            px[x, y] = T.rgb(pal[RAMPA[i]])
    # brilho especular por ultimo: e' o que da' o "molhado" no slot.
    cor_brilho = T.mistura(pal["L"], "#ffffff", 0.55)
    for (fy, fx) in _pontos_brilho(g, v["brilho"]):
        px[fx, fy] = cor_brilho
    return img


def _pontos_brilho(g, altura):
    """Acha 3 pixels de carne na faixa escolhida. Com 13 formas diferentes nao
    da' mais pra cravar coordenada fixa: o brilho e' procurado dentro do corpo,
    senao caia no vazio em metade dos itens."""
    carne = [(y, x) for y in range(SIZE) for x in range(SIZE)
             if g[y][x] in ZONAS_CORPO]
    if not carne:
        return []
    ys = [c[0] for c in carne]
    y0, y1 = min(ys), max(ys)
    faixa = {"alto": 0.28, "meio": 0.48, "baixo": 0.68}[altura]
    alvo = y0 + (y1 - y0) * faixa
    linha = [c for c in carne if abs(c[0] - alvo) <= 1]
    if not linha:
        return []
    linha.sort(key=lambda c: c[1])
    corte = linha[:max(1, len(linha) // 3)]
    return corte[:3]


def modelo_plano(nome):
    """Item 2D vanilla: uma camada, sem elements nem display customizado."""
    return {
        "parent": "minecraft:item/generated",
        "textures": {"layer0": f"{T.NS}:item/{nome}"},
    }


# ---------------------------------------------------------------- catalogo --
# Espelho de CatchCraft/src/main/resources/config.yml -> categories.<id>.fish.
# A categoria "default" nao tem lista de biomas: e' o fallback de qualquer
# bioma que nao caia em ocean/river/swamp/frozen/jungle.
ESPECIES = {
    "default": ["sardinha", "salmao", "bota-velha", "robalo", "peixe-lendario",
                "carpa", "perca-gigante"],
    "ocean": ["atum", "garoupa", "tesouro-afundado", "cavala-real",
              "tubarao-abissal", "sardinha-prateada", "espadarte"],
    "river": ["truta", "bota-velha-rio", "piapara", "dourado", "bagre-gigante",
              "carpa-do-rio", "pirarucu"],
    "swamp": ["perca-do-pantano", "sapo-touro", "bota-podre", "piraiba",
              "lodo-ancestral", "enguia-do-lodo", "tartaruga-cascuda"],
    "frozen": ["bacalhau-congelado", "salmao-artico", "cristal-de-gelo",
               "linguado-polar", "narval-fantasma", "arenque-polar",
               "esturjao-glacial"],
    "jungle": ["piranha", "acara-disco", "tucunare", "cipo-afogado",
               "arraia-de-rio", "matrinxa-ancestral"],
}

# bossfish.yml: um boss por cardume. Usam a paleta PROPRIA do boss (a mesma do
# trofeu dele), nao a do cardume - e' o que os separa da cardumada.
BOSSES = {
    "ocean": "kraken", "river": "boto", "swamp": "iara",
    "frozen": "leviata", "jungle": "cobra-grande",
    "default": "serpente-abissal",
}


def catalogo_peixes():
    """(nome, imagem, rotulo) de cada especie + cada boss."""
    itens = []
    for cardume in T.CARDUMES:
        # "default" usa uma paleta so' dos peixes (prata-azulado), separada da
        # do trofeu de Peixedex (que continua cinza) - ver T.PALETA_PEIXE_DEFAULT.
        pal = T.PALETA_PEIXE_DEFAULT if cardume == "default" else T.PALETAS[f"peixedex-{cardume}"]
        for especie in ESPECIES[cardume]:
            itens.append((f"peixe_{especie}",
                          pinta_peixe(pal, variacao(especie), especie),
                          especie))
    for cardume, boss in BOSSES.items():
        itens.append((f"peixe_{boss}",
                      pinta_peixe(T.PALETAS[boss], variacao(boss), boss,
                                  boss=True),
                      boss + "*"))
    return itens


# ----------------------------------------------------------------- preview --
def folha_peixes(itens):
    """Folha de contato ampliada: o peixe 32x32 nao se le' em tamanho real."""
    cols, cel, zoom = 8, 140, 4
    linhas = (len(itens) + cols - 1) // cols
    sheet = Image.new("RGBA", (cel * cols, (cel + 18) * linhas), (30, 32, 38, 255))
    draw = ImageDraw.Draw(sheet)
    fonte = ImageFont.load_default()
    for i, (nome, img, rotulo) in enumerate(itens):
        cx, cy = (i % cols) * cel, (i // cols) * (cel + 18)
        grande = img.resize((SIZE * zoom, SIZE * zoom), Image.NEAREST)
        sheet.alpha_composite(grande, (cx + (cel - SIZE * zoom) // 2, cy + 6))
        draw.text((cx + 6, cy + cel + 2), rotulo[:18], font=fonte,
                  fill=(225, 227, 233, 255))
    sheet.save(os.path.join(T.PREVIEW_DIR, "peixes.png"))


def limpa_antigos():
    """Apaga peixe_*.png/json de rodadas antigas, senao arquivos de catalogos
    velhos ficam de carona dentro do zip."""
    for pasta, ext in ((T.TEX_DIR, ".png"), (T.MODEL_DIR, ".json"),
                       (T.ITEM_DIR, ".json")):
        if not os.path.isdir(pasta):
            continue
        for f in os.listdir(pasta):
            if f.startswith("peixe_") and f.endswith(ext):
                os.remove(os.path.join(pasta, f))


def gera(itens):
    """Escreve textura + modelo + item definition de cada peixe dentro de pack/."""
    limpa_antigos()
    for nome, img, _ in itens:
        img.save(os.path.join(T.TEX_DIR, nome + ".png"))
        T.escreve_json(os.path.join(T.MODEL_DIR, nome + ".json"), modelo_plano(nome))
        T.escreve_json(os.path.join(T.ITEM_DIR, nome + ".json"), {
            "model": {"type": "minecraft:model", "model": f"{T.NS}:item/{nome}"}
        })
    folha_peixes(itens)


def valida():
    for nome, arte in (("mascara", MASCARA_ESCAMA), ("boss", MASCARA_BOSS)):
        assert len(arte) == 16 and all(len(l) == 16 for l in arte), \
            f"{nome} fora de 16x16"
    ids = [i for c in ESPECIES.values() for i in c]
    assert len(ids) == len(set(ids)), "id de especie repetido"
    assert len(ids) == 41, f"esperava 41 especies no config.yml, achei {len(ids)}"
    todos = ids + list(BOSSES.values())
    faltando = [i for i in todos if i not in CATALOGO_FORMA]
    assert not faltando, f"especie sem forma no catalogo: {faltando}"
    sobrando = [i for i in CATALOGO_FORMA if i not in todos]
    assert not sobrando, f"forma para id inexistente: {sobrando}"
    for especie in todos:
        arq, params = CATALOGO_FORMA[especie]
        assert arq in ARQUETIPOS, f"{especie}: arquetipo '{arq}' nao existe"
        g = grade(especie, variacao(especie))
        assert len(g) == SIZE and all(len(l) == SIZE for l in g), \
            f"{especie}: grade fora de {SIZE}x{SIZE}"
        assert all(ch in ZONAS or ch == "." for l in g for ch in l), \
            f"{especie}: caractere sem zona"
        carne = sum(1 for l in g for ch in l if ch in ZONAS_CORPO)
        assert carne >= 25, f"{especie}: silhueta quase vazia ({carne}px de carne)"


if __name__ == "__main__":
    # Rodar isolado so' regenera os peixes; nao refaz o zip nem os trofeus.
    valida()
    for d in (T.TEX_DIR, T.MODEL_DIR, T.ITEM_DIR, T.PREVIEW_DIR):
        os.makedirs(d, exist_ok=True)
    itens = catalogo_peixes()
    gera(itens)
    print(f"{len(itens)} peixes gerados em", T.TEX_DIR)
