# Installation

You will need a version of python 3 installed on your machine. If you need help getting this installed, please consult the [Python documentation](https://www.python.org/downloads/).

## Setting up a virtual environment

### Mac

Begin by opening a terminal in the root directory and creating a virtual environment:

```
python3 -m venv venv
```

You'll notice that this creates a `venv` folder in the root directory. Anytime you want to work on or test this project, begin by running `source venv/bin/activate`.

### Windows

Consult [this link](https://mothergeo-py.readthedocs.io/en/latest/development/how-to/venv-win.html#where-is-python) to set up a virtual environment. You may also choose to use a similar but easier virtual enviroment solution such as micromamba or anaconda. This is fine.

## Install the dependencies

Simply run `pip install -r requirements.txt`.
