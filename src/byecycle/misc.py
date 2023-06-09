"""
Collection of shared structures, types, and functions.
"""

import enum
from typing import (
    Annotated,
    Iterable,
    Literal,
    Optional,
    TypeAlias,
    TypedDict,
    Unpack,
    cast,
)

from typer import Exit, Option

from byecycle import __version__

ImportKind: TypeAlias = Literal["dynamic", "conditional", "typing", "parent", "vanilla"]
"""The types/kinds of imports that are currently recognized."""
EdgeKind: TypeAlias = Literal["good", "bad", "complicated", "skip"]
"""Describes an import cycle, helping with evaluating how much of an issue it could be."""
edge_order: dict[EdgeKind, int] = {"bad": 0, "complicated": 1, "good": 2, "skip": 3}


class ImportMetaData(TypedDict):
    """Metadata to interpret import cycle severity."""

    tags: list[ImportKind]
    cycle: EdgeKind | None


GraphDict: TypeAlias = dict[str, dict[str, ImportMetaData]]
"""Dictionary representation of an import graph.

The keys on the first level are the qualnames of importing modules, the keys on the second 
level are the qualnames of imported modules, and the values on the second level contain
the metadata dictionary of their keyed imports ([`ImportMetaData`][byecycle.misc.ImportMetaData]).
Metadata consists of a `tags`-list of [`ImportKind`][byecycle.misc.ImportKind]s and a
`cycle` which is either an [`EdgeKind`][byecycle.misc.EdgeKind] if there is a cycle, or
`None` if there isn't.

??? example
    ```py
    {
        "foo": {
            "foo.a": {
                "tags": ["vanilla"],
                "cycle": "complicated"
            }
        }
        "foo.a": {
            "foo": {
                "tags": ["parent", "vanilla"],
                "cycle": "complicated"
            },
            "foo.c": {
                "tags": ["vanilla"],
                "cycle": None
            }
        }
        "foo.b": {
            "foo": {
                "tags": ["parent"],
                "cycle": "complicated"
            },
            "foo.c": {
                "tags": ["typing"],
                "cycle": "skip"
            }
        }
        "foo.c": {
            "foo": {
                "tags": ["parent"],
                "cycle": None
            },
            "foo.b": {
                "tags": ["vanilla"],
                "cycle": "skip"
            }
        }
    }
    ```
"""


class SeverityMap(TypedDict, total=False):
    """Mapping of [`ImportKind`][byecycle.misc.ImportKind]s to [`EdgeKind`][byecycle.misc.ImportKind]s."""

    dynamic: EdgeKind
    conditional: EdgeKind
    typing: EdgeKind
    parent: EdgeKind
    vanilla: EdgeKind


class ImportStatement(TypedDict):
    """Container for the information that we need from an AST import node.

    The module-value is always non-empty, the name-value is only set by `ast.ImportFrom`.
    """

    module: str
    name: str | None


class _Edge(str, enum.Enum):
    """Proxy of the [`EdgeKind`][byecycle.misc.ImportKind] type alias.

    Necessary for typer due to https://github.com.tiangolo/typer/issues/76. I really hate
    it, also makes mypy sad.
    """

    good: EdgeKind = "good"
    bad: EdgeKind = "bad"
    complicated: EdgeKind = "complicated"
    skip: EdgeKind = "skip"


def _print_version(val: bool):
    if val:
        print(f"byecycle \N{bicycle} version: {__version__}")
        raise Exit()


