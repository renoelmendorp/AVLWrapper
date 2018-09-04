#!/usr/bin/env python3

import json
from avlwrapper import Geometry, Surface, Section, NacaAirfoil, Control, Point, Spacing, Session, Case, Parameter, ParameterSweep

if __name__ == '__main__':

    # control surface definition of a flap (to be used in the wing)
    flap_control = Control(name="flap",
                           gain=1.0,
                           x_hinge=0.8,
                           duplicate_sign=1.0)

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
                       duplicate_sign=1.0)

    # tail surface definition, sections are defined in-line
    tail_surface = Surface(name="Horizontal Stabiliser",
                           n_chordwise=8,
                           chord_spacing=Spacing.cosine,
                           n_spanwise=8,
                           span_spacing=Spacing.cosine,
                           y_duplicate=0.0,
                           sections=[Section(leading_edge_point=Point(3.5, 0, 0.2),
                                             chord=0.4,
                                             controls=[elevator]),
                                     Section(leading_edge_point=Point(3.7, 1.2, 0.2),
                                             chord=0.25,
                                             controls=[elevator])])

    # geometry object (which corresponds to an AVL input-file)
    geometry = Geometry(name="Test wing",
                        reference_area=4.8,
                        reference_chord=0.74,
                        reference_span=4,
                        reference_point=Point(0.21, 0, 0.15),
                        surfaces=[wing_surface, tail_surface])

    # Cases (multiple cases can be defined)
    cruise_case = Case(name='Cruise', alpha=4.0)  # Case defined by one angle-of-attack

    # More elaborate case, angle-of-attack of 4deg, elevator parameter which sets Cm (pitching moment) to 0.0
    cruise_trim_case = Case(name='Trimmed',
                            alpha=4.0,
                            elevator=Parameter(name='elevator', constraint='Cm', value=0.0))

    # Landing case; flaps down by 15deg
    landing_case = Case(name='Landing', alpha=7.0, flap=15.0)

    # create session with the geometry object and the cases
    session = Session(geometry=geometry, cases=[cruise_case, cruise_trim_case, landing_case])

    # get results and write the resulting dict to a JSON-file
    session.show_geometry()
    results = session.get_results()
    with open('out.json', 'w') as f:
        f.write(json.dumps(results))

    polar_cases = ParameterSweep(base_case=cruise_trim_case,
                                 parameters=[{'name': 'alpha',
                                             'values': list(range(15))}])

    session = Session(geometry=geometry, cases=polar_cases.cases)

    results = session.get_results()
    with open('out2.json', 'w') as f:
        f.write(json.dumps(results))
