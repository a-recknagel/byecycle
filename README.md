# byecycle 🚲

[![python](https://img.shields.io/pypi/pyversions/byecycle)](https://pdm.fming.dev)
[![pyPI](https://img.shields.io/pypi/v/byecycle)](https://pypi.org/project/byecycle)
[![docs](https://img.shields.io/badge/doc-pages-blue)](https://a-recknagel.github.io/byecycle/)
[![pdm-managed](https://img.shields.io/badge/packaging-pdm-blueviolet)](https://pdm.fming.dev)
[![license](https://img.shields.io/pypi/l/byecycle)](https://github.com/a-recknagel/byecycle/blob/main/LICENSE)
[![chat](https://img.shields.io/badge/chat-gitter-mediumturquoise)](https://matrix.to/#/#chextra:gitter.im)

Find and expose cyclic imports in python projects.

## Installation

`byecycle` uses the built-in [ast module](https://docs.python.org/3/library/ast.html#ast.parse)
to parse code files. As a consequence, it can only handle python code within the same
major version (read: no support for python 1 and 2), and the same or lower minor version
of the python interpreter it was installed with. If `byecycle` raises `SyntaxError`s in
code that you know to be working, try using a `byecycle` that is installed with the same
python version that can run the code in question.

### From PyPI
#### Requirements:
 - python 3.11 or higher
 - [pipx](https://pypa.github.io/pipx/installation/)
```shell
pipx install byecycle
```
---

### Development Setup
#### Requirements:
 - python 3.11 or higher
 - [pdm](https://pdm.fming.dev/)
 - git
```shell
git clone https://github.com/a-recknagel/byecycle.git
cd byecycle
pdm install -G:all
```

## Usage

### As a Command Line Tool

```shell
# with a path
byecycle /home/me/dev/byecycle/src/byecycle/
# or the name of an installed package
byecycle byecycle
```
The result will be a json string:

```json
{
  "byecycle.misc": {},
  "byecycle.graph": {
    "byecycle": {
      "tags": [
        "vanilla",
        "parent"
      ],
      "cycle": "complicated"
    },
    "byecycle.misc": {
      "tags": [
        "vanilla"
      ],
      "cycle": null
    }
  },
  [...]
  "byecycle": {
    "byecycle.graph": {
      "tags": [
        "vanilla",
        "parent"
      ],
      "cycle": "complicated"
    }
  }
}
```
By default, the result is printed with some rich formatting to highlight types and such.
If you need the output to be plain ascii, pass the `--no-rich` flag.

---

For bigger projects, you might get much more complex output. The intent of returning
`json` is to have something that can be easily piped into e.g. `jq` for further
processing:

```shell
# filter out imports that don't have a cycle
byecycle byecycle | jq '.[] |= (.[] |= select(.cycle != null) | select(. != {}))'
```
```json
{
  "byecycle.graph": {
    "byecycle": {
      "tags": [
        "parent",
        "vanilla"
      ],
      "cycle": "complicated"
    }
  },
  "byecycle.cli": {
    "byecycle": {
      "tags": [
        "parent",
        "vanilla"
      ],
      "cycle": "complicated"
    }
  },
  "byecycle": {
    "byecycle.graph": {
      "tags": [
        "parent",
        "vanilla"
      ],
      "cycle": "complicated"
    },
    "byecycle.cli": {
      "tags": [
        "parent",
        "vanilla"
      ],
      "cycle": "complicated"
    }
  }
}
```
Alternatively, you can also call the main entrypoint's core functionality as a regular
python function. Among other things, it returns a dictionary equivalent to the CLI's json
that you can work with:

```python
from byecycle import run
cycles, *_ = run("byecycle")
# filter out imports that don't have a cycle
for outer_k, outer_v in cycles.items():
    for inner_k, inner_v in outer_v.items():
        if inner_v["cycle"]:
            print(f"{outer_k} -> {inner_k}: {inner_v['cycle']}")
```
```text
byecycle.graph -> byecycle -> complicated
byecycle.cli -> byecycle -> complicated
byecycle -> byecycle.graph -> complicated
byecycle -> byecycle.cli -> complicated
```

---

See the help text of `byecycle` for an explanation of tags/`ImportKind`s and
cycle/`EdgeKind`s.

In short, if there is a cycle, the tags of all involved imports inform
the cycle-severity, with the highest severity winning out if multiple apply. The defaults
can be overriden in order to isolate, filter, or highlight cycles with specific 
severities.

### To Visualize the Import Graph

If you pass the `--draw` flag<sup>1</sup> on your command-line-call, `byecycle` will create an image of
the import graph instead:

```shell
byecycle byecycle --draw
```
<img src="https://github.com/a-recknagel/byecycle/assets/2063412/e5e8427c-8554-4ce5-9f9f-e2e9eca40742" alt="Plot of imports in the byecycle project" width="320" height="240">
<img src="https://github.com/a-recknagel/byecycle/assets/2063412/a00586db-e71e-4e74-94ed-0709129920b0" alt="Legend for nodes in the plot" width="320" height="240">

---
<sup>[1]</sup><sub> Requires installation of the `draw`-extra, i.e. `pipx install "byecycle[draw]"`.</sub>
