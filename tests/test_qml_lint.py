"""Cheap structural QML checks: Quickshell refuses a component whose object
sets the same property twice ("Property value set multiple times"), which
silently made the whole palette unavailable in 0.10.0 development."""
import glob
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKIP = ("function", "signal", "property", "required", "readonly", "import")


def duplicate_bindings(path):
    found = []
    stack = [{}]
    with open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            s = line.split("//")[0].strip()
            m = re.match(r"^([A-Za-z_][\w.]*)\s*:\s*[^{]", s)
            if m and not s.startswith(SKIP):
                key = m.group(1)
                if key in stack[-1]:
                    found.append((n, key, stack[-1][key]))
                stack[-1][key] = n
            for ch in s:
                if ch == "{":
                    stack.append({})
                elif ch == "}" and len(stack) > 1:
                    stack.pop()
    return found


class QmlLintTests(unittest.TestCase):
    def test_no_property_set_twice_in_one_object(self):
        files = glob.glob(os.path.join(ROOT, "*.qml")) + glob.glob(os.path.join(ROOT, "shell", "*.qml"))
        self.assertTrue(files)
        problems = []
        for f in files:
            for n, key, first in duplicate_bindings(f):
                problems.append(f"{os.path.relpath(f, ROOT)}:{n} {key} (first set on line {first})")
        self.assertEqual(problems, [])


if __name__ == "__main__":
    unittest.main()
