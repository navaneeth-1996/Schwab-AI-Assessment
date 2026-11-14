"""Tiny line-oriented demo shell. No business logic lives here.

    python -m course_registration.cli --capacity 2 --prereq CS101 --course CS201

Commands:
    learner <id> [completed_course ...]   register a learner
    complete <id> <course>                 add a completed course
    revoke <id> <course>                   revoke a completed course
    enroll <id> | drop <id> | leave <id>
    show                                   print offering state
    quit
"""

from __future__ import annotations

import argparse
import shlex
import sys

from . import CourseOffering, LearnerDirectory


def _fmt(result) -> str:
    line = f"{result.outcome.value}: {result.message}"
    if result.promoted:
        line += f" | promoted: {', '.join(result.promoted)}"
    if result.removed:
        line += f" | removed (ineligible): {', '.join(r.learner_id for r in result.removed)}"
    return line


def run(lines, out, offering: CourseOffering, directory: LearnerDirectory) -> None:
    ops = {"enroll": offering.enroll, "drop": offering.drop, "leave": offering.leave_waitlist}
    for raw in lines:
        parts = shlex.split(raw)
        if not parts or parts[0].startswith("#"):
            continue
        cmd, args = parts[0].lower(), parts[1:]
        try:
            if cmd in ("quit", "exit"):
                return
            if cmd in ops and len(args) == 1:
                print(_fmt(ops[cmd](args[0])), file=out)
            elif cmd == "learner" and args:
                directory.register(args[0], args[1:])
                print(f"registered {args[0]} completed={args[1:]}", file=out)
            elif cmd == "complete" and len(args) == 2 and directory.exists(args[0]):
                directory.add_completion(*args)
                print("ok", file=out)
            elif cmd == "revoke" and len(args) == 2 and directory.exists(args[0]):
                directory.revoke_completion(*args)
                print("ok", file=out)
            elif cmd == "show":
                s = offering.snapshot()
                print(f"{s.course_id} (prereq {s.prerequisite_course_id}) "
                      f"{len(s.enrolled)}/{s.capacity} enrolled", file=out)
                print(f"  enrolled: {list(s.enrolled)}", file=out)
                print(f"  waitlist: {list(s.waitlist)}", file=out)
                print(f"  statuses: { {k: v.value for k, v in s.statuses.items()} }", file=out)
            else:
                print(f"? unrecognised command: {raw.strip()}", file=out)
        except Exception as exc:  # keep the demo shell alive
            print(f"error: {exc}", file=out)


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--course", default="CS201")
    ap.add_argument("--prereq", default="CS101")
    ap.add_argument("--capacity", type=int, default=2)
    a = ap.parse_args(argv)
    directory = LearnerDirectory()
    offering = CourseOffering(a.course, a.capacity, a.prereq, directory)
    run(sys.stdin, sys.stdout, offering, directory)


if __name__ == "__main__":
    main()
