import os
import pep8


def test_pep8():
    style = pep8.StyleGuide()
    style.options.ignore += ("E501", "E701", "E251", "E203", "W503")
    errors = 0
    python_files = set()

    for root, _, files in os.walk("hier_config"):
        for f in files:
            if os.path.isfile(os.path.join(root, f)):
                if f.endswith(".py"):
                    python_files.add(os.path.join(root, f))

    errors += style.check_files(python_files).total_errors

    assert errors == 0, f"PEP8 style errors: {errors}"
