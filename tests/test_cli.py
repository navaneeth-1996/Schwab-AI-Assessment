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
    assert "REJECTED: Rejected: prerequisite CS101 not completed." in text
    assert "DROPPED: Dropped. | promoted: cara | skipped (ineligible, retained): ben" in text
    assert "DROPPED: Dropped. | promoted: ben" in text
    s = o.snapshot()
    assert s.enrolled == ("ben",)
    assert s.waitlist == ("amy", "dan")
