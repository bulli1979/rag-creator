from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "documentApi"))
from app.conversation_context import resolve_retrieval_context
from app.wavelength_reasoning import compare_wavelength


class FollowupContextTests(unittest.TestCase):
    history = [
        {"role": "user", "content": "what is NOTCAM?"},
        {"role": "assistant", "content": "NOTCam is an infrared instrument."},
    ]

    def test_original_followup_resolves_instrument(self):
        result = resolve_retrieval_context("can the instrument be used to observer at 500nm?", self.history)
        self.assertEqual(result.query, "can NOTCAM be used to observer at 500nm?")
        self.assertEqual(result.resolution, "inherited")

    def test_explicit_switch_overrides_history(self):
        result = resolve_retrieval_context("Can ALFOSC observe at 500nm?", self.history)
        self.assertEqual(result.instruments, frozenset({"ALFOSC"}))
        self.assertEqual(result.resolution, "explicit")

    def test_chained_followup_and_ellipsis(self):
        history = self.history + [{"role": "user", "content": "Can it observe at 500nm?"}]
        result = resolve_retrieval_context("What about 1000nm?", history)
        self.assertIn("NOTCAM", result.query)

    def test_ambiguous_subject_is_not_guessed(self):
        history = [{"role": "user", "content": "Compare NOTCAM and ALFOSC."}]
        self.assertEqual(resolve_retrieval_context("Can it observe at 500nm?", history).resolution, "ambiguous")

    def test_assistant_invention_is_not_used(self):
        history = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "NOTCAM"}]
        self.assertEqual(resolve_retrieval_context("Can the instrument observe at 500nm?", history).resolution, "unresolved")

    def test_new_unrelated_topic_stops_subject_inheritance(self):
        history = self.history + [{"role": "user", "content": "What is the weather?"}]
        self.assertEqual(resolve_retrieval_context("Can the instrument observe at 500nm?", history).resolution, "unresolved")
        self.assertEqual(resolve_retrieval_context("How is the weather?", self.history).resolution, "standalone")


