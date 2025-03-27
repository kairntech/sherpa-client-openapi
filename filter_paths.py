import re
from pathlib import Path

import plac
from yaml import load, dump

try:
    from yaml import CLoader as Loader, CDumper as Dumper
except ImportError:
    from yaml import Loader, Dumper


def find_schemas(op):
    refs = get_recursively(op, '$ref')
    return [r[len('#/components/schemas/'):] for r in refs]


def get_recursively(search_dict, field):
    """
    Takes a dict with nested lists and dicts,
    and searches all dicts for a key of the field
    provided.
    """
    fields_found = []

    for key, value in search_dict.items():

        if key == field:
            fields_found.append(value)

        elif isinstance(value, dict):
            results = get_recursively(value, field)
            for result in results:
                fields_found.append(result)

        elif isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    more_results = get_recursively(item, field)
                    for another_result in more_results:
                        fields_found.append(another_result)

    return fields_found


def complete_schemas(public_schemas, all_schemas):
    more_schemas = set()
    for sc in public_schemas:
        schema = all_schemas[sc]
        schemas = find_schemas(schema)
        for s in schemas:
            if s not in public_schemas:
                more_schemas.add(s)
    public_schemas.update(more_schemas)
    if more_schemas:
        public_schemas.update(more_schemas)
        complete_schemas(public_schemas, all_schemas)
    return public_schemas


@plac.annotations(
    input=("Input yaml file", "positional", None, str),
    private=("Private operationIds", "positional", None, str),
    output=("Output yaml file", "positional", None, str)
)
def filter_paths(
        input="sherpa.yaml",
        private="private.txt",
        output="sherpa_public.yaml"
):
    input_file = Path(input)
    private_file = Path(private)
    output_file = Path(output)
    if not input_file.exists():
        print("Input file not found", input_file)
        exit(1)
    private_patterns = []
    with private_file.open("r", encoding="utf-8") as fin:
        for l in fin.readlines():
            l = l.strip()
            if l:
                private_patterns.append(re.compile(l))
    with input_file.open("r", encoding="utf-8") as fin:
        data = load(fin, Loader=Loader)

        # schemas = data['components']['schemas']

        public_paths = {}
        public_schemas = set()
        for path, ops in data['paths'].items():
            public_ops = {}
            for key, op in ops.items():
                opid = op['operationId']
                if not any(p.match(opid) for p in private_patterns):
                    public_ops[key] = op
                    schemas = find_schemas(op)
                    public_schemas.update(schemas)
            if public_ops:
                public_paths[path] = public_ops
        data['paths'] = public_paths
        public_schemas = complete_schemas(public_schemas, data['components']['schemas'])
        data['components']['schemas'] = {k: v for k, v in data['components']['schemas'].items() if k in public_schemas}
        with output_file.open("w", encoding="utf-8") as fout:
            out = dump(data, fout, Dumper=Dumper)


if __name__ == '__main__':
    plac.call(filter_paths)
