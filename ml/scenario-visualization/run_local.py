"""Offline SDXL + IP-Adapter Plus Face experiment on CUDA or Apple GPUs.

The output is an illustration, never a health/appearance prediction.
No face recognition model, fine-tuning, upload, or persistent face embedding.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import resource
import time
from gpu_runtime import resolve_device, sample_memory as record_memory, write_progress

ROOT = Path(__file__).resolve().parent
os.environ["HF_HOME"] = str(ROOT / ".local/hf")
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"
os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"

LABEL = "AI-generated illustration - not a prediction of appearance or health."
DEFAULT_PROMPT = (
    "Photographic head and shoulders portrait of the person in the reference, "
    "natural skin texture, ordinary casual clothing, soft neutral daylight, "
    "a quiet everyday indoor setting, realistic facial proportions."
)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path,
                        default=ROOT / ".local/reference/astronaut.png")
    parser.add_argument("--crop", type=int, nargs=4, metavar=("LEFT", "TOP", "RIGHT", "BOTTOM"))
    parser.add_argument("--size", type=int, choices=(512, 768, 1024), default=512)
    parser.add_argument("--steps", type=int, default=20)
    parser.add_argument("--scale", type=float, default=0.7)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--prompt", default=DEFAULT_PROMPT)
    parser.add_argument("--device", choices=("auto", "cuda", "mps", "cpu"), default="auto")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--progress-file", type=Path)
    args = parser.parse_args()
    if not 1 <= args.steps <= 100:
        parser.error("--steps must be between 1 and 100")
    if not 0 <= args.scale <= 1:
        parser.error("--scale must be between 0 and 1")
    if not args.reference.is_file():
        parser.error("Reference image does not exist")
    return args


def main():
    args = parse_args()
    import numpy as np
    import torch
    from diffusers import StableDiffusionXLPipeline
    from PIL import Image, ImageDraw, ImageFont, ImageOps
    from transformers import CLIPVisionModelWithProjection

    args.device = resolve_device(torch, args.device)
    if args.output_dir is None:
        args.output_dir = ROOT / ".local/outputs" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    args.output_dir.mkdir(parents=True, exist_ok=False)
    dtype = torch.float32 if args.device == "cpu" else torch.float16
    started = time.perf_counter()
    stats = {
        "status": "running", "label": LABEL, "device": args.device,
        "platform": platform.platform(), "size": args.size,
        "steps": args.steps, "adapter_scale": args.scale, "seed": args.seed,
        "prompt": args.prompt, "reference_crop": args.crop,
        "reference_sha256": hashlib.sha256(args.reference.read_bytes()).hexdigest(),
        "models": json.loads((ROOT / "models.lock.json").read_text()),
        "versions": {n: importlib.metadata.version(n) for n in
                     ("torch", "diffusers", "transformers", "accelerate", "Pillow")},
        "sampled_mps_driver_peak_bytes": 0,
        "sampled_mps_tensor_peak_bytes": 0,
    }

    def sample_memory():
        record_memory(torch, args.device, stats)

    def on_step(pipe, step, timestep, kwargs):
        sample_memory()
        write_progress(args.progress_file, step + 1, pipe.num_timesteps)
        print(f"Denoising {step + 1}/{args.steps}", flush=True)
        return kwargs

    try:
        reference = ImageOps.exif_transpose(Image.open(args.reference)).convert("RGB")
        if args.crop:
            left, top, right, bottom = args.crop
            if not (0 <= left < right <= reference.width and 0 <= top < bottom <= reference.height):
                raise ValueError("Crop must be a nonempty rectangle inside the reference image")
            reference = reference.crop(args.crop)
        reference.save(args.output_dir / "reference.png")
        print("Loading image encoder and SDXL from local files...", flush=True)
        encoder = CLIPVisionModelWithProjection.from_pretrained(
            ROOT / ".local/models/adapter/models/image_encoder",
            torch_dtype=dtype, local_files_only=True, use_safetensors=True)
        pipe = StableDiffusionXLPipeline.from_pretrained(
            ROOT / ".local/models/sdxl", image_encoder=encoder,
            torch_dtype=dtype, variant="fp16", use_safetensors=True,
            local_files_only=True, add_watermarker=False)
        pipe.load_ip_adapter(
            str(ROOT / ".local/models/adapter"), subfolder="sdxl_models",
            weight_name="ip-adapter-plus-face_sdxl_vit-h.safetensors",
            image_encoder_folder=None, local_files_only=True)
        pipe.set_ip_adapter_scale(args.scale)
        pipe.enable_vae_slicing()
        pipe.enable_vae_tiling()
        # Preserve the adapter's attention processors. Replacing them with generic
        # attention slicing processors can discard image conditioning.
        pipe.to(args.device)
        sample_memory()
        stats["load_seconds"] = time.perf_counter() - started
        print(f"Loaded in {stats['load_seconds']:.1f}s; starting generation", flush=True)
        generation_start = time.perf_counter()
        with torch.inference_mode():
            result = pipe(
                prompt=args.prompt,
                negative_prompt="airbrushed skin, beauty filter, plastic skin, distorted face, illustration, painting, text",
                ip_adapter_image=reference, height=args.size, width=args.size,
                num_inference_steps=args.steps, guidance_scale=5.0,
                generator=torch.Generator(device="cpu").manual_seed(args.seed),
                callback_on_step_end=on_step,
            ).images[0]
        sample_memory()
        stats["generation_seconds"] = time.perf_counter() - generation_start
        pixels = np.asarray(result)
        stats["pixel_std"] = float(pixels.std())
        if stats["pixel_std"] < 1:
            raise RuntimeError("Output is nearly uniform; inspect numerical stability")
        # Burn in the disclosure so exported images retain their meaning.
        font = ImageFont.load_default(size=14)
        labeled = Image.new("RGB", (args.size, args.size + 60), "#17202a")
        labeled.paste(result, (0, 0))
        draw = ImageDraw.Draw(labeled)
        draw.text((12, args.size + 10), "AI-generated illustration", fill="white", font=font)
        draw.text((12, args.size + 32), "Not a prediction of appearance or health.", fill="white", font=font)
        labeled.save(args.output_dir / "illustration.png")
        comparison = Image.new("RGB", (args.size * 2, args.size + 90), "#17202a")
        comparison.paste(ImageOps.contain(reference, (args.size, args.size)), (0, 30))
        comparison.paste(labeled, (args.size, 30))
        draw = ImageDraw.Draw(comparison)
        draw.text((12, 8), "Reference photo", fill="white", font=font)
        draw.text((args.size + 12, 8), "Generated scenario (not an observed after)", fill="white", font=font)
        comparison.save(args.output_dir / "comparison.png")
        stats["status"] = "success"
    except Exception as exc:
        stats["status"] = "failed"
        stats["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        stats["total_seconds"] = time.perf_counter() - started
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        stats["peak_process_rss_bytes"] = peak if platform.system() == "Darwin" else peak * 1024
        (args.output_dir / "metrics.json").write_text(json.dumps(stats, indent=2) + "\n")
        print(json.dumps({k: v for k, v in stats.items() if k not in ("models", "prompt")}, indent=2), flush=True)
        print(f"Output: {args.output_dir}", flush=True)


if __name__ == "__main__":
    main()
