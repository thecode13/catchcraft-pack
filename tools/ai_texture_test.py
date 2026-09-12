"""Teste do modelo anjoismysign/minecraft-item-16px para gerar sprite 16x16 de item.
Roda uma vez, salva o resultado em ai_output/, nao faz parte do pipeline de producao.
"""
from diffusers import StableDiffusionPipeline
import torch

MODEL_ID = "anjoismysign/minecraft-item-16px"
OUT_DIR = "ai_output"

import os
os.makedirs(OUT_DIR, exist_ok=True)

device = "cuda" if torch.cuda.is_available() else "cpu"
# GTX 16xx (1650/1660) tem bug conhecido: fp16 no UNet gera NaN -> imagem preta.
# Solucao: pipeline inteiro em fp32, com offload sequencial pra caber nos 4GB de VRAM.
dtype = torch.float32

import time

print(f"Carregando {MODEL_ID} em {device} ({dtype})...")
pipe = StableDiffusionPipeline.from_pretrained(MODEL_ID, torch_dtype=dtype)
pipe.enable_attention_slicing()
pipe.vae.enable_slicing()
if device == "cuda":
    pipe.enable_sequential_cpu_offload()
else:
    pipe = pipe.to(device)
print("Pipeline carregado.")

prompts = [
    "a leather fisherman satchel bag, item icon",
    "a magic fishing lure bait, glowing, item icon",
]

def progress(pipe, step, timestep, kwargs):
    print(f"  step {step}", flush=True)
    return kwargs

for i, prompt in enumerate(prompts):
    print(f"Gerando: {prompt}")
    t0 = time.time()
    image = pipe(
        prompt,
        num_inference_steps=15,
        guidance_scale=7.5,
        callback_on_step_end=progress,
    ).images[0]
    print(f"Levou {time.time()-t0:.1f}s")
    path = os.path.join(OUT_DIR, f"test_{i}_{prompt[:20].replace(' ', '_')}.png")
    image.save(path)
    print(f"Salvo em {path}")

print("Concluido.")
