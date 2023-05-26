from __future__ import annotations

import ast
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import networkx as nx  # type: ignore

from byecycle.misc import EdgeKind, ImportKind, cycle_severity, path_to_module_name


class Module:
    """Represent a python module and the modules it imports."""

    _modules: list["Module"] = list()
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
                # when calling this function, filter with `startswith(package)`
                raise RuntimeError
        else:
            # bad parameter type
            raise RuntimeError

        self.imports[target].add(tag)

    def __hash__(self):
        return self.name.__hash__()

    def __repr__(self):
        imports = {
            k.name: v if v else "∅"
            for k, v in sorted(
                self.imports.items(), key=lambda x: x[0].name, reverse=True
            )
        }
        return f"Module('{self.name}') -> {imports}"

    @classmethod
    def modules(cls) -> Iterable["Module"]:
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
            https://discuss.python.org/t/question-understanding-imports-a-bit-better-how-are-cycles-avoided/26647/2

        Notes:
            This method can only be called once all Nodes have been initialised.
        """
        nodes: dict[str, Module] = {node.name: node for node in cls.modules()}
        for node in cls.modules():
            package = node.name.rsplit(".", 1)[0]  # only direct parent, not grandparents
            if package in nodes and package != node.name:
                node.add(nodes[package], "parent")


class ImportVisitor(ast.NodeVisitor):
    """Collect import statements in a module and assign them an `ImportKind` category.

    Relies on a non-standard `_parent` field being present in each node which contains
    a link to its parent node.
    """

    def __init__(self):
        self.imports: list[tuple[str, ImportKind]] = []

    @classmethod
    def find_import_kind(cls, node: ast.Import | ast.ImportFrom) -> ImportKind:
        parent: ast.AST = node._parent  # type: ignore[union-attr]
        match parent:
            case ast.If(
                _parent=ast.Module,  # type: ignore[misc]
                test=(ast.Name(id="TYPE_CHECKING") | ast.Attribute(attr="TYPE_CHECKING")),
            ):
                # guarded by `if typing.TYPE_CHECKING:`
                return "typing"
            case ast.If(_parent=ast.Module):  # type: ignore[misc]
                # probably guarded by `if sys.version >= (x, y, z):`, but doesn't actually
                # matter -- anything but TYPE_CHECKING is env-dependent during runtime or
                # too obtuse to consider (I'm not writing code that checks for `if True:`)
                return "conditional"
            case ast.AST(_parent=current):  # type: ignore[misc]
                while True:
                    # test if the import happens somewhere in a function
                    if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        return "dynamic"
                    try:
                        current = current._parent
                    except AttributeError:
                        # any nodes that reach this point are treated as regular toplevel
                        # imports, like imports that happen in a class body
                        return "vanilla"
            case _:
                # shouldn't happen, but just in case
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


def import_map(package: str) -> list[Module]:
    """Creates a directed graph of import statements.

    Args:
        package: Path to the source root, e.g. "/home/dev/my_lib/src/my_lib"

    Returns:
        Mapping of python module names to a list of all module names that it imports
    """
    node_data: dict[Module, list[tuple[str, ImportKind]]] = {}
    package_name = Path(package).name

    # walk the project, compile all python files, collect their import statements
    for path in Path(package).rglob("*"):
        if not path.name.endswith(".py"):
            continue
        name = path_to_module_name(str(path), package, package_name)

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
        node_data[Module(name)] = [
            (m, t) for m, t in visitor.imports if m.startswith(package_name)
        ]
    Module.add_parent_imports()

    # add all found imports to their respective module
    for module, imports in node_data.items():
        for import_, kind in imports:
            module.add(import_, kind)

    return [*Module.modules()]


def build_digraph(modules: list[Module], **kwargs: EdgeKind) -> nx.DiGraph:
    """Turns a module-imports-mapping into a smart graph object."""
    g = nx.DiGraph()
    g.add_nodes_from([m.name for m in modules])
    for module in modules:
        for import_, tags in module.imports.items():
            g.add_edge(module.name, import_.name, tags=tags)
    for e_0, e_1 in g.edges():
        if g.has_edge(e_1, e_0):
            g[e_0][e_1]["tags"] = g[e_0][e_1]["tags"] | g[e_1][e_0]["tags"]
            g[e_0][e_1]["cycle"] = cycle_severity(g[e_0][e_1]["tags"], **kwargs)
        else:
            g[e_0][e_1]["cycle"] = None
    for e_0, e_1 in g.edges():
        g[e_0][e_1]["tags"] = [*g[e_0][e_1]["tags"]]
    return g
