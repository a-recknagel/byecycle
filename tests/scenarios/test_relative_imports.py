def test_absolute_imports(cli):
    result = cli("byecycle")

    assert result.exit_code == 0
    assert "byecycle" in result.json()