class WavelengthReasoningTests(unittest.TestCase):
    def evidence(self, **updates):
        return [{"citationId": "D-aaaaaaaaaaaaaaaa-C0", "instrument": "NOTCAM",
                 "status": "active", "authority": "tier_2_reference",
                 "content": "NOTCam is a multi-mode instrument for use in the short-wave infrared region (0.8 - 2.5µm).",
                 **updates}]

    def test_original_comparison_is_derived_and_cited(self):
        result = compare_wavelength("can NOTCAM be used to observer at 500nm?", self.evidence())
        self.assertTrue(result.validation.answer.startswith("No. 500nm (= 0.5 µm) is below NOTCAM"))
        self.assertIn("[D-aaaaaaaaaaaaaaaa-C0]", result.validation.answer)
        self.assertEqual(result.derivation["relation"], "below")
        self.assertIn("0.8 - 2.5µm", result.derivation["quote"])

    def test_wrapped_overview_prose_keeps_instrument_subject(self):
        source = "NOTCam is a multi-mode instrument for use in the short-wave infrared\nregion of the electromagnetic spectrum (0.8 - 2.5µm). It has 1024 pixels."
        result = compare_wavelength("Can NOTCAM observe at 500nm?", self.evidence(content=source))
        self.assertEqual(result.derivation["relation"], "below")
        self.assertIsNotNone(compare_wavelength("NOTCAM: What wavelength range does the camera cover?", self.evidence(content=source)))

    def test_direct_range_question_uses_same_checked_source(self):
        for question in ("Which wavelength range does NOTCAM cover?", "What is NOTCAM's wavelength range?"):
            with self.subTest(question=question):
                result = compare_wavelength(question, self.evidence())
                self.assertIn("0.8–2.5 µm", result.validation.answer)
                self.assertEqual(result.derivation["relation"], "range")
                self.assertIsNone(result.derivation["requestedMicrometres"])

    def test_above_inside_and_boundaries(self):
        for quantity, relation in (("3000nm", "above"), ("1000nm", "within"),
                                   ("800nm", "within"), ("2500nm", "within"), ("0.5μm", "below")):
            with self.subTest(quantity=quantity):
                result = compare_wavelength(f"Can NOTCAM observe at {quantity}?", self.evidence())
                self.assertEqual(result.derivation["relation"], relation)
                if relation == "within":
                    self.assertIn("does not confirm", result.validation.answer)

    def test_mixed_and_spelled_source_units(self):
        for source in ("NOTCam covers wavelengths from 800 nm to 2.5 micrometres.",
                       "NOTCam covers wavelengths from 800–2500 nanometers.",
                       "NOTCam covers wavelengths from 0,8 to 2,5 μm."):
            with self.subTest(source=source):
                result = compare_wavelength("Can NOTCAM observe at 500nm?", self.evidence(content=source))
                self.assertEqual(result.derivation["relation"], "below")

    def test_other_instrument_uses_its_own_evidence(self):
        result = compare_wavelength("Can FIES observe at 500nm?", self.evidence(
            instrument="FIES", content="FIES covers wavelengths from 370 to 830 nm."))
        self.assertEqual(result.derivation["relation"], "within")
        self.assertIn("FIES", result.validation.answer)

    def test_landing_range_keeps_gap_free_and_extended_coverage_distinct(self):
        source=('FIES is a high-resolution spectrograph. The entire spectral range 390-810 nm is covered without gaps. '
                'Extended coverage up to 910 nm is available with minor inter-order wavelength gaps.')
        evidence=self.evidence(instrument='FIES',sourceRole='instrument_landing',content=source)
        result=compare_wavelength('What wavelength range does FIES cover?',evidence)
        self.assertIn('390-810 nm',result.validation.answer)
        self.assertIn('without gaps',result.validation.answer)
        self.assertIn('910 nm',result.validation.answer)
        self.assertIn('minor inter-order wavelength gaps',result.validation.answer)
        self.assertIsNone(compare_wavelength('What wavelength range does FIES cover?',self.evidence(
            instrument='FIES',sourceRole='instrument_landing',content=source.replace('FIES is','NOTCAM is'))))
        self.assertIsNone(compare_wavelength('What wavelength range does FIES cover?',self.evidence(
            instrument='FIES',sourceRole='instrument_landing',content=source.replace('entire spectral','filter spectral'))))

    def test_unsafe_evidence_is_not_used(self):
        for changes in ({"status": "historical"}, {"authority": "tier_4_unreviewed"},
                        {"instrument": "ALFOSC"},
                        {"content": "NOTCam does not cover wavelengths from 0.8 to 2.5µm."},
                        {"content": "NOTCam's filter covers wavelengths from 0.8 to 2.5µm."},
                        {"content": "NOTCam has 0.8 to 2.5µm pixels."},
                        {"content": "NOTCam's planned design covers wavelengths from 0.8 to 2.5µm."}):
            with self.subTest(changes=changes):
                self.assertIsNone(compare_wavelength("Can NOTCAM observe at 500nm?", self.evidence(**changes)))

    def test_conflicting_ranges_are_not_resolved_arbitrarily(self):
        conflicting = self.evidence() + self.evidence(content="NOTCam covers wavelengths from 0.4 to 2.5µm.")
        self.assertIsNone(compare_wavelength("Can NOTCAM observe at 500nm?", conflicting))

    def test_complex_or_unsupported_question_uses_normal_path(self):
        for question in ("Can NOTCAM observe at 500nm in spectroscopy mode?",
                         "Can NOTCAM observe at 500nm and 1000nm?",
                         "Can NOTCAM observe at -500nm?", "Can NOTCAM observe at 5e2nm?",
                         "Can NOTCAM observe at 500mm?", "What is NOTCAM?",
                         "Could NOTCAM observe at 500nm in the past?",
                         "Can the instrument observe at 500nm?"):
            with self.subTest(question=question):
                self.assertIsNone(compare_wavelength(question, self.evidence()))

    def test_german_answer(self):
        result = compare_wavelength("Kann NOTCAM bei einer Wellenlänge von 500nm beobachten?", self.evidence(), "de")
        self.assertTrue(result.validation.answer.startswith("Nein."))


if __name__ == "__main__":
    unittest.main()
