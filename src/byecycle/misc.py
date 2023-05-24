import enum
from typing import (
    Annotated,
    Literal,
    Optional,
    Sequence,
    TypeAlias,
    TypedDict,
    Unpack,
    cast,
)

from typer import Exit, Option

from byecycle import __version__

EdgeKind: TypeAlias = Literal["good", "bad", "complicated", "skip"]
ImportKind: TypeAlias = Literal["dynamic", "conditional", "typing", "parent", "vanilla"]
edge_order: dict[EdgeKind, int] = {"bad": 0, "complicated": 1, "good": 2, "skip": 3}


class ImportMetaData(TypedDict):
    tags: list[ImportKind]
    cycle: EdgeKind | None


GraphDict: TypeAlias = dict[str, dict[str, ImportMetaData]]


class SeverityMap(TypedDict, total=False):
    dynamic: EdgeKind
    conditional: EdgeKind
    typing: EdgeKind
    parent: EdgeKind
    vanilla: EdgeKind


class Edge(str, enum.Enum):
    """Proxy of the EdgeKind type alias.

    Necessary for typer due to https://github.com.tiangolo/typer/issues/76. I really hate
    it.
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
dynamic_annotation: TypeAlias = Annotated[Edge, Option(help=help_texts["dynamic_annotation"])]
conditional_annotation: TypeAlias = Annotated[Edge, Option(help=help_texts["conditional_annotation"])]
typing_annotation: TypeAlias = Annotated[Edge, Option(help=help_texts["typing_annotation"])]
parent_annotation: TypeAlias = Annotated[Edge, Option(help=help_texts["parent_annotation"])]
vanilla_annotation: TypeAlias = Annotated[Edge, Option(help=help_texts["vanilla_annotation"])]
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
    cycles: Sequence[ImportKind] | set[ImportKind], **kwargs: Unpack[SeverityMap]
) -> EdgeKind | None:
    """"""
    if not cycles:
        return None  # shouldn't happen, every import has at least one ImportKind
    severity_map = cast(SeverityMap, {**_default_cycle_severity, **kwargs})
    cycles = [c for c in cycles if c != "vanilla"]
    if not cycles:
        return severity_map["vanilla"]
    severity = sorted((severity_map[c] for c in cycles), key=edge_order.get)  # type: ignore
    return severity[0]


def path_to_module_name(path: str, base: str, name: str) -> str:
    """Turns a file path into a valid module name.

    Args:
        path: Absolute path to the file in question.
        base: Absolute path to the "source root".
        name: Name of the distribution.

    Examples:
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
