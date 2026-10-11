"""Run on the NVIDIA host before starting the queue. Does not download anything."""
import hashlib
import json
from pathlib import Path


def main():
    import torch
    from gpu_runtime import resolve_device
    resolve_device(torch, 'cuda')
    # Exercise a CUDA kernel, not only driver discovery.
    value = torch.ones((64, 64), device='cuda', dtype=torch.float16)
    assert (value @ value).float().mean().item() == 64
    torch.cuda.synchronize()
    root = Path(__file__).resolve().parent
    manifest = json.loads((root / 'models.lock.json').read_text())
    for model in manifest['models']:
        for item in model['files']:
            path = root / '.local/models' / model['name'] / item['path']
            if path.stat().st_size != item['size']:
                raise RuntimeError('Model size mismatch: ' + str(path))
            if item['sha256']:
                with path.open('rb') as stream:
                    if hashlib.file_digest(stream, 'sha256').hexdigest() != item['sha256']:
                        raise RuntimeError('Model checksum mismatch: ' + str(path))
    print(json.dumps({'device':torch.cuda.get_device_name(0), 'torch':torch.__version__,
                      'cuda':torch.version.cuda, 'vram_bytes':torch.cuda.get_device_properties(0).total_memory,
                      'models_verified':True}))


if __name__ == '__main__':
    main()
