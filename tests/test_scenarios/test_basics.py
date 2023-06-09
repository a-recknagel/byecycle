import json
import subprocess
import sys

import pytest


def test_version(cli):
    result = cli("--version")

    assert "version: " in result.output


@pytest.mark.parametrize(
    "install", [pytest.param(True, id="package"), pytest.param(False, id="source tree")]
)
class TestMainEntrypoint:
    def test_no_imports(self, cli, pip, install):
        source = pip(
            {
                "foo": {
                    "__init__": "",
                    "bar": "",
                    "baz": {
                        "__init__": "",
                        "qux": "",
                        "quux": "",
                    },
                }
            },
            install=install,
        )

        result = cli("foo" if install else source)

        assert result.exit_code == 0
        assert result.json == {
            "foo": {},
            "foo.bar": {"foo": {"cycle": None, "tags": ["parent"]}},
            "foo.baz": {"foo": {"cycle": None, "tags": ["parent"]}},
            "foo.baz.qux": {"foo.baz": {"cycle": None, "tags": ["parent"]}},
            "foo.baz.quux": {"foo.baz": {"cycle": None, "tags": ["parent"]}},
        }

    def test_imports(self, cli, pip, install):
        source = pip(
            {
                "foo": {
                    "__init__": "import foo.bar",
                    "bar": "import foo.baz.qux",
                    "baz": {
                        "__init__": "",
                        "qux": "import foo.baz.quux",
                        "quux": "x = 1",
                    },
                }
            },
            install=install,
        )

        result = cli("foo" if install else source)

        assert result.exit_code == 0
        assert result.json == {
            "foo": {"foo.bar": {"cycle": "complicated", "tags": ["vanilla"]}},
            "foo.bar": {
                "foo": {"cycle": "complicated", "tags": ["parent"]},
                "foo.baz.qux": {"cycle": None, "tags": ["vanilla"]},
            },
            "foo.baz": {"foo": {"cycle": None, "tags": ["parent"]}},
            "foo.baz.qux": {
                "foo.baz": {"cycle": None, "tags": ["parent"]},
                "foo.baz.quux": {"cycle": None, "tags": ["vanilla"]},
            },
            "foo.baz.quux": {"foo.baz": {"cycle": None, "tags": ["parent"]}},
        }

    def test_imports_from(self, cli, pip, install):
        source = pip(
            {
                "foo": {
                    "__init__": "from foo import bar",
                    "bar": "from foo.baz import qux",
                    "baz": {
                        "__init__": "",
                        "qux": "from foo.baz.quux import x",
                        "quux": "x = 1",
                    },
                }
            },
            install=install,
        )

        result = cli("foo" if install else source)

        assert result.exit_code == 0
        assert result.json == {
            "foo": {"foo.bar": {"cycle": "complicated", "tags": ["vanilla"]}},
            "foo.bar": {
                "foo": {"cycle": "complicated", "tags": ["parent"]},
                "foo.baz.qux": {"cycle": None, "tags": ["vanilla"]},
            },
            "foo.baz": {"foo": {"cycle": None, "tags": ["parent"]}},
            "foo.baz.qux": {
                "foo.baz": {"cycle": None, "tags": ["parent"]},
                "foo.baz.quux": {"cycle": None, "tags": ["vanilla"]},
            },
            "foo.baz.quux": {"foo.baz": {"cycle": None, "tags": ["parent"]}},
        }

    def test_relative_imports_from(self, cli, pip, install):
        source = pip(
            {
                "foo": {
                    "__init__": "from . import bar",
                    "bar": "from .baz import qux",
                    "baz": {
                        "__init__": "",
                        "qux": "from .quux import x",
                        "quux": "x = 1",
                        "quuux": "from ..baz.quux import x",
                    },
                }
            },
            install=install,
        )

        result = cli("foo" if install else source)

        assert result.exit_code == 0
        assert result.json == {
            "foo": {"foo.bar": {"cycle": "complicated", "tags": ["vanilla"]}},
            "foo.bar": {
                "foo": {"cycle": "complicated", "tags": ["parent"]},
                "foo.baz.qux": {"cycle": None, "tags": ["vanilla"]},
            },
            "foo.baz": {"foo": {"cycle": None, "tags": ["parent"]}},
            "foo.baz.qux": {
                "foo.baz": {"cycle": None, "tags": ["parent"]},
                "foo.baz.quux": {"cycle": None, "tags": ["vanilla"]},
            },
            "foo.baz.quux": {"foo.baz": {"cycle": None, "tags": ["parent"]}},
            "foo.baz.quuux": {
                "foo.baz": {"cycle": None, "tags": ["parent"]},
                "foo.baz.quux": {"cycle": None, "tags": ["vanilla"]},
            },
        }

    def test_vanilla_cycle(self, cli, pip, install):
        source = pip(
            {
                "foo": {
                    "__init__": "",
                    "bar": "import foo.baz",
                    "baz": "import foo.bar",
                },
            },
            install=install,
        )

        result = cli("foo" if install else source)

        assert result.exit_code == 0
        assert result.json == {
            "foo": {},
            "foo.bar": {
                "foo": {"cycle": None, "tags": ["parent"]},
                "foo.baz": {"cycle": "bad", "tags": ["vanilla"]},
            },
            "foo.baz": {
                "foo": {"cycle": None, "tags": ["parent"]},
                "foo.bar": {"cycle": "bad", "tags": ["vanilla"]},
            },
        }

    def test_typing_cycle(self, cli, pip, install):
        source = pip(
            {
                "foo": {
                    "__init__": "",
                    "bar": (
                        "import typing\n" "if typing.TYPE_CHECKING:\n" "   import foo.baz"
                    ),
                    "baz": "import foo.bar",
                },
            },
            install=install,
        )

        result = cli("foo" if install else source)

        assert result.exit_code == 0
        assert result.json == {
            "foo": {},
            "foo.bar": {
                "foo": {"cycle": None, "tags": ["parent"]},
                "foo.baz": {"cycle": "skip", "tags": ["typing"]},
            },
            "foo.baz": {
                "foo": {"cycle": None, "tags": ["parent"]},
                "foo.bar": {"cycle": "skip", "tags": ["vanilla"]},
            },
        }

    def test_conditional_cycle(self, cli, pip, install):
        source = pip(
            {
                "foo": {
                    "__init__": "",
                    "bar": (
                        "import sys\n"
                        "if sys.version >= (3, 10, 0):\n"
                        "   import foo.baz"
                    ),
                    "baz": "import foo.bar",
                },
            },
            install=install,
        )

        result = cli("foo" if install else source)

        assert result.exit_code == 0
        assert result.json == {
            "foo": {},
            "foo.bar": {
                "foo": {"cycle": None, "tags": ["parent"]},
                "foo.baz": {"cycle": "complicated", "tags": ["conditional"]},
            },
            "foo.baz": {
                "foo": {"cycle": None, "tags": ["parent"]},
                "foo.bar": {"cycle": "complicated", "tags": ["vanilla"]},
            },
        }

    def test_dynamic_cycle(self, cli, pip, install):
        source = pip(
            {
                "foo": {
                    "__init__": "",
                    "bar": ("def qux():\n" "   import foo.baz"),
                    "baz": "import foo.bar",
                },
            },
            install=install,
        )

        result = cli("foo" if install else source)

        assert result.exit_code == 0
        assert result.json == {
            "foo": {},
            "foo.bar": {
                "foo": {"cycle": None, "tags": ["parent"]},
                "foo.baz": {"cycle": "complicated", "tags": ["dynamic"]},
            },
            "foo.baz": {
                "foo": {"cycle": None, "tags": ["parent"]},
                "foo.bar": {"cycle": "complicated", "tags": ["vanilla"]},
            },
        }

    def test_class_scope_is_toplevel_cycle(self, cli, pip, install):
        source = pip(
            {
                "foo": {
                    "__init__": "",
                    "bar": ("class Qux:\n" "   import foo.baz"),
                    "baz": "import foo.bar",
                },
            },
            install=install,
        )

        result = cli("foo" if install else source)

        assert result.exit_code == 0
        assert result.json == {
            "foo": {},
            "foo.bar": {
                "foo": {"cycle": None, "tags": ["parent"]},
                "foo.baz": {"cycle": "bad", "tags": ["vanilla"]},
            },
            "foo.baz": {
                "foo": {"cycle": None, "tags": ["parent"]},
                "foo.bar": {"cycle": "bad", "tags": ["vanilla"]},
            },
        }

    def test_print_plain(self, cli, pip, install):
        source = pip(
            {
                "foo": {
                    "__init__": "",
                    "bar": "",
                    "baz": {
                        "__init__": "",
                        "qux": "",
                        "quux": "",
                    },
                }
            },
            install=install,
        )

        result = cli("foo" if install else source, "--no-rich")

        assert result.exit_code == 0
        assert result.json == {
            "foo": {},
            "foo.bar": {"foo": {"cycle": None, "tags": ["parent"]}},
            "foo.baz": {"foo": {"cycle": None, "tags": ["parent"]}},
            "foo.baz.qux": {"foo.baz": {"cycle": None, "tags": ["parent"]}},
            "foo.baz.quux": {"foo.baz": {"cycle": None, "tags": ["parent"]}},
        }


def test_byecycle_as_subprocess_module(pip):
    source = pip(
        {
            "foo": {
                "__init__": "",
                "bar": "",
                "baz": {
                    "__init__": "",
                    "qux": "",
                    "quux": "",
                },
            }
        },
        install=False,
    )

    result = subprocess.run(
        [sys.executable, "-m", "byecycle", source],
        capture_output=True,
    )

    assert result.returncode == 0
    assert json.loads(result.stdout) == {
        "foo": {},
        "foo.bar": {"foo": {"cycle": None, "tags": ["parent"]}},
        "foo.baz": {"foo": {"cycle": None, "tags": ["parent"]}},
        "foo.baz.qux": {"foo.baz": {"cycle": None, "tags": ["parent"]}},
        "foo.baz.quux": {"foo.baz": {"cycle": None, "tags": ["parent"]}},
    }


def test_package_not_installed(cli):
    result = cli("foo")

    assert result.exit_code == 1
    assert "Failed trying to resolve project" in result.exception.args[0]


@pytest.mark.parametrize("path", ["/foo", "./foo", "/home/dev/foo"])
def test_path_not_found(cli, path):
    result = cli(path)

    assert result.exit_code == 1
    assert "Failed trying to resolve project" in result.exception.args[0]
