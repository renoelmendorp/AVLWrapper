from avlwrapper.geometry import Geometry, Surface, Section, NacaAirfoil, Spacing, Control
from avlwrapper.general import Point
from avlwrapper.case import Case, Parameter
from avlwrapper.io import Session
import json

if __name__ == '__main__':

    flap_control = Control(name="flap",
                           gain=1.0,
                           x_hinge=0.8,
                           duplicate_sign=1.0)

    root_section = Section(leading_edge_point=Point(0, 0, 0),
                           chord=1.0,
                           controls=[flap_control],
                           airfoil=NacaAirfoil(naca='2414'))
    tip_section = Section(leading_edge_point=Point(0.6, 2.0, 0),
                          chord=0.4,
                          controls=[flap_control],
                          airfoil=NacaAirfoil(naca='2410'))

    wing_surface = Surface(name="Wing",
                           n_chordwise=8,
                           chord_spacing=Spacing.cosine,
                           n_spanwise=12,
                           span_spacing=Spacing.cosine,
                           y_duplicate=0.0,
                           sections=[root_section, tip_section])

    elevator = Control(name="elevator",
                       gain=1.0,
                       x_hinge=0.6,
                       duplicate_sign=1.0)

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

    geometry = Geometry(name="Test wing",
                        reference_area=4.8,
                        reference_chord=0.74,
                        reference_span=4,
                        reference_point=Point(0.21, 0, 0.15),
                        surfaces=[wing_surface, tail_surface])

    cruise_case = Case(name='Cruise', alpha=4.0)

    cruise_trim_case = Case(name='Trimmed', alpha=4.0)
    cruise_trim_case.parameters['elevator'] = Parameter(name='elevator', constraint='Cm', value=0.0)

    landing_case = Case(name='Landing', alpha=7.0, flap=15.0)

    session = Session(geometry=geometry, cases=[cruise_case, cruise_trim_case, landing_case])
    results = session.get_results()

    with open('out.json', 'w') as f:
        f.write(json.dumps(results))
