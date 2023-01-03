import os.path

import pytest

import avlwrapper as avl

CDIR = os.path.dirname(os.path.realpath(__file__))
RES_DIR = os.path.join(CDIR, "resources")


def test_supra():
    model = avl.Aircraft.from_file(os.path.join(RES_DIR, "supra.avl"))
    cases = avl.Case.from_file(os.path.join(RES_DIR, "supra.run"))
    session = avl.Session(geometry=model, cases=cases)
    results = session.run_all_cases()
    assert len(results) == len(cases)