# fmt: off
help_texts = {
    "dynamic_annotation": "Interpretation of cycles that happen dynamically in functions, potentially severely delayed during runtime.",
    "conditional_annotation": "Interpretation of cycles that only take place under certain circumstances, e.g. specific python-versions.",
    "typing_annotation": "Interpretation of cycles that happen within an `if typing.TYPE_CHECKING` context, i.e. only during static type checks.",
    "parent_annotation": "Interpretation of cycles due to parent modules importing their children, usually non-critical public API exposure in `__init__.py` files.",
    "vanilla_annotation": "Interpretation of 'normal' top-of-the-module cyclic imports.",
    "rich_annotation": "If unset, print plain ascii to the terminal.",
    "draw_annotation": "Flag which, if set, will draw the resulting import graph with matplotlib and write it to disk.",
    "draw_only_cycles_annotation": "If set, don't draw non-cyclic imports.",
    "version_annotation": "Print this package's version and exit.",
}
rich_annotation: TypeAlias = Annotated[bool, Option(help=help_texts["rich_annotation"])]
draw_annotation: TypeAlias = Annotated[bool, Option(help=help_texts["draw_annotation"])]
dynamic_annotation: TypeAlias = Annotated[_Edge, Option(help=help_texts["dynamic_annotation"])]
conditional_annotation: TypeAlias = Annotated[_Edge, Option(help=help_texts["conditional_annotation"])]
typing_annotation: TypeAlias = Annotated[_Edge, Option(help=help_texts["typing_annotation"])]
parent_annotation: TypeAlias = Annotated[_Edge, Option(help=help_texts["parent_annotation"])]
vanilla_annotation: TypeAlias = Annotated[_Edge, Option(help=help_texts["vanilla_annotation"])]
draw_only_cycles_annotation: TypeAlias = Annotated[Optional[bool], Option("--draw-only-cycles", help=help_texts["draw_only_cycles_annotation"])]
version_annotation: TypeAlias = Annotated[Optional[bool], Option("--version", callback=_print_version, is_eager=True, help=help_texts["version_annotation"])]
# fmt: on

_default_cycle_severity: SeverityMap = {
    "dynamic": "complicated",
    "conditional": "complicated",
    "typing": "skip",
    "parent": "complicated",
    "vanilla": "bad",
}


def cycle_severity(
    tags_a: set[ImportKind], tags_b: set[ImportKind], **kwargs: Unpack[SeverityMap]
) -> EdgeKind:
    """Interpret the severity of an import cycle given their tags.

    In general, all tags get thrown in the same bag and the one with the highest mapped
    severity "wins". Except for the "vanilla" tag, which will only have its severity
    considered if both imports had "vanilla" in their tag list.

    Args:
        tags_a: The set of import-kind tags for the first import statement.
        tags_b: The set of import-kind tags for the second import statement.
        **kwargs: Valid values are keywords equating to [`ImportKind`][byecycle.misc.ImportKind]s
            mapping to [`EdgeKind`][byecycle.misc.ImportKind]s in order to override that
            [`ImportKind`][byecycle.misc.ImportKind]'s severity-interpretation.

    Returns:
        A string denoting the severity of the cycle.
    """
    tags: set[ImportKind] = tags_a | tags_b
    if "vanilla" in tags and ("vanilla" not in tags_a or "vanilla" not in tags_b):
        tags.remove("vanilla")
    severity_map = cast(SeverityMap, {**_default_cycle_severity, **kwargs})
    severity = sorted((severity_map[t] for t in tags), key=edge_order.get)  # type: ignore[arg-type]
    return severity[0]


def path_to_module_name(path: str, base: str, name: str) -> str:
    """Turns a file path into a valid module name.

    Just an educated guess on my part, I couldn't find an official reference. Chances are
    that you can't know the real name of a package unless you actually install it, and
    only projects that adhere to best practices and/or common sense regarding naming and
    structure can be handled correctly by this function.

    Args:
        path: Absolute path to the file in question.
        base: Absolute path to the "source root".
        name: Name of the distribution.

    Returns:
        A string in the form of an importable python module.

    Example:
        ```py
        >>> # Sample call #1:
        >>> path_to_module_name(
        ...     path = "/home/me/dev/project/src/project/__init__.py"
        ...     base = "/home/me/dev/project/src/project/"
        ...     name = "project"
        ... )
        project
        >>> # Sample call #2:
        >>> path_to_module_name(
        ...     path = "/home/me/dev/project/src/project/code.py"
        ...     base = "/home/me/dev/project/src/project/"
        ...     name = "project"
        ... )
        project.code
        >>> # etc.
        ```

    Notes:
        - What if there is a namespace?
        - What if the name of the distribution is different from the base?
        - What if a distribution installs multiple packages?
    """
    return (
        path.removeprefix(base[: -len(name)])
        .removesuffix(".py")
        .removesuffix("__init__")
        .strip("/")
        .replace("/", ".")
    )
