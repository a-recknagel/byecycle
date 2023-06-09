import importlib.util
import json
import os.path
from pathlib import Path

import networkx as nx  # type: ignore[import]
import typer
from rich import print, print_json

from byecycle.graph import Module, build_digraph
from byecycle.misc import EdgeKind, GraphDict
from byecycle.misc import _default_cycle_severity as severity
from byecycle.misc import (
    _Edge,
    conditional_annotation,
    draw_annotation,
    draw_only_cycles_annotation,
    dynamic_annotation,
    parent_annotation,
    rich_annotation,
    typing_annotation,
    vanilla_annotation,
    version_annotation,
)

cli = typer.Typer(rich_markup_mode="rich")


@cli.command(no_args_is_help=True)
def run(
    project: str,
    dynamic: dynamic_annotation = severity["dynamic"],  # type: ignore[assignment]
    conditional: conditional_annotation = severity["conditional"],  # type: ignore[assignment]
    typing: typing_annotation = severity["typing"],  # type: ignore[assignment]
    parent: parent_annotation = severity["parent"],  # type: ignore[assignment]
    vanilla: vanilla_annotation = severity["vanilla"],  # type: ignore[assignment]
    rich: rich_annotation = True,
    draw: draw_annotation = False,
    draw_only_cycles: draw_only_cycles_annotation = None,
    version: version_annotation = None,
):
    """Detect import cycles in python projects.

    A json-string will be printed to stdout containing a rich import listing which can be
    used for further analysis. The PROJECT can be either a path to a source tree, or the
    name of an installed distribution. For distributions, take care that no folder of
    the same name is local to your call site which could confuse the resolution logic.
    """
    data, graph, name = _run(
        project,
        dynamic=dynamic,  # type: ignore[arg-type]
        conditional=conditional,  # type: ignore[arg-type]
        typing=typing,  # type: ignore[arg-type]
        parent=parent,  # type: ignore[arg-type]
        vanilla=vanilla,  # type: ignore[arg-type]
    )
    if draw:
        from byecycle.draw import draw_graph

        graph_path, legend_path = draw_graph(name, graph, draw_only_cycles is True)
        print(f"Saved graph image at ", end="")
        print(graph_path.resolve())
        print("Saved graph legend at ", end="")
        print(legend_path.resolve())
    else:
        if rich:
            print_json(data=data)
        else:
            print(json.dumps(data, ensure_ascii=True, indent=2))


def _run(
    project: str,
    *,
    dynamic: EdgeKind = severity["dynamic"],
    conditional: EdgeKind = severity["conditional"],
    typing: EdgeKind = severity["typing"],
    parent: EdgeKind = severity["parent"],
    vanilla: EdgeKind = severity["vanilla"],
) -> tuple[GraphDict, nx.DiGraph, str]:
    """Programmatic equivalent of running this package through the CLI.

    Args:
        project: Either the path to a project source, or the name of an installed package.
        dynamic: Severity of dynamic import cycles.
        conditional: Severity of conditional import cycles.
        typing: Severity of typing-only import cycles.
        parent: Severity of parent-package-resolution related import cycles.
        vanilla: Severity of vanilla import cycles.

    Returns:
        A dictionary-representation of the import graph.
        The actual import graph.
        The name of the package.
    """
    if os.path.isdir(project):
        project_path = Path(project)
    else:
        try:
            spec = importlib.util.find_spec(project)
        except ImportError:
            spec = None
        if spec is None or spec.origin is None:
            raise RuntimeError(
                f"Failed trying to resolve {project=} as a package, please pass the "
                f"source code location as proper path."
            )
        project_path = Path(spec.origin).parent.resolve()

    root = Module.parse(project_path)
    graph = build_digraph(
        root,
        dynamic=dynamic,
        conditional=conditional,
        typing=typing,
        parent=parent,
        vanilla=vanilla,
    )
    return {key: {**graph[key]} for key in graph}, graph, project_path.name
