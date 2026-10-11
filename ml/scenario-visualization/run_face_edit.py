"""Edit a selected face region locally, preserving all pixels outside its mask."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from run_local import ROOT, LABEL  # Also configures offline inference.
from face_regions import prepare_masks, composite_face
from gpu_runtime import resolve_device, sample_memory, write_progress


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", type=Path, default=ROOT / ".local/reference/astronaut.png")
    parser.add_argument("--face-box", required=True, type=int, nargs=4)
    region = parser.add_mutually_exclusive_group(required=True)
    region.add_argument("--edit-box", type=int, nargs=4, help="Ellipse inside LEFT TOP RIGHT BOTTOM")
    region.add_argument("--mask", type=Path, help="Original-size mask: black preserves, white edits")
    parser.add_argument("--strength", type=float, default=0.25)
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--size", choices=(512, 768), type=int, default=512)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--finish", choices=("original", "soft-light"), default="original")
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument("--device", choices=("auto", "cuda", "mps"), default="auto")
    parser.add_argument("--progress-file", type=Path)
    parser.add_argument("--prompt", default="The same face and cheek, natural skin detail, same facial geometry, same expression, matching the original lighting and skin tone, realistic photograph")
    args = parser.parse_args()
    if not 0 < args.strength <= 0.5:
        parser.error("Use strength greater than 0 and at most 0.5 to limit changes")
    if not 1 <= args.steps <= 100 or int(args.steps * args.strength) < 1:
        parser.error("Use 1–100 steps and at least one effective denoising step")

    import numpy as np
    import torch
    from PIL import Image, ImageOps, ImageDraw, ImageFont
    from diffusers import StableDiffusionXLInpaintPipeline
    from transformers import CLIPVisionModelWithProjection

    original = ImageOps.exif_transpose(Image.open(args.reference)).convert("RGB")
    input_mask = Image.open(args.mask) if args.mask else None
    hard, alpha = prepare_masks(original, args.face_box, args.edit_box, input_mask)
    face = original.crop(args.face_box)
    device = resolve_device(torch, args.device)
    out = args.output_dir or ROOT / ".local/outputs" / datetime.now(timezone.utc).strftime("face-edit-%Y%m%dT%H%M%SZ")
    out.mkdir(parents=True, exist_ok=False)
    hard.save(out / "mask.png")
    alpha.save(out / "blend-mask.png")
    original.save(out / "reference.png")
    stats = {"device": device, "status": "running", "label": LABEL, "face_box": args.face_box,
             "edit_box": args.edit_box, "strength": args.strength, "steps": args.steps, "finish": args.finish,
             "effective_steps": 0, "size": args.size, "seed": args.seed,
             "prompt": args.prompt, "reference_sha256": hashlib.sha256(args.reference.read_bytes()).hexdigest(),
             "sampled_mps_driver_peak_bytes": 0}
    start = time.perf_counter()

    def memory():
        sample_memory(torch, device, stats)

    def on_step(pipe, step, timestep, kwargs):
        memory()
        stats["effective_steps"] += 1
        write_progress(args.progress_file, step + 1, pipe.num_timesteps)
        print(f"Face edit step {step + 1}", flush=True)
        return kwargs

    try:
        print("Loading local masked-edit pipeline...", flush=True)
        encoder = CLIPVisionModelWithProjection.from_pretrained(
            ROOT / ".local/models/adapter/models/image_encoder", torch_dtype=torch.float16,
            local_files_only=True, use_safetensors=True)
        pipe = StableDiffusionXLInpaintPipeline.from_pretrained(
            ROOT / ".local/models/sdxl", image_encoder=encoder, torch_dtype=torch.float16,
            variant="fp16", use_safetensors=True, local_files_only=True, add_watermarker=False)
        pipe.load_ip_adapter(str(ROOT / ".local/models/adapter"), subfolder="sdxl_models",
                             weight_name="ip-adapter-plus-face_sdxl_vit-h.safetensors",
                             image_encoder_folder=None, local_files_only=True)
        pipe.set_ip_adapter_scale(0.7)
        pipe.enable_vae_tiling()
        pipe.enable_vae_slicing()
        pipe.to(device)
        memory()
        stats["load_seconds"] = time.perf_counter() - start
        generation_start = time.perf_counter()
        with torch.inference_mode():
            generated = pipe(
                prompt=args.prompt, negative_prompt="different person, changed expression, plastic skin, beauty filter, distorted face, body, text",
                image=face.resize((args.size, args.size), Image.Resampling.LANCZOS),
                mask_image=hard.crop(args.face_box).resize((args.size, args.size), Image.Resampling.NEAREST),
                ip_adapter_image=face, strength=args.strength,
                height=args.size, width=args.size, num_inference_steps=args.steps,
                guidance_scale=3.0, generator=torch.Generator("cpu").manual_seed(args.seed),
                callback_on_step_end=on_step,
            ).images[0]
        memory()
        stats["generation_seconds"] = time.perf_counter() - generation_start
        if np.asarray(generated).std() < 1:
            raise RuntimeError("Generated crop is nearly uniform")
        if args.finish == "soft-light":
            # Artistic tone curve, not a physiological or product-efficacy model.
            values = np.asarray(generated).astype(np.float32) / 255
            generated = Image.fromarray(np.rint(np.clip(values + 0.04 * values * (1 - values), 0, 1) * 255).astype(np.uint8))
        result = composite_face(original, generated, args.face_box, alpha)
        changed = np.any(np.asarray(result) != np.asarray(original), axis=2)
        selected = np.asarray(hard) > 0
        stats["selected_pixels"] = int(selected.sum())
        stats["changed_pixels_inside_mask"] = int((changed & selected).sum())
        stats["changed_pixels_outside_mask"] = int((changed & ~selected).sum())
        assert stats["changed_pixels_outside_mask"] == 0
        # Keep exact-resolution content above a disclosure footer (no unlabeled export).
        font = ImageFont.load_default(size=14)
        labeled = Image.new("RGB", (original.width, original.height + 60), "#17202a")
        labeled.paste(result)
        draw = ImageDraw.Draw(labeled)
        draw.text((10, original.height + 8), "AI-edited face region - illustration only", fill="white", font=font)
        draw.text((10, original.height + 30), "Not a prediction of appearance or health.", fill="white", font=font)
        labeled.save(out / "illustration.png")
        # Preview only the face: no generated body or new framing.
        comparison = Image.new("RGB", (1024, 580), "#17202a")
        comparison.paste(face.resize((512, 512), Image.Resampling.LANCZOS), (0, 30))
        comparison.paste(result.crop(args.face_box).resize((512, 512), Image.Resampling.LANCZOS), (512, 30))
        draw = ImageDraw.Draw(comparison)
        draw.text((10, 8), "Original face crop", fill="white", font=font)
        draw.text((522, 8), "Only the selected face region edited", fill="white", font=font)
        draw.text((10, 552), LABEL, fill="white", font=font)
        comparison.save(out / "face-comparison.png")
        stats["status"] = "success"
    except Exception as exc:
        stats["status"] = "failed"
        stats["error"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        stats["total_seconds"] = time.perf_counter() - start
        (out / "metrics.json").write_text(json.dumps(stats, indent=2) + "\n")
        print(json.dumps(stats, indent=2), flush=True)
        print(f"Output: {out}", flush=True)


if __name__ == "__main__":
    main()
