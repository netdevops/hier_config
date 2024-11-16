Contributing
============

Fork, then clone the repo:

```
git@github.com:YOUR-USERNAME/hier_config.git
```

Install Poetry:

```
https://python-poetry.org/docs/#installation
```

Set up your environment:

```
cd hier_config
poetry install
poetry shell
```

Create a branch

```
git checkout -b YOUR-BRANCH
```

Make sure linters, type-checkers, and tests pass:

```
python scripts/build.py lint-and-test
```

Make your change. Add tests for your change. Make the linters, type-checkers, and tests pass:

```
python scripts/build.py lint-and-test
```

Push to your fork and submit a pull request.

At this point, you're waiting on us. We'll at least comment. We may suggest changes, improvements, or alternatives.

Some things that will increase the chance that your pull request is accepted:

* Write to the python style-guide (https://www.python.org/dev/peps/pep-0008/).
* Write tests.
* Write docstrings (https://www.python.org/dev/peps/pep-0257/).
* Write a good commit message.

