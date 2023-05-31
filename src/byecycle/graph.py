from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path
from typing import Iterable, Self, Unpack

import networkx as nx  # type: ignore

from byecycle.misc import (
    EdgeKind,
    ImportKind,
    SeverityMap,
    cycle_severity,
    path_to_module_name,
)


class Module:
    """Represent a python module and the modules it imports."""

    _modules: list[Module] = []
    _sorted: bool = False

    def __init__(self, name: str):
        self.name: str = name
        Module._modules.append(self)
        self.imports: dict[Module, set[ImportKind]] = defaultdict(set)

    def add(self, other: Module | str, tag: ImportKind):
        """Add an import to this Module.

        This method can only be called once all Modules have been instantiated.

        Args:
            other: A modules, either as an object or as a string that will be evaluated as
                its longest match from all valid module names. Valid strings are fully
                qualified import arguments, i.e. `"foo.bar"` from `import foo.bar` or
                `"foo.bar.baz"` from `from foo.bar import baz`. If `foo.bar` is a
                registered module with name `baz` in it, both strings would add the module
                `foo.bar` as an import.
            tag: Describes the kind of import, e.g. import of module `foo` has the
                tags `typing`, meaning it is the import of a parent module within an
                `if typing.TYPE_CHECKING` block, which will be important information once
                we want to visualize the severity of certain cyclic imports.

        Raises:
            RuntimeError: If bad arguments are passed.
        """
        if not Module._sorted:
            # sort in descending alphabetical order, so that the longest match is found
            # first
            Module._modules.sort(key=lambda n: n.name, reverse=True)
            Module._sorted = True

        if isinstance(other, Module):
            target = other
        elif isinstance(other, str):
            for node in Module.modules():
                if other.startswith(node.name):
                    target = node
                    break
            else:
                # when calling this function, filter with `startswith(package)` to avoid
                # this exception
                raise RuntimeError(f"Tried to add non-local import {other=}.")
        else:
            # bad parameter type
            raise RuntimeError(f"Tried to use invalid type {type(other)} as module.")

        self.imports[target].add(tag)

    def __hash__(self):
        """Setting the hash of a module to be equal to its name's hash.

        That way, module objects can be found in hash maps by searching for their name
        as a string. Also means that you can't mix strings and modules in said hash maps
        without getting very confusing bugs. But, you know, why would you ever want to do
        that anyway, right?
        """
        return self.name.__hash__()

    def __str__(self):
        imports = {
            k.name: v
            for k, v in sorted(
                self.imports.items(), key=lambda x: x[0].name, reverse=True
            )
        }
        return f"'{self.name}' -> {imports}"

    @classmethod
    def reset(cls):
        cls._modules = []
        cls._sorted = False

    @classmethod
    def modules(cls) -> Iterable[Module]:
        """Accessor for all registered modules."""
        yield from cls._modules

    @classmethod
    def add_parent_imports(cls):
        """Make modules with parent packages import them explicitly.

        While the parent package's name doesn't automatically exist in a module's
        namespace, any import like `from foo.bar import baz` will, before `baz` is
        resolved, import `foo.bar` -- which in turn needs an import of `foo` before that.

        Treating their reliance chain as _imports_ models this link accurately for the
        most part, but does create the impression of cycles if a parent imports names from
        a child, which is a popular pattern for simplifying/exposing a public API. As a
        consequence, these child-parent imports should be treated differently during
        analysis.

        See Also:
            [discuss.python.org: Partial Modules](https://discuss.python.org/t/question-understanding-imports-a-bit-better-how-are-cycles-avoided/26647/2)
            for a technical explanation of how parent and child modules interact during
            imports.

        Notes:
            This method wil only produce accurate results once all Nodes have been
            initialised.
        """
        nodes: dict[str, Module] = {node.name: node for node in cls.modules()}
        for node in [*cls.modules()]:  # node.add() may shuffle cls.modules
            package = node.name.rsplit(".", 1)[0]  # only direct parent, not grandparents
            if package in nodes and package != node.name:
                node.add(nodes[package], "parent")

    @classmethod
    def populate(cls, source_path: Path):
        """Walks down a source tree and registers each python file as a [`Module`][byecycle.graph.Module].

        After parsing all files recursively, all import statements in each file that
        import a module that resolves to any of the files just recursed are listed
        on their respective [`Module`][byecycle.graph.Module]. Additionally, some metadata from the context of the
        import is retained. Specifically, the import-kind defintions are:

        ___`vanilla`___

        :   A regular import at the top-level of the module

        ___`typing`___

        :   Only executed during static type analyis

        ___`dynamic`___

        :   Scoped in a function, which might not be executed on module load

        ___`conditional`___

        :   In an if-block at the top-level of the module, so only maybe executed

        ___`parent`___

        :   Due to the module in question being a parent of the current module (in python,
            parent modules are imported before their children)

        If a module is imported multiple times in different ways, all their metadata is
        aggregated on the same entry.

        Once this method was executed, the [`Module.modules`][byecycle.graph.Module.modules]
        class-method can be called to produce all created modules.

        Note:
            Since `populate` takes place at the class-level, calling this funtion multiple
            times will clear the data from a previous call.

        Args:
            source_path: Location of the source tree of the package that should be walked.
                The `.name` attribute of this parameter is assumed to be the name of the
                package in order to identify which imports are local imports.
        """
        cls.reset()
        node_data: dict[Module, list[tuple[str, ImportKind]]] = {}
        package_name = source_path.name

        # walk the project, compile all python files, collect their import statements
        for path in source_path.rglob("*"):
            if not path.name.endswith(".py"):
                continue
            name = path_to_module_name(str(path), str(source_path), package_name)

            with open(path) as f:
                ast_ = ast.parse(f.read())

            # add a link to parent modules to make `Module.add_parent_imports` work
            # and a link to their assumed module path to resolve imports
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
            node_data[cls(name)] = [
                (m, t) for m, t in visitor.imports if m.startswith(package_name)
            ]
        cls.add_parent_imports()

        # add all found imports to their respective module
        for module, imports in node_data.items():
            for import_, kind in imports:
                module.add(import_, kind)


