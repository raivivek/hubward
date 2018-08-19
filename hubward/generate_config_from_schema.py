from jsonschema import Draft4Validator, validators
from collections import OrderedDict
from textwrap import wrap as _wrap
import ruamel.yaml


def access(dct, keys):
    """
    Access a value from an arbitrarily-nested dictionary, given a set of keys.

    If any key doesn't exist, returns None.


    >>> access({'a': {'aa': {'aaa': {'b': 1, 'c': 2}}}}, keys=['a', 'aa', 'aaa', 'b'])
    1
    """
    o = dct
    for k in keys:
        o = o.get(k)
        if o is None:
            return None
    return o


def follow_ref(ref, dct):
    """
    Follow a "$ref" JSON Schema reference
    """
    ref = ref.lstrip('#/')
    keys = ref.split('/')
    return access(dct, keys)


def _indent(s, amount):
    """
    Indents string `s` by `amount` doublespaces.
    """
    pad = '  ' * amount
    return '\n'.join([pad + i for i in s.splitlines(False)])


def create_config(schema, fout=None):
    """
    Generates an example config file based on the schema alone and writes it to
    `fout`, which can then be validated.

    The goal is to have the schema be the sole source of config files.

    "description" fields in the schema will be printed out as YAML comments,
    serving as documentation.

    Parameters
    ----------
    schema : str
        Filename of schema

    fout : file-like
        Output file to write YAML to.
    """

    d = ruamel.yaml.load(open(schema), Loader=ruamel.yaml.SafeLoader)

    def props(path, v, fout=None, print_key=True):
        """
        Recursively print out a filled-in config file based on the schema
        """

        # Set the full original and output file objects, but only on the first
        # time.
        try:
            props.orig
        except AttributeError:
            props.orig = v

        try:
            props.out
        except AttributeError:
            props.out = fout

        # Key into schema
        if path:
            k = path[-1]
        else:
            k = None

        def wrap(s):
            "wrap a string at the current indent level"
            return ("\n%s# " % (indent)).join(_wrap(s))

        indent = '  ' * props.level

        #  Print out the description as a comment.
        if 'description' in v:
            props.out.write('\n%s# %s\n' % (indent, wrap(v['description'])))

        # Describe the possible values of any enums.
        if 'enum' in v:
            enum = '\n'.join(['%s# - "%s"' % (indent, i) for i in v['enum']])
            props.out.write(
                '{indent}# options for "{k}" are:\n{enum}\n'
                .format(**locals()))

        default = v.get('default')

        # Create an appropriate prefix. This avoids trailing spaces for keys
        # with no value; this also sets strings with no default to "" instead
        # of a blank space.
        prefix = " "
        if default is None:
            if v.get('type') == "string":
                default = '""'
            else:
                default = ""
                prefix = ""

        else:
            # It's tricky to get arrays to be generated using $ref references;
            # this allows a default to be written into the schema and printed
            # nicely in the generated output.

            if v.get('type') in ['object', 'array']:
                default ='\n' + _indent(
                    ruamel.yaml.safe_dump(default, default_flow_style=False, indent=2, line_break=False),
                    props.level + 2
                )


        if not print_key:
            k = ""
            colon = ""
            indent = ""
        else:
            colon = ":"

        # Write out what we have so far.
        props.out.write(
            '{indent}{k}{colon}{prefix}{default}\n'.format(**locals()))


        # Follow references if needed for an array
        if 'type' in v and v['type'] == 'array':
            if 'default' not in v:
                props.level += 1
                props.out.write('%s-' % ('  ' * props.level))
                props.level -= 1

                if '$ref' in v['items']:
                    props.level += 1
                    props(path,
                          follow_ref(v['items']['$ref'],
                                     props.orig),
                          print_key=False)
                    props.level -= 1

        # Recursively call this function for everything in properties
        if 'properties' in v:
            for k, v in v['properties'].items():
                props.level += 1
                path.append(k)
                props(path, v)
                props.level -= 1
                path.pop()
        return

    # Set the default level and then recursively call props to generate the
    # YAML file.
    #
    props.level = -1
    props([], d, fout, print_key=False)
    return
