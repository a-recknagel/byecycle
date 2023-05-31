from json import loads
from typing import Literal
import sys
import tempfile
from pathlib import Path
import os

from typer.testing import CliRunner
import pytest
from click.testing import Result
from pip._internal.cli.main import main as pip_cli

from byecycle.cli import cli as byecli


_runner = CliRunner(mix_stderr=False)

class JsonResult(Result):
    def json(self, source: Literal["stdout", "stderr"] = "stdout"):
        return loads(getattr(self, source))
@pytest.fixture
def cli():
    def call(*args, **kwargs) -> JsonResult:
        result = _runner.invoke(byecli, args=args, **kwargs)
        return JsonResult(**vars(result))

    return call


PYPROJECT_TEMPLATE = """\
[project]
name = "{name}"
version = "0.0.0.dev0"
[build-system]
build-backend = "setuptools.build_meta"
requires = ["setuptools"]
"""
@pytest.fixture
def pip():
    old_modules = sys.modules.copy()
    tmp_dirs: dict[str, tuple[tempfile.TemporaryDirectory, str]] = {}

    def local_installer(*, install=True, **kwargs: str | dict):

        def files_from_dict(path: Path, files: dict[str, str | dict]):
            for file_name, file_content in files.items():
                if isinstance(file_content, str):
                    with open(path / f"{file_name}.py", "w") as f:
                        f.write(file_content)
                elif isinstance(file_content, dict):
                    os.mkdir(path / file_name)
                    files_from_dict(path / file_name, file_content)
                else:
                    raise RuntimeError(
                        f"Bad format for {files=}, keys should be valid module names "
                        f"and values should be python file contents or a recursion."
                    )

        # create source trees
        for name, source in kwargs.items():
            tmp_dir = tempfile.TemporaryDirectory(prefix=f"{name}_")
            base = Path(tmp_dir.name) / name
            base.mkdir()
            tmp_dirs[str(base)] = tmp_dir, name if install else ""
            files_from_dict(base, source)
            with open(base.parent / "pyproject.toml", "w") as f:
                f.write(PYPROJECT_TEMPLATE.format(name=name))

        if install:
            pip_cli(["install"] + [src.name for src, _ in tmp_dirs.values()])
        return [base for base in tmp_dirs.keys()]

    yield local_installer

    for tmp_dir, installed in tmp_dirs.values():
        tmp_dir.cleanup()
        if installed:
            pip_cli(["uninstall", "-y", installed])

    sys.modules = old_modules
