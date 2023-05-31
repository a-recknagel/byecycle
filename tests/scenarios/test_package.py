def test_simple_self(cli):
    result = cli("byecycle")

    assert result.exit_code == 0
    assert "byecycle" in result.json()

foo = {
    "__init__": "",
    "bar": "",
    "baz": {
        "__init__": "",
        "qux": "",
        "quux": "",
    }
}


def test_foo(cli, pip):
    pip(foo=foo)
    import sys
    import foo as _
