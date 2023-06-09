"""
All algorithms that are concerned with generating the import graph live in this module.
On a high level, the following takes place:

1. Given an absolute path to a directory, recursively collect all python files in it
2. Compile the [AST](https://docs.python.org/3/library/ast.html#module-ast) of each file
3. Collect all import statements from the ASTs, retain those that successfully match
   against any of the parsed files (a _module_)
4. From the context of the import-node within its AST, categorize each import statement
5. Distribute the imports onto the modules they took place in, merge their categories if
   there were multiple
6. From these `module -> modules` mappings, generate a di-graph where the nodes are all
   parsed modules, and the edges are the imports that take place between them
7. A bidirectional edge implies an import cycle, and each edge retains the import
   categories as metadata to help interpret the severity of the cycle
"""
from __future__ import annotations

import ast
import itertools
from collections import defaultdict
from operator import attrgetter
from pathlib import Path
from typing import Iterable, Self, Unpack

import networkx as nx  # type: ignore[import]

from byecycle.misc import (
    EdgeKind,
    ImportKind,
    ImportStatement,
    SeverityMap,
    cycle_severity,
    path_to_module_name,
)


class Module:
    """Represent a python module and the modules it imports.

    Every module has links to both its parent and children modules, as well as a
    collection of modules that it imports in some way or another.

    Parent-module imports are a bit of a special case, as their name doesn't actually
    exist in the child module's namespace. But since any import like
    `from foo.bar import baz` will, before `baz` is resolved, import `foo.bar` (which in
    turn needs an import of `foo` before that), they are registered first thing anyway.

    Treating their reliance chain as _imports_ models their relationship accurately for
    the most part, but does create the impression of cycles if a parent imports names from
    a child, which is a popular pattern for simplifying/exposing a public API. As a
    consequence, these child-parent imports should be treated differently during
    analysis.

    See Also:
        [discuss.python.org: Partial Modules](https://discuss.python.org/t/question-understanding-imports-a-bit-better-how-are-cycles-avoided/26647/2)
        for a technical explanation of how parent and child modules interact during
        imports.
    """

    def __init__(self, name: str, parent: Module | None):
        self.name: str = name
        self.parent: Module | None = parent
        self.children: dict[str, Module] = {}
        self.imports: dict[Module, set[ImportKind]] = defaultdict(set)
        if self.parent is not None:
            self.imports[self.parent] = {"parent"}
            self.parent.children[self.name] = self

    def __getitem__(self, item: str) -> Module:
        return self.children[item]

    def __str__(self):
        if self.children:
            children = ", ".join(map(str, self.children.values()))
            return f"{{{self.name} -> {children}}}"
        else:
            return self.name

    def __repr__(self):
        return f"Module('{self.name}')"

    def __hash__(self):
        """Setting the hash of a module to be equal to its name's hash.

        That way, module objects can be found in hash maps by searching for their name
        as a string. This also means that you can't mix strings and modules in said hash
        maps without getting very confusing bugs. But, you know, why would you ever want
        to do that anyway, right?
        """
        return self.name.__hash__()

    def __eq__(self, other):
        """Modules of the same name should always be equal to each other.

        A module comparing equal with its name enables searching for them in hash maps by
        their name.
        """
        return self.name == other or self.name == other.name

    def add_import(self, import_: ImportStatement, tag: ImportKind, root: Module):
        """Register a local import statement and its tag to this Module.

        Args:
            import_: Equivalent to an import statement. If the name is set, it may or may
                not refer to a module.
            tag: Describes the kind of import, e.g. import of module `foo` has the
                tags `typing`, meaning it is the import of a parent module within an
                `if typing.TYPE_CHECKING` block, which will be important information once
                we want to visualize the severity of certain cyclic imports.
            root: The root module, which is used to find the other module. It must point
                to the root module of the fully parsed source tree in order to produce
                correct results.

        !!! warning
            Given that an import statement of the form `from foo.bar import baz` can't be
            reasonably resolved in a static approach, a little guessing has to take place.
            The current idea is to try and import the full normalized statement
            `foo.bar.baz` as a module. If that fails (read, no python file was parsed
            which corresponds to the module name), only the part between `from` and
            `import`, i.e. `foo.bar` is attempted, assuming that `baz` is an attribute
            within `foo.bar`.

            As long as the import statements would not raise an `ImportError`, this
            _should_ always produce correct results.
        """
        target: dict[str, Module] | Module = {root.name: root}  # seed
        for sub_module in itertools.accumulate(
            import_["module"].split("."), lambda a, b: f"{a}.{b}"
        ):
            target = target[sub_module]
        if import_["name"] is not None:
            try:
                target = target[f"{import_['module']}.{import_['name']}"]
            except KeyError:
                pass  # "name" was not a module -- that's ok
        self.imports[target].add(tag)  # type: ignore[index]

    @staticmethod
    def walk(module: Module) -> Iterable[Module]:
        yield module
        for recursion in map(Module.walk, module.children.values()):
            yield from recursion

    @classmethod
    def parse(cls, source_path: Path) -> Module:
        """Walks down a source tree and registers each python file as a [`Module`][byecycle.graph.Module].

        After parsing all files recursively, all import statements in each file that
        import a module that resolves to any of the files that we just parsed are listed
        on their respective [`Module`][byecycle.graph.Module]. Additionally, some metadata
        from the context of the import is retained. Specifically, the import-kind
        definitions are:

        ___`vanilla`___

        :   A regular import at the top-level of the module

        ___`typing`___

        :   Only executed during static type analysis

        ___`dynamic`___

        :   Scoped in a function, which might not be executed on module load

        ___`conditional`___

        :   In an if-block at the top-level of the module, so only maybe executed

        ___`parent`___

        :   Due to the module in question being a parent of the current module (in python,
            parent modules are imported before their children)

        If a module is imported multiple times in different ways, all their metadata is
        aggregated on the same entry.

        Args:
            source_path: Location of the source tree of the package that should be walked.
                The `.name` attribute of this parameter is assumed to be the name of the
                package in order to identify which imports are local imports.

        Returns:
            The top level, aka "root", module.
        """
        root_name = source_path.name
        node_data: dict[Module, list[tuple[ImportStatement, ImportKind]]] = {}
        module_map: dict[str, Module] = {}

        # walk the project, compile all python files, collect their import statements
        # package modules need to be parsed first to make parent-child-linkage work
        for path in sorted(
            source_path.rglob("*.py"),
            key=lambda x: x.parent if x.name == "__init__.py" else x,
        ):
            name = path_to_module_name(str(path), str(source_path), root_name)
            with open(path) as f:
                ast_ = ast.parse(f.read())

            # add a link to the parent module and their qualname
            for node in ast.walk(ast_):
                for child in ast.iter_child_nodes(node):
                    child._parent = node  # type: ignore[attr-defined]
                    child._module = (  # type: ignore[attr-defined]
                        name.split(".") + ["."]
                        if path.name == "__init__.py"
                        else name.split(".")
                    )
            visitor = ImportVisitor()
            visitor.visit(ast_)

            parent = module_map.get(name.rsplit(".", 1)[0])
            module = cls(name, parent)
            module_map[name] = module
            node_data[module] = [
                (m, t) for m, t in visitor.imports if m["module"].startswith(root_name)
            ]

        # all source files parsed
        root = module_map[root_name]

        # link up import data with their respective module
        for module, imports in node_data.items():
            for import_, kind in imports:
                module.add_import(import_, kind, root)

        return root


