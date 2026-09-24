"""TOML reading. Python 3.11 ships tomllib; Cowork's workspace on the user's computer has 3.10,
so the engine carries tomli, the library tomllib was made from (jobkit/_vendor/tomli, MIT)."""

try:
    import tomllib as _toml
except ImportError:  # Python 3.10
    from ._vendor import tomli as _toml

loads = _toml.loads
TOMLDecodeError = _toml.TOMLDecodeError


def load_file(path):
    with open(path, encoding="utf-8") as f:
        return loads(f.read())