class ImportVisitor(ast.NodeVisitor):
    """Collect import statements in a module and assign them an [`ImportKind`][byecycle.misc.ImportKind] category.

    Relies on a non-standard `_parent` field being present in each node which contains
    a link to its parent node.
    """

    def __init__(self):
        self.imports: list[tuple[str, ImportKind]] = []

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
                    # test if the import happens somewhere in a function
                    if isinstance(parent, (ast.FunctionDef, ast.AsyncFunctionDef)):
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
            self.imports.append((alias.name, kind))

    def visit_ImportFrom(self, node: ast.ImportFrom):
        kind = self.find_import_kind(node)
        # handle relative imports
        if node.level:
            path = node._module[: -node.level]  # type: ignore[attr-defined]
            if node.module:
                path.append(node.module)
            module = ".".join(path)
        else:
            assert node.module is not None  # iff None when node.level > 0 # nosec
            module = node.module

        for alias in node.names:
            self.imports.append((f"{module}.{alias.name}", kind))


def build_digraph(modules: list[Module], **kwargs: Unpack[SeverityMap]) -> nx.DiGraph:
    """Turns a module-imports-mapping into a smart graph object.

    Args:
        modules: [`Module`][byecycle.graph.Module] objects that know what other local
            modules they import, and how.
        **kwargs: Override the default settings for the severity of the "how" when imports
            in local modules might cause import cycles.

    Returns:
        A graph object which allows the kind of operations that you'd want when working
        with graph-like structures. Every edge in the graph has a `tags` and a `cycle`
        entry (accessible with `getitem()`) holding metadata that can help interpret how
        much of an issue a particular cyclic import might be.
    """
    g = nx.DiGraph()
    g.add_nodes_from([m.name for m in modules])
    for module in modules:
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
