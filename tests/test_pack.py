"""Pack tests, in the project's canary tradition: the good pack MUST pass,
and deliberately law-breaking packs MUST fail the specific row they break.
A validator that never fails proves nothing (calibration canaries, same
philosophy as the DodgeBot MUST-FAIL wall pattern).

Run: python3 -m unittest discover tests
"""

from __future__ import annotations

import copy
import unittest

from forge import validate
from forge.build import build_pack


def _sheets_no_png(sheets):
    return {name: (w, h, px) for name, (w, h, px) in sheets.items()}


class PackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest, cls.sheets, cls.pngs = build_pack()

    # -- the real pack -------------------------------------------------------

    def test_pack_validates_green(self):
        report = validate.validate_pack(self.manifest, self.sheets)
        failing = [r["check"] for r in report["rows"] if not r["pass"]]
        self.assertEqual(failing, [], f"pack failed rows: {failing}")

    def test_build_is_deterministic(self):
        manifest2, _, pngs2 = build_pack()
        self.assertEqual(self.manifest, manifest2)
        self.assertEqual(self.pngs, pngs2)

    def test_every_frame_cell_sized(self):
        for key, fam in self.manifest["families"].items():
            w, h, _ = self.sheets[fam["image"]]
            self.assertEqual(h, fam["cellPx"], key)
            self.assertEqual(w, fam["cellPx"] * fam["frames"], key)

    # -- canaries: each one MUST fail its row --------------------------------

    def _row(self, report, check):
        return next(r for r in report["rows"] if r["check"] == check)

    def test_canary_friendly_wearing_the_signature_fails(self):
        # Relabel a hostile family as player: its bright rim must now fail
        # the friendly edge check (an accessibility treatment leaking onto
        # player shots would break Law 2).
        manifest = copy.deepcopy(self.manifest)
        manifest["families"]["husk_dart"]["role"] = "player"
        report = validate.validate_pack(manifest, self.sheets)
        self.assertFalse(self._row(report, "hostile-signature")["pass"])

    def test_canary_hostile_without_signature_fails(self):
        # Relabel a player family as hostile: no rim => signature row fails.
        manifest = copy.deepcopy(self.manifest)
        fam = manifest["families"]["wheelblade"]
        fam["role"] = "hostile"
        report = validate.validate_pack(manifest, self.sheets)
        self.assertFalse(self._row(report, "hostile-signature")["pass"])

    def test_canary_identical_hostile_silhouettes_fail(self):
        # Two hostile families sharing one sheet: IoU = 1.0 must fail even
        # with distinct declared classes (measurement, not self-description).
        manifest = copy.deepcopy(self.manifest)
        clone = copy.deepcopy(manifest["families"]["husk_dart"])
        clone["silhouette"] = "totally-different-honest"
        manifest["families"]["husk_dart_clone"] = clone
        report = validate.validate_pack(manifest, self.sheets)
        row = self._row(report, "silhouette-distinct")
        self.assertFalse(row["pass"])
        self.assertTrue(row["detail"]["classesUnique"])

    def test_canary_strobe_fails_photosensitivity(self):
        # Blow out every odd frame of an animated hostile family to white:
        # the per-frame luminance delta cap must trip.
        manifest = copy.deepcopy(self.manifest)
        sheets = _sheets_no_png(self.sheets)
        fam = manifest["families"]["ring_roundel"]
        w, h, px = sheets[fam["image"]]
        px = bytearray(px)
        for y in range(h):
            for x in range(w):
                if (x // fam["cellPx"]) % 2 == 1:
                    i = (y * w + x) * 4
                    if px[i + 3]:
                        px[i : i + 3] = b"\xff\xff\xff"
        sheets[fam["image"]] = (w, h, bytes(px))
        report = validate.validate_pack(manifest, sheets)
        self.assertFalse(self._row(report, "photosensitivity")["pass"])

    def test_canary_interior_partial_alpha_fails(self):
        # Half-transparent pixel at the CENTER of a big solid family: AA is
        # legal only hugging the outer boundary, so this must fail.
        manifest = copy.deepcopy(self.manifest)
        sheets = _sheets_no_png(self.sheets)
        fam = manifest["families"]["boulder"]
        w, h, px = sheets[fam["image"]]
        px = bytearray(px)
        cell = fam["cellPx"]
        px[((cell // 2) * w + cell // 2) * 4 + 3] = 128
        sheets[fam["image"]] = (w, h, bytes(px))
        report = validate.validate_pack(manifest, sheets)
        self.assertFalse(self._row(report, "alpha-hygiene")["pass"])

    def test_canary_roster_hole_fails(self):
        manifest = copy.deepcopy(self.manifest)
        manifest["families"]["lead_needle"]["consumers"] = []
        report = validate.validate_pack(manifest, self.sheets)
        self.assertFalse(self._row(report, "roster-coverage")["pass"])


if __name__ == "__main__":
    unittest.main()
