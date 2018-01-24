if __name__ == '__main__':
    from avlwrapper.geometry import FileWrapper
    from avlwrapper.case import Case
    from avlwrapper.io import Session
    import json

    geometry = FileWrapper(file='b737.avl')
    case = Case(name='Cruise')
    session = Session(geometry=geometry, cases=[case])
    results = session.get_results()

    with open('out.json', 'w') as f:
        f.write(json.dumps(results))
