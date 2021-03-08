import os.path

import avlwrapper as avl

file_path = os.path.join(avl.config.MODULE_DIR, "examples", "b737.avl")

my_aircraft = avl.Aircraft.from_file(file_path)
my_trim_case = avl.Case(
    name="trimmed",
    alpha=avl.Parameter("alpha", setting="CL", value=0.6),
    elevator=avl.Parameter("elevator", setting="Cm", value=0.0),
)

session = avl.Session(my_aircraft, cases=[my_trim_case])
results = session.run_all_cases()
