import io
from pathlib import Path

from course_registration import CourseOffering, LearnerDirectory
from course_registration.cli import run


def test_demo_script_runs_end_to_end():
    d = LearnerDirectory()
    o = CourseOffering("CS201", 1, "CS101", d)
    out = io.StringIO()
    run((Path(__file__).parent.parent / "examples" / "demo.txt").read_text().splitlines(), out, o, d)
    text = out.getvalue()
    assert "DROPPED: Dropped. | promoted: erin | removed (ineligible): bob" in text
    assert "PREVIOUSLY_DROPPED" in text and "PREVIOUSLY_REMOVED" in text
    assert o.snapshot().enrolled == ("erin",) and o.snapshot().waitlist == ("carol",)
