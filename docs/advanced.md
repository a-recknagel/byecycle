## Intended Usage

### Packaging a Wild Growth of Scripts
IDEs like spyder do a lot to Just Make Things Work with respect to imports, even if
strictly speaking they shouldn't due to cycles or incorrect structuring. As a consequence,
a loose collection of scripts can grow in complexity to such a degree that untangling it
into something that is executable _without_ the help of an IDE and its import-and-pathing
magic turns into a major headache. Especially if things only break sometimes and/or not 
immediately.

Running `byecycle` on the top-level intended as the package root should give you something
to iterate quickly with during debugging.

### Custom Tooling
The output of the non-visualizing portion of this project is intended to be easy to 
integrate into other tools. Be it linters, other types of visualizers, static import 
solvers, or whatever else can make use of this kind of information.

## Limitations

### Python is Dynamic
This tool does not actually run the code it analyzes. That is good, because

 - import cycles crash a runner immediately, stopping you from mapping the full import
   graph
 - running all executable lines of code can be slow, or downright impossible
 - code can have a wide range of hard-to-fulfill runtime dependencies on its environment
   -- config files, databases, third party or os packages, etc.
 - other issues with the code (except for `SyntaxError`s) don't mess with this specific
   task

On the other hand,

 - dynamic imports are not recognized, only bare `import` or `import from` statements 
   count
 - "dead code" can't be ignored (might be good, might be bad)
 - hunting down all edge cases of modelling python's import mechanism correctly is a 
   sisyphean task

### There Should Be One-- and Preferably Only One --Obvious Way to [Package Code]
Talking about edge cases `byecycle` will have a hard time working with your code if

 - you use [namespaces](https://peps.python.org/pep-0420/)
 - your package's name [differs](https://pypi.org/project/beautifulsoup4/) from your 
   distribution's name
 - you have a distribution that installs multiple packages (ever wondered where 
   `pkg_resources` is from? Funny coincidence with who is in charge if it right now)
 - you use any other fun and interesting ways to package your code that I'm not aware of

That being said, current best practices should be covered. But if you find something, [bug
tickets are welcome](https://github.com/a-recknagel/byecycle/issues/new/choose)!

## Tooling

This project uses a few tools to help during development. If you have a working 
development setup, all of them should be installed and configured already.

A good reference for development setup debugging is to take a look at the [github-actions
workflow](https://github.com/a-recknagel/byecycle/actions/workflows/pipeline.yml). It
performs a development setup and runs all the tools, so if you can repeat the steps taken
there you should receive the same result.

It's a good idea to run all these tools and fix any issues that they report before
committing new code, as a failing pipeline blocks a PR from getting accepted.

### Autoformatters
Straight forward, just run them and they'll fix formatting issues.

```shell
isort src/ tests/
black src/ tests/
```

### Type Checks
Fixing type errors can be tricky, don't be afraid to ask for help if you get stuck.

```shell
mypy src/
```

### Test Suite
Tests are invaluable for debugging. 
```shell
pytest tests/
```
Optionally with a coverage report.
```shell
pytest tests/ --cov
```
