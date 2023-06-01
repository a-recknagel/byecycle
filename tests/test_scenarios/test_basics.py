import json
import subprocess
import sys


def test_version(cli):
    result = cli("--version")

    assert "version: " in result.output


def test_package_no_imports(cli, pip):
    pip(
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
        }
    )

    result = cli("foo")

    assert result.exit_code == 0
    assert result.json == {
        "foo": {},
        "foo.bar": {"foo": {"cycle": None, "tags": ["parent"]}},
        "foo.baz": {"foo": {"cycle": None, "tags": ["parent"]}},
        "foo.baz.qux": {"foo.baz": {"cycle": None, "tags": ["parent"]}},
        "foo.baz.quux": {"foo.baz": {"cycle": None, "tags": ["parent"]}},
    }


def test_package_with_imports(cli, pip):
    pip(
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
        }
    )

    result = cli("foo")

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


def test_package_with_relative_imports(cli, pip):
    pip(
        {
            "foo": {
                "__init__": "from . import bar",
                "bar": "from .baz import qux",
                "baz": {
                    "__init__": "",
                    "qux": "from .quux import x",
                    "quux": "x = 1",
                    "quuux": "from ..foo.quux import x",
                },
            }
        }
    )

    result = cli("foo")

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
            "foo": {"cycle": None, "tags": ["vanilla"]},
            "foo.baz": {"cycle": None, "tags": ["parent"]},
        },
    }


def test_source_tree_no_imports(cli, pip):
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

    result = cli(source)

    assert result.exit_code == 0
    assert result.json == {
        "foo": {},
        "foo.bar": {"foo": {"cycle": None, "tags": ["parent"]}},
        "foo.baz": {"foo": {"cycle": None, "tags": ["parent"]}},
        "foo.baz.qux": {"foo.baz": {"cycle": None, "tags": ["parent"]}},
        "foo.baz.quux": {"foo.baz": {"cycle": None, "tags": ["parent"]}},
    }


def test_source_tree_with_imports(cli, pip):
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
        install=False,
    )

    result = cli(source)

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


def test_source_tree_with_relative_imports(cli, pip):
    source = pip(
        {
            "foo": {
                "__init__": "from . import bar",
                "bar": "from .baz import qux",
                "baz": {
                    "__init__": "",
                    "qux": "from .quux import x",
                    "quux": "x = 1",
                    "quuux": "from ..foo.quux import x",
                },
            }
        },
        install=False,
    )

    result = cli(source)

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
            "foo": {"cycle": None, "tags": ["vanilla"]},
            "foo.baz": {"cycle": None, "tags": ["parent"]},
        },
    }


def test_package_vanilla_cycle(cli, pip):
    pip(
        {
            "foo": {
                "__init__": "",
                "bar": "import foo.baz",
                "baz": "import foo.bar",
            },
        }
    )

    result = cli("foo")

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


def test_package_typing_cycle(cli, pip):
    pip(
        {
            "foo": {
                "__init__": "",
                "bar": (
                    "import typing\n" "if typing.TYPE_CHECKING:\n" "   import foo.baz"
                ),
                "baz": "import foo.bar",
            },
        }
    )
    result = cli("foo")

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


def test_package_conditional_cycle(cli, pip):
    pip(
        {
            "foo": {
                "__init__": "",
                "bar": (
                    "import sys\n" "if sys.version >= (3, 10, 0):\n" "   import foo.baz"
                ),
                "baz": "import foo.bar",
            },
        }
    )
    result = cli("foo")

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


def test_package_dynamic_cycle(cli, pip):
    pip(
        {
            "foo": {
                "__init__": "",
                "bar": ("def qux():\n" "   import foo.baz"),
                "baz": "import foo.bar",
            },
        }
    )
    result = cli("foo")

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


def test_package_class_scope_is_toplevel_cycle(cli, pip):
    pip(
        {
            "foo": {
                "__init__": "",
                "bar": ("class Qux:\n" "   import foo.baz"),
                "baz": "import foo.bar",
            },
        }
    )
    result = cli("foo")

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


def test_package_does_not_exist(cli):
    result = cli("foo")

    assert result.exit_code == 1
    assert "Failed trying to resolve project='foo'" in result.exception.args[0]


def test_package_print_plain(cli, pip):
    pip(
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
        }
    )

    result = cli("foo", "--no-rich")

    assert result.exit_code == 0
    assert result.json == {
        "foo": {},
        "foo.bar": {"foo": {"cycle": None, "tags": ["parent"]}},
        "foo.baz": {"foo": {"cycle": None, "tags": ["parent"]}},
        "foo.baz.qux": {"foo.baz": {"cycle": None, "tags": ["parent"]}},
        "foo.baz.quux": {"foo.baz": {"cycle": None, "tags": ["parent"]}},
    }


def test_source_tree_byecycle_as_subprocess_module(pip):
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
        }
    )

    result = subprocess.run(
        [sys.executable, "-m", "byecycle", source], capture_output=True
    )

    assert json.loads(result.stdout) == {
        "foo": {},
        "foo.bar": {"foo": {"cycle": None, "tags": ["parent"]}},
        "foo.baz": {"foo": {"cycle": None, "tags": ["parent"]}},
        "foo.baz.qux": {"foo.baz": {"cycle": None, "tags": ["parent"]}},
        "foo.baz.quux": {"foo.baz": {"cycle": None, "tags": ["parent"]}},
    }
