"""Mask geometry and exact preservation outside the user-selected region."""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def validate_box(box, size):
    left, top, right, bottom = box
    if not (0 <= left < right <= size[0] and 0 <= top < bottom <= size[1]):
        raise ValueError("Selection must be nonempty and inside the original image")


def prepare_masks(original, face_box, edit_box=None, mask=None, feather=2):
    validate_box(face_box, original.size)
    if face_box[2] - face_box[0] != face_box[3] - face_box[1]:
        raise ValueError("For this prototype, --face-box must be square")
    if (edit_box is None) == (mask is None):
        raise ValueError("Provide exactly one edit box or mask")
    if feather < 0:
        raise ValueError("Feather radius must be nonnegative")
    if edit_box is not None:
        validate_box(edit_box, original.size)
        mask = Image.new("L", original.size, 0)
        left, top, right, bottom = edit_box
        ImageDraw.Draw(mask).ellipse((left, top, right - 1, bottom - 1), fill=255)
    else:
        if mask.size != original.size:
            raise ValueError("Mask must match the EXIF-oriented original's dimensions")
        mask = mask.convert("L")
    hard = np.asarray(mask) > 0
    face_allowed = np.zeros(hard.shape, dtype=bool)
    left, top, right, bottom = face_box
    face_allowed[top:bottom, left:right] = True
    if not hard.any():
        raise ValueError("Edit mask is empty")
    if (hard & ~face_allowed).any():
        raise ValueError("Edit mask must stay inside the selected face box")
    binary = Image.fromarray(hard.astype(np.uint8) * 255)
    soft = np.asarray(binary.filter(ImageFilter.GaussianBlur(feather))).copy()
    # Blurring must never expand the edited area beyond the selected mask.
    soft[~hard] = 0
    return binary, Image.fromarray(soft)


def composite_face(original, generated_crop, face_box, alpha):
    validate_box(face_box, original.size)
    if alpha.size != original.size:
        raise ValueError("Alpha dimensions must match the original")
    left, top, right, bottom = face_box
    canvas = original.copy()
    canvas.paste(generated_crop.resize((right - left, bottom - top), Image.Resampling.LANCZOS), (left, top))
    result = Image.composite(canvas, original, alpha)
    outside = np.asarray(alpha) == 0
    if not np.array_equal(np.asarray(result)[outside], np.asarray(original)[outside]):
        raise AssertionError("Pixels outside the edit mask changed")
    return result
