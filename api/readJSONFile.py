import json


def read_json_to_list(file_path):
    """Read a JSON dictionary file and return every word as a flat list of strings."""
    with open(file_path, "r", encoding="utf-8") as json_file:
        data = json.load(json_file)

    # Some word lists are a plain JSON array
    if isinstance(data, list):
        return [str(w) for w in data]

    string_list = []
    for value in data.values():
        if isinstance(value, list):
            string_list.extend(value)
        else:
            string_list.append(str(value))
    return string_list
