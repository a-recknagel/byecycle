import shutil
import signal
import site
import sys
import tempfile
from functools import cached_property
from json import loads as json_loads
from pathlib import Path
from typing import Literal

import pytest
from typer.testing import CliRunner, Result

from byecycle.cli import cli as byecli

_runner = CliRunner(mix_stderr=False)


class JsonResult(Result):
    @cached_property
    def json(self, source: Literal["stdout", "stderr"] = "stdout"):
        return json_loads(getattr(self, source))


@pytest.fixture
def cli():
    """Cli runner."""

    def call(*args, **kwargs) -> JsonResult:
        result = _runner.invoke(byecli, args=args, **kwargs)
        return JsonResult(**vars(result))

    return call


@pytest.fixture
def pip():
    """Not actually pip.

    But for testing purposes it's close enough.
    """
    old_modules = sys.modules.copy()
    old_path = sys.path.copy()
    tmp_dir: tempfile.TemporaryDirectory | None = None

    def pseudo_installer(source: dict, *, install=True) -> str:
        def files_from_dict(path: Path, files: dict[str, str | dict]):
            for file_name, file_content in files.items():
                if isinstance(file_content, str):
                    with open(path / f"{file_name}.py", "w") as f:
                        f.write(file_content)
                elif isinstance(file_content, dict):
                    package = path / file_name
                    package.mkdir()
                    files_from_dict(package, file_content)
                else:
                    raise RuntimeError(
                        f"Bad format for {files=}, keys should be valid module names "
                        f"and values should be python file contents or a recursion."
                    )

        nonlocal tmp_dir

        # create source trees
        if len(source) != 1:
            raise RuntimeError("Exactly one top-level import-package required.")
        name = [*source][0]
        tmp_dir = tempfile.TemporaryDirectory(prefix=f"{name}_")
        files_from_dict(Path(tmp_dir.name), source)

        if install:
            sys.path.append(tmp_dir.name)

        return str(Path(tmp_dir.name) / name)

    try:
        yield pseudo_installer
    finally:
        # cleanup of tmp files
        if tmp_dir:
            tmp_dir.cleanup()

    # restoring system
    sys.modules = old_modules
    sys.path = old_path


@pytest.fixture(scope="session", autouse=True)
def termination_handler():
    """Sends a SIGINT in case SIGTERM was sent to the current process.

    By default, fixture cleanup won't run on SIGTERM, which is unfortunately the default
    signal pycharm uses when trying to stop a process. See
    https://github.com/pytest-dev/pytest/issues/9142 for details and the origin of this
    snippet. Praise be asottile, what would we do without you.
    """
    orig = signal.signal(signal.SIGTERM, signal.getsignal(signal.SIGINT))
    yield
    signal.signal(signal.SIGTERM, orig)
