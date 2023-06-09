import pytest

from byecycle.graph import Module


@pytest.mark.parametrize(
    "func, expected",
    [
        (str, "{foo -> foo.bar, foo.baz}"),
        (repr, "Module('foo')"),
    ],
)
def test_module_representation(func, expected):
    foo = Module("foo", None)
    Module("foo.bar", foo)
    Module("foo.baz", foo)
    foo.add_import({"module": "foo", "name": "bar"}, "vanilla", foo)
    foo.add_import({"module": "foo", "name": "baz"}, "vanilla", foo)

    assert func(foo) == expected


def test_module_adding_first_party_imports():
    foo = Module("foo", None)
    Module("foo.bar", foo)

    foo.add_import({"module": "foo.bar", "name": None}, "vanilla", foo)

    assert foo.imports["foo.bar"]


def test_module_adding_first_party_imports_from_finds_if_module_exists():
    foo = Module("foo", None)
    Module("foo.bar", foo)

    foo.add_import({"module": "foo", "name": "bar"}, "vanilla", foo)

    assert foo.imports["foo.bar"]


def test_module_adding_first_party_imports_from_skips_name_if_it_is_not_a_module():
    foo = Module("foo", None)

    foo.add_import({"module": "foo", "name": "bar"}, "vanilla", foo)

    assert foo.imports["foo"]
    assert not foo.imports["foo.bar"]


def test_module_adding_unregistered_first_party_imports_crashes():
    foo = Module("foo", None)

    with pytest.raises(KeyError, match="foo.bar"):
        foo.add_import({"module": "foo.bar", "name": None}, "vanilla", foo)


def test_module_adding_second_party_imports_crashes():
    foo = Module("foo", None)

    with pytest.raises(KeyError, match="os"):
        foo.add_import({"module": "os", "name": None}, "vanilla", foo)


def test_module_adding_third_party_imports_crashes():
    foo = Module("foo", None)

    with pytest.raises(KeyError, match=r"bar"):
        foo.add_import({"module": "bar", "name": None}, "vanilla", foo)
