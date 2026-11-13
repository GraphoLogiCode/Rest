"""Small device boundary shared by the CLI runners; importable without torch."""
import json
from pathlib import Path


def resolve_device(torch, requested):
    if requested == "auto":
        if torch.cuda.is_available():
            return "cuda"
        if torch.backends.mps.is_available():
            return "mps"
        raise RuntimeError("No GPU available. Install CUDA PyTorch on an NVIDIA host, or use an Apple GPU.")
    if requested == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable. Check NVIDIA drivers, the CUDA PyTorch build, and container GPU access.")
    if requested == "mps" and not torch.backends.mps.is_available():
        raise RuntimeError("MPS unavailable; run on an Apple GPU outside the sandbox.")
    if requested not in {"cuda", "mps", "cpu"}:
        raise ValueError("Unsupported device")
    return requested


def sample_memory(torch, device, stats):
    if device == "cuda":
        torch.cuda.synchronize()
        stats["cuda_peak_allocated_bytes"] = torch.cuda.max_memory_allocated()
        stats["cuda_peak_reserved_bytes"] = torch.cuda.max_memory_reserved()
    elif device == "mps":
        torch.mps.synchronize()
        stats["sampled_mps_driver_peak_bytes"] = max(
            stats.get("sampled_mps_driver_peak_bytes", 0), torch.mps.driver_allocated_memory())
        stats["sampled_mps_tensor_peak_bytes"] = max(
            stats.get("sampled_mps_tensor_peak_bytes", 0), torch.mps.current_allocated_memory())


def write_progress(path, completed, total):
    """Atomic progress file; this measures denoising only, not load/export time."""
    if path is None:
        return
    path = Path(path)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"completedSteps": completed, "totalSteps": total}))
    temporary.replace(path)