class ImportVisitor(ast.NodeVisitor):
    """Collect import statements in a module and assign them an [`ImportKind`][byecycle.misc.ImportKind] category.

    Relies on a non-standard `_parent` field being present in each node which contains
    a link to its parent node, and `_module` to resolve relative imports.
    """

    def __init__(self):
        self.imports: list[tuple[ImportStatement, ImportKind]] = []

    @classmethod
    def find_import_kind(cls, node: ast.Import | ast.ImportFrom) -> ImportKind:
        """Find the [`ImportKind`][byecycle.misc.ImportKind] of an import statement.

        A single import statement can only have a single [`ImportKind`][byecycle.misc.ImportKind].
        This function uses information in the `ast.AST`-node to identify if it was
        `dynamic`, `typing`, `conditional`, or `vanilla`.

        Args:
            node: Node in which the import statement takes place.

        Returns:
            The identified [`ImportKind`][byecycle.misc.ImportKind], by default `vanilla`.
        """
        parent: ast.AST = node._parent  # type: ignore[union-attr]
        match parent:
            case ast.If(
                _parent=ast.Module(),  # type: ignore[misc]
                test=(ast.Name(id="TYPE_CHECKING") | ast.Attribute(attr="TYPE_CHECKING")),
            ):
                # guarded by `if typing.TYPE_CHECKING:`
                return "typing"
            case ast.If(_parent=ast.Module()):  # type: ignore[misc]
                # probably guarded by `if sys.version >= (x, y, z):`, but doesn't actually
                # matter -- anything but TYPE_CHECKING is env-dependent during runtime or
                # too obtuse to consider (I'm not writing code that checks for `if True:`)
                return "conditional"
            case _:
                while True:
                    if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        # the import happens somewhere in a function
                        return "dynamic"
                    try:
                        parent = parent._parent  # type: ignore[attr-defined]
                    except AttributeError:
                        # any nodes that reach this point are treated as regular toplevel
                        # imports, like imports that happen in a class body
                        return "vanilla"

    def visit_Import(self, node: ast.Import):
        kind = self.find_import_kind(node)
        for alias in node.names:
            self.imports.append(({"module": alias.name, "name": None}, kind))

    def visit_ImportFrom(self, node: ast.ImportFrom):
        kind = self.find_import_kind(node)
        # handle relative imports
        if node.level:
            path = node._module[: -node.level]  # type: ignore[attr-defined]
            if node.module:
                path.append(node.module)
            module = ".".join(path)
        else:
            # if node.level is 0, node.module can't be None
            module = node.module  # type: ignore[assignment]

        for alias in node.names:
            self.imports.append(({"module": module, "name": alias.name}, kind))


def build_digraph(root: Module, **kwargs: Unpack[SeverityMap]) -> nx.DiGraph:
    """Turns module-import-mappings into a smart graph object.

    Args:
        root: Gets walked to produce all [`Module`][byecycle.graph.Module] objects that
            know what other local modules they import, and how.
        **kwargs: Override the default settings for the severity of the "how" when imports
            in local modules might cause import cycles.

    Returns:
        A graph object which supports the kind of operations that you'd want when working
            with graph-like structures. Every edge in the graph has a `tags` and a `cycle`
            entry (accessible with `getitem()`) holding metadata that can help interpret
            how much of an issue a particular cyclic import might be.
    """
    g = nx.DiGraph()
    g.add_nodes_from(map(attrgetter("name"), Module.walk(root)))
    for module in Module.walk(root):
        for import_, tags in module.imports.items():
            g.add_edge(module.name, import_.name, tags=tags)
    for e_0, e_1 in g.edges():
        if g.has_edge(e_1, e_0):
            g[e_0][e_1]["cycle"] = cycle_severity(
                g[e_0][e_1]["tags"], g[e_1][e_0]["tags"], **kwargs
            )
        else:
            g[e_0][e_1]["cycle"] = None
    for e_0, e_1 in g.edges():
        g[e_0][e_1]["tags"] = [*g[e_0][e_1]["tags"]]
    return g
