import unittest
import numpy as np
from PIL import Image
from face_regions import prepare_masks, composite_face


class FaceRegionTests(unittest.TestCase):
    def setUp(self):
        self.original = Image.fromarray(np.random.default_rng(42).integers(0, 256, (80, 100, 3), dtype=np.uint8))
        self.face = (20, 10, 80, 70)

    def test_composite_preserves_every_pixel_outside_mask(self):
        hard, alpha = prepare_masks(self.original, self.face, edit_box=(30, 25, 45, 40), feather=4)
        edited = composite_face(self.original, Image.new("RGB", (512, 512), "white"), self.face, alpha)
        changed = np.any(np.asarray(edited) != np.asarray(self.original), axis=2)
        selected = np.asarray(hard) > 0
        self.assertTrue(changed[selected].any())
        self.assertFalse(changed[~selected].any())
        self.assertFalse((np.asarray(alpha)[~selected] > 0).any())

    def test_outside_face_selection_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "inside the selected face"):
            prepare_masks(self.original, self.face, edit_box=(5, 5, 30, 30))

    def test_empty_or_wrong_size_mask_is_rejected(self):
        for mask in (Image.new("L", self.original.size), Image.new("L", (10, 10), 255)):
            with self.assertRaises(ValueError):
                prepare_masks(self.original, self.face, mask=mask)

    def test_invalid_face_box_is_rejected(self):
        for box in ((-1, 0, 60, 60), (20, 10, 80, 60), (20, 10, 20, 10)):
            with self.assertRaises(ValueError):
                prepare_masks(self.original, box, edit_box=(30, 25, 45, 40))


if __name__ == "__main__":
    unittest.main()
