"""
This code can be taken as a template for implementing a visualization of a module-import-
graph. This attempt here using matplotlib is something of a bare minimum, lacking key
features like the ability to zoom, editing, or any kind of rich inspection.

But it should give an idea of how a `networkx.DiGraph` can be used, and what kind of
metadata was put on its edges.
"""

from chextra import warn

warn()

from pathlib import Path

import matplotlib.colors as clrs  # type: ignore[import]
import matplotlib.patches as ptc  # type: ignore[import]
import matplotlib.pyplot as plt  # type: ignore[import]
import networkx as nx  # type: ignore[import]

DEFAULT_COLORS = {
    "no_cycle": "black",
    "good": "green",
    "bad": "red",
    "complicated": "yellow",
}


def draw_graph(package: str, g: nx.DiGraph, draw_only_cycles: bool) -> tuple[Path, Path]:
    """Use matplotlib to draw the import graph.

    This function also writes the drawn pictures to disk.

    Returns:
        The file location of the graph image.
        The file location of the legend of the nodes from the graph image.
    """
    graph_path = Path(f"{package}.png")
    legend_path = Path(f"{package}_legend.png")

    all_colors = list(clrs.CSS4_COLORS)
    ratio = 0 if not g.nodes() else len(all_colors) / len(g.nodes())
    colors = {k: all_colors[int(i * ratio)] for i, k in enumerate(g.nodes())}

    # draw and store digraph visualization
    layout = nx.kamada_kawai_layout(g)
    nx.draw_networkx_nodes(
        g,
        pos=layout,
        node_color=colors.values(),
        node_shape="o",
    )
    nx.draw_networkx_edges(
        g,
        pos=layout,
        edge_color=DEFAULT_COLORS["no_cycle"],
        arrows=True,
        edgelist=[
            (e_0, e_1)
            for e_0, e_1 in g.edges
            if g[e_0][e_1]["cycle"] is None and not draw_only_cycles
        ],
    )
    nx.draw_networkx_edges(
        g,
        pos=layout,
        edge_color=DEFAULT_COLORS["good"],
        arrows=False,
        edgelist=[(e_0, e_1) for e_0, e_1 in g.edges if g[e_0][e_1]["cycle"] == "good"],
    )
    nx.draw_networkx_edges(
        g,
        pos=layout,
        edge_color=DEFAULT_COLORS["bad"],
        arrows=False,
        edgelist=[(e_0, e_1) for e_0, e_1 in g.edges if g[e_0][e_1]["cycle"] == "bad"],
    )
    nx.draw_networkx_edges(
        g,
        pos=layout,
        edge_color=DEFAULT_COLORS["complicated"],
        arrows=False,
        edgelist=[
            (e_0, e_1) for e_0, e_1 in g.edges if g[e_0][e_1]["cycle"] == "complicated"
        ],
    )
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(graph_path)
    plt.show()

    # store legend
    plt.legend(
        loc="upper center",
        ncol=2,
        fancybox=True,
        shadow=True,
        handles=[ptc.Patch(color=c, label=l) for l, c in colors.items()],
    )
    plt.axis("off")
    plt.tight_layout()
    plt.savefig(legend_path, transparent=True)

    return graph_path, legend_path
