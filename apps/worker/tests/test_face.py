import unittest

from app.face import KnownFace, RecognizedFace, _best_known_face_match, _find_face_match_for_detection
from app.types import BoundingBox, Detection


class DummyRecognizer:
    def __init__(self, scores: dict[tuple[str, str], float]) -> None:
        self.scores = scores

    def match(self, embedding, known_embedding, _metric) -> float:
        return self.scores[(embedding, known_embedding)]


class DummyCv2:
    FaceRecognizerSF_FR_COSINE = 0


class FaceHelperTests(unittest.TestCase):
    def test_best_known_face_match_returns_highest_score_above_threshold(self) -> None:
        recognizer = DummyRecognizer(
            {
                ("live-1", "known-a"): 0.41,
                ("live-1", "known-b"): 0.77,
            }
        )
        result = _best_known_face_match(
            embedding="live-1",
            known_faces=[
                KnownFace(
                    employee_id="employee-a",
                    employee_code="EMP-A",
                    full_name="Alpha Employee",
                    role_title="Operator",
                    embedding="known-a",
                ),
                KnownFace(
                    employee_id="employee-b",
                    employee_code="EMP-B",
                    full_name="Bravo Employee",
                    role_title="Manager",
                    embedding="known-b",
                ),
            ],
            recognizer=recognizer,
            cv2_module=DummyCv2(),
            threshold=0.45,
        )

        self.assertIsNotNone(result)
        self.assertEqual(result.employee_id, "employee-b")
        self.assertAlmostEqual(result.score, 0.77)

    def test_find_face_match_for_detection_uses_face_inside_person_box(self) -> None:
        detection = Detection(
            label="person",
            entity_type="person",
            confidence=0.93,
            bbox=BoundingBox(x1=100, y1=80, x2=320, y2=420),
        )
        matched_face = RecognizedFace(
            bbox=(150.0, 120.0, 70.0, 70.0),
            employee_id="employee-1",
            employee_code="EMP-1",
            full_name="Inside Face",
            role_title="Engineer",
            score=0.81,
        )
        outside_face = RecognizedFace(
            bbox=(350.0, 100.0, 60.0, 60.0),
            employee_id="employee-2",
            employee_code="EMP-2",
            full_name="Outside Face",
            role_title="Engineer",
            score=0.95,
        )

        result = _find_face_match_for_detection(detection, [outside_face, matched_face])

        self.assertIsNotNone(result)
        self.assertEqual(result.employee_id, "employee-1")


if __name__ == "__main__":
    unittest.main()
