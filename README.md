# CatchCraft — resource pack de troféus

Texturas dos troféus do CatchCraft. Toda a arte é **gerada por código**, não
desenhada à mão: a fonte da verdade é `tools/gerar_trofeus.py`.

## Regerar tudo

```
python tools/gerar_trofeus.py
```

Isso reescreve `pack/`, a folha de contato em `preview/contato.png` e o
`CatchCraftPack.zip`, e imprime o SHA-1 do zip.

> O SHA-1 **muda a cada geração**, mesmo sem alterar nenhuma cor — o zip guarda
> a data de modificação dos arquivos. Sempre que regerar, atualize o
> `resource-pack-sha1` do `server.properties`.

## Como mexer na arte

| Quero mudar | Onde |
|---|---|
| A cor de um troféu | `PALETAS` — 4 tons por troféu: contorno, escuro, médio, claro |
| O símbolo de um troféu | `EMBLEMAS` — grade ASCII 8×8 (`.` vazio, `g` claro, `G` médio, `o` contorno) |
| O formato da taça | `PERFIL_TACA` — para cada linha `y`, o intervalo `(x0, x1)` preenchido |
| O formato do livro do Peixedex | `PERFIL_TOMO` |
| A coroa do "Primeiro Domador" | `COROA` |

O sombreamento é automático: a função `preenche` detecta a borda de cada peça
(vira contorno) e clareia os 2 px da esquerda / escurece os 2 px da direita,
simulando luz vindo do alto-esquerdo. É o que dá unidade visual às 18 peças.

## O que tem no pack (18 peças)

- **6 troféus de boss** — taça na cor do boss, com emblema próprio.
- **6 troféus "Primeiro Domador"** — mesma taça em ouro, com coroa; o emblema
  mantém a cor do boss, então dá pra saber de qual boss é sem ler a lore.
- **6 troféus de Peixedex completo** — silhueta de livro, uma cor por cardume.

Tamanho total do zip: ~21 KB. Isso é o download inteiro do jogador.

## Instalar no servidor

1. Publique o zip numa Release deste repo (ele é público, então o download
   funciona sem autenticação — que é o que o cliente do Minecraft precisa):

```bash
gh release create v1.0.1 CatchCraftPack.zip --title "v1.0.1" --notes "..."
```

2. No `server.properties`:

```
resource-pack=https://github.com/thecode13/catchcraft-pack/releases/download/v1.0.0/CatchCraftPack.zip
resource-pack-sha1=218d01187b56806b08359504ad7a8971da578b3e
require-resource-pack=true
```

A URL aponta para uma **tag fixa**, de propósito: assim um pack novo não troca
o conteúdo debaixo de quem já baixou. Ao publicar uma versão nova, crie uma tag
nova e atualize URL **e** SHA-1 juntos.

3. Só então ligue `resource-pack.trophy-models: true` no `config.yml` do plugin.

**Por que `require-resource-pack=true` aqui.** O componente `item_model` aponta
para um modelo que só existe dentro do pack. Se o cliente não tiver o pack, ele
desenha o cubo roxo-e-preto de textura faltando — **não** o item vanilla. Ou
seja: com os modelos ligados, o pack deixa de ser opcional.

Se você preferir que o pack continue opcional, o caminho é manter
`trophy-models: false`: aí os troféus voltam ao visual vanilla para todo mundo.
Não existe meio-termo por jogador — o servidor não sabe quem aceitou o pack no
momento em que monta o item.

## O `pack.mcmeta` precisa de três campos

Acima do formato **64**, o jogo passou a **exigir** `min_format` e `max_format`.
Um `pack.mcmeta` só com `pack_format` é recusado com "Corrompido ou incompatível"
na tela de pacotes — foi exatamente o erro que apareceu em 2026-09-10:

```
JsonParseException: Pack declares support for version newer than 64,
but is missing mandatory fields min_format and max_format
```

O gerador já escreve os três. `pack_format` fica só por compatibilidade com
clientes antigos, que ignoram os outros dois.

## De onde sai o `PACK_FORMAT`

Está em **88**, confirmado para **MC 26.2** (a versão do servidor em 2026-09-10).

Esse número nunca deve ser chutado. Ele é declarado pelo próprio jogo, em
`version.json` dentro do jar vanilla que o Paper baixa:

```bash
python -c "import zipfile,json;print(json.loads(zipfile.ZipFile('cache/mojang_26.2.jar').read('version.json'))['pack_version'])"
```

O campo é `pack_version.resource_major`. Rode isso na pasta do servidor sempre
que o Minecraft subir de versão e atualize `PACK_FORMAT` no gerador.

## Ligação com o plugin

O pack sozinho não faz nada. O plugin precisa marcar cada troféu com o modelo
correspondente, em `FishingListener.giveBossTrophy` e
`PeixedexRewards.giveCardumeTrophy`:

```java
meta.setItemModel(new NamespacedKey("catchcraft", "trofeu_" + boss.id()));
```

Chaves disponíveis: `trofeu_<boss>`, `trofeu_ouro_<boss>`,
`trofeu_peixedex_<cardume>`.
