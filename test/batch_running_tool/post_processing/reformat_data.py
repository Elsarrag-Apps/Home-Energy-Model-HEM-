import json


def read_run_json(path):
    """
    path: str filepath to json
    Read in run json as a dictionary.
    returns dictionary of run json
    """
    with open(path) as json_file:
        project_dict = json.load(json_file)

    return project_dict
