import os

import pytest

import avlwrapper as avl


def pytest_collection_modifyitems(config, items):
    if "avl_bin" in avl.default_config.settings:
        return
    if os.environ.get("AVLWRAPPER_REQUIRE_AVL"):
        # in CI, a missing AVL executable is an error, not a reason to skip
        raise pytest.UsageError("AVL executable not found")
    skip_avl = pytest.mark.skip(reason="AVL executable not found")
    for item in items:
        if "avl" in item.keywords:
            item.add_marker(skip_avl)
