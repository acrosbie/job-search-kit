"""What's new in each version, said once to a user whose folder used an older one.

`start` lists it in `next` the first time it runs on a newer engine, then notes the version as seen
in data/kit.json, so it is said once. A folder with no scans yet is being set up: nothing to say.
"""

import os

from . import __version__, store

NEWS = {
    "0.9.0": "Each application has its own record, a check that can't reach your job boards says so and changes "
             "nothing, and there's a weekly work-search log (say \"my work search log\").",
    "0.10.0": "Prep for a later interview round starts from what you said about the last one.",
    "0.11.0": "Your jobs page opens with Today: your next interview, what to do now, and how your search is going. "
              "Each job worth a look is written up for you.",
    "0.11.1": "Your jobs page lists each top pick once and says how many jobs were screened out, and a cancelled "
              "interview can be taken off your calendar.",
}


def _v(text):
    try:
        return tuple(int(x) for x in text.split("."))
    except ValueError:
        return ()


def unseen(root, has_history):
    """The lines not yet said for this folder, oldest first; and the current version noted as seen. A
    folder that never noted one hears only the current minor version's news."""
    folder = store.Folder(root)
    path = os.path.join(folder.data, "kit.json")
    kit = folder.read_json(path) or {}
    seen = kit.get("seen_version", "")
    if seen == __version__:
        return []
    folder.write_json(path, {**kit, "seen_version": __version__})
    if not has_history:
        return []
    now = _v(__version__)
    if seen:
        keep = [v for v in NEWS if _v(seen) < _v(v) <= now]
    else:
        keep = [v for v in NEWS if _v(v)[:2] == now[:2] and _v(v) <= now]
    return [NEWS[v] for v in sorted(keep, key=_v)]
