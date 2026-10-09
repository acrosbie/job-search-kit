"""Write the engine's fingerprint into plugins/job-search/engine/jobkit/__init__.py.

Run after changing any file under plugins/job-search/engine/ (tests/test_guards.py fails until you
do): python tools/update_fingerprint.py
"""

import os
import re
import sys

ENGINE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "plugins", "job-search", "engine")
sys.path.insert(0, ENGINE)

from jobkit import fingerprint  # noqa: E402

path = os.path.join(ENGINE, "jobkit", "__init__.py")
with open(path, encoding="utf-8") as f:
    text = f.read()
new = re.sub(r'__fingerprint__ = "[0-9a-f]*"', f'__fingerprint__ = "{fingerprint.compute()}"', text)
with open(path, "w", encoding="utf-8", newline="\n") as f:
    f.write(new)
print(re.search(r'__fingerprint__ = "([0-9a-f]*)"', new).group(1))
