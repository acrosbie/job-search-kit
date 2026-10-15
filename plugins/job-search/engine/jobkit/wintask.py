"""The morning scan as a Windows scheduled task, for a computer where only Windows itself reaches the
job boards.

Found in real use (2026-10-08 to 10-12): Claude's workspaces, both the one on the user's computer and
the one on Anthropic's servers, were refused by a proxy on every board, while the same scan run on
Windows (from Remote Control) read 589 of 592. A Cowork scheduled task runs in the refused workspace,
so it can't do the fetching. This task does: Windows runs the folder's own copy of the engine each
morning, with `--out`, and a Cowork task can go through what it found (schedules.md).

The task runs the user's Python without a window (pythonw.exe, when it's there), only while they're
signed in, and catches up when the computer wakes after the time it was due.
"""

import datetime as dt
import os
import subprocess
import sys
import tempfile
from xml.sax.saxutils import escape

from .errors import Refused

NAME = "Job search morning scan"
# A run that reaches no board (the network not up yet after the computer wakes, say) exits with
# UNREACHED, and Windows tries again this often, this many times.
RETRY_MINUTES, RETRIES = 20, 3
DAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday")


def _python():
    exe = sys.executable
    quiet = os.path.join(os.path.dirname(exe), "pythonw.exe")
    return quiet if os.path.exists(quiet) else exe


def command(folder):
    """(program, arguments) the task runs: the folder's engine, scanning, its result in data/."""
    folder = os.path.abspath(folder)
    run = os.path.join(folder, ".kit", "engine", "run.py")
    out = os.path.join(folder, "data", "scan-latest.json")
    return _python(), f'-B "{run}" scan --folder "{folder}" --out "{out}" --fail-if-unreached'


def task_xml(folder, at, weekdays=False, today=None):
    program, args = command(folder)
    start = f"{(today or dt.date.today()).isoformat()}T{at}:00"
    when = ("<ScheduleByWeek><DaysOfWeek>" + "".join(f"<{d} />" for d in DAYS) +
            "</DaysOfWeek><WeeksInterval>1</WeeksInterval></ScheduleByWeek>") if weekdays else \
        "<ScheduleByDay><DaysInterval>1</DaysInterval></ScheduleByDay>"
    return f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>Checks the job boards for your job search each morning and saves what's new in your Job Search folder. Made by the job search kit; Claude can remove it.</Description>
  </RegistrationInfo>
  <Triggers>
    <CalendarTrigger>
      <StartBoundary>{start}</StartBoundary>
      <Enabled>true</Enabled>
      {when}
    </CalendarTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <StartWhenAvailable>true</StartWhenAvailable>
    <RunOnlyIfNetworkAvailable>true</RunOnlyIfNetworkAvailable>
    <ExecutionTimeLimit>PT30M</ExecutionTimeLimit>
    <RestartOnFailure>
      <Interval>PT{RETRY_MINUTES}M</Interval>
      <Count>{RETRIES}</Count>
    </RestartOnFailure>
    <Enabled>true</Enabled>
  </Settings>
  <Actions Context="Author">
    <Exec>
      <Command>{escape(program)}</Command>
      <Arguments>{escape(args)}</Arguments>
      <WorkingDirectory>{escape(os.path.abspath(folder))}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>
"""


def _check_time(at):
    try:
        dt.time.fromisoformat(at)
    except ValueError:
        raise Refused(f"give the time as HH:MM, such as 06:45, not {at!r}")
    if len(at) != 5:
        raise Refused(f"give the time as HH:MM, such as 06:45, not {at!r}")


def _windows():
    if os.name != "nt":
        raise Refused("a Windows scheduled task is made on Windows itself: run this from Remote Control or Code "
                      "mode on the user's computer, not from Claude's workspace")


def _schtasks(*args):
    return subprocess.run(["schtasks", *args], capture_output=True, text=True)


def create(folder, at, weekdays=False):
    _windows()
    _check_time(at)
    if not os.path.exists(os.path.join(folder, ".kit", "engine", "run.py")):
        raise Refused("the folder has no copy of the engine yet: run start first, which puts it there")
    work = tempfile.mkdtemp()
    path = os.path.join(work, "task.xml")
    with open(path, "w", encoding="utf-16") as f:
        f.write(task_xml(folder, at, weekdays))
    done = _schtasks("/Create", "/TN", NAME, "/XML", path, "/F")
    if done.returncode != 0:
        raise Refused(f"Windows didn't make the task: {(done.stderr or done.stdout).strip()}")
    program, args = command(folder)
    return {"task": NAME, "at": at, "days": "weekdays" if weekdays else "every day", "runs": f"{program} {args}"}


def show():
    _windows()
    done = _schtasks("/Query", "/TN", NAME, "/V", "/FO", "LIST")
    if done.returncode != 0:
        return {"task": NAME, "exists": False}
    fields = {}
    for line in done.stdout.splitlines():
        k, sep, v = line.partition(":")
        if sep and k.strip() in ("Next Run Time", "Last Run Time", "Last Result", "Status", "Task To Run"):
            fields[k.strip().lower().replace(" ", "_")] = v.strip()
    # Made before 0.16.0, it doesn't try again after a run that reached no board: make it again.
    outdated = "--fail-if-unreached" not in fields.get("task_to_run", "--fail-if-unreached")
    return {"task": NAME, "exists": True, **fields, "outdated": outdated}


def remove():
    _windows()
    done = _schtasks("/Delete", "/TN", NAME, "/F")
    if done.returncode != 0:
        raise Refused(f"there's no task called {NAME!r} to remove")
    return {"removed": NAME}
