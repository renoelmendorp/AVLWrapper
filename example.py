#!/usr/bin/env python3

import json
from avlwrapper import (Geometry, Surface, Section, NacaAirfoil, Control,
                        Point, Spacing, Session, Case, Parameter,
                        create_sweep_cases, partitioned_cases)

if __name__ == '__main__':

    # control surface definition of a flap (to be used in the wing)
    flap_control = Control(name="flap",
                           gain=1.0,
                           x_hinge=0.8,
                           duplicate_sign=1)

    # wing root section with a flap control and NACA airfoil
    root_section = Section(leading_edge_point=Point(0, 0, 0),
                           chord=1.0,
                           controls=[flap_control],
                           airfoil=NacaAirfoil(naca='2414'))

    # wing tip
    tip_section = Section(leading_edge_point=Point(0.6, 2.0, 0),
                          chord=0.4,
                          controls=[flap_control],
                          airfoil=NacaAirfoil(naca='2410'))

    # wing surface defined by root and tip sections
    wing_surface = Surface(name="Wing",
                           n_chordwise=8,
                           chord_spacing=Spacing.cosine,
                           n_spanwise=12,
                           span_spacing=Spacing.cosine,
                           y_duplicate=0.0,
                           sections=[root_section, tip_section])

    # elevator control for the tail surface
    elevator = Control(name="elevator",
                       gain=1.0,
                       x_hinge=0.6,
                       duplicate_sign=1)

    # tail surface definition, sections are defined in-line
    tail_sections = [Section(leading_edge_point=Point(3.5, 0, 0.2),
                             chord=0.4,
                             controls=[elevator]),
                     Section(leading_edge_point=Point(3.7, 1.2, 0.2),
                             chord=0.25,
                             controls=[elevator])]
    tail_surface = Surface(name="Horizontal Stabiliser",
                           n_chordwise=8,
                           chord_spacing=Spacing.cosine,
                           n_spanwise=8,
                           span_spacing=Spacing.cosine,
                           y_duplicate=0.0,
                           sections=tail_sections)

    # geometry object (which corresponds to an AVL input-file)
    geometry = Geometry(name="Test wing",
                        reference_area=4.8,
                        reference_chord=0.74,
                        reference_span=4,
                        reference_point=Point(0.21, 0, 0.15),
                        surfaces=[wing_surface, tail_surface])

    # Cases (multiple cases can be defined)

    # Case defined by one angle-of-attack
    cruise_case = Case(name='Cruise', alpha=4.0)

    # More elaborate case, angle-of-attack of 4deg,
    # elevator parameter which sets Cm (pitching moment) to 0.0
    control_param = Parameter(name='elevator', constraint='Cm', value=0.0)
    cruise_trim_case = Case(name='Trimmed',
                            alpha=4.0,
                            elevator=control_param)

    # Landing case; flaps down by 15deg
    landing_case = Case(name='Landing', alpha=7.0, flap=15.0)

    # create session with the geometry object and the cases
    all_cases = [cruise_case, cruise_trim_case, landing_case]
    session = Session(geometry=geometry, cases=all_cases)

    # show geometry with AVL
    session.show_geometry()

    session.show_trefftz_plot(1)

    # get results and write the resulting dict to a JSON-file
    with open('out.json', 'w') as f:
        f.write(json.dumps(session.results))

    # generate cases for a parameter sweep
    polar_cases = create_sweep_cases(base_case=cruise_trim_case,
                                     parameters=[{'name': 'alpha',
                                                  'values': list(range(15))},
                                                 {'name': 'beta',
                                                  'values': list(range(-5, 6))}])

    # avl only supports 25 cases, use partitioned_cases generator
    partitions = partitioned_cases(polar_cases)

    results = {}
    for partition in partitions:
        session = Session(geometry=geometry, cases=partition)
        results.update(session.results)

    with open('out2.json', 'w') as f:
        f.write(json.dumps(results))
