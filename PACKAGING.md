# Packaging and publishing DevTime

How to build the package, verify it, and (when approved) publish to TestPyPI and then
PyPI. The goal is a one-line install: `pipx install devtime-ei` (the package is named
`devtime-ei`; the command it installs is `dtc`).

> **Token safety:** never paste API tokens into commands that land in shell history if
> you can avoid it. Prefer environment variables or GitHub Secrets. Tokens must never
> be committed, written into any file, echoed, or included in logs, README, this file,
> workflows, PR text, or release notes. The expected env var names are
> `TEST_PYPI_API_TOKEN` and `PYPI_API_TOKEN`.

## Local build

```bash
python -m pip install --upgrade pip build twine
rm -rf dist build *.egg-info src/*.egg-info
python -m build
python -m twine check dist/*
```

## Wheel smoke test

macOS / Linux:

```bash
python -m venv .venv-wheel-test
source .venv-wheel-test/bin/activate
pip install dist/*.whl
dtc --help
python -c "import importlib.metadata as m; print(m.version('devtime-ei'))"
# Verify the bundled demo resource ships and works from the wheel:
dtc demo init && (cd devtime-demo-saas && dtc init && dtc scan && dtc concepts)
```

Windows PowerShell:

```powershell
python -m venv .venv-wheel-test
.venv-wheel-test\Scripts\Activate.ps1
pip install dist/*.whl
dtc --help
python -c "import importlib.metadata as m; print(m.version('devtime-ei'))"
dtc demo init; cd devtime-demo-saas; dtc init; dtc scan; dtc concepts; cd ..
```

## TestPyPI upload (only after the checks above pass)

macOS / Linux:

```bash
python -m twine upload --repository testpypi dist/* -u __token__ -p "$TEST_PYPI_API_TOKEN"
```

Windows PowerShell:

```powershell
python -m twine upload --repository testpypi dist/* -u __token__ -p $env:TEST_PYPI_API_TOKEN
```

## TestPyPI install check

macOS / Linux:

```bash
python -m venv .venv-testpypi
source .venv-testpypi/bin/activate
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple devtime-ei
dtc --help
python -c "import importlib.metadata as m; print(m.version('devtime-ei'))"
```

Windows PowerShell:

```powershell
python -m venv .venv-testpypi
.venv-testpypi\Scripts\Activate.ps1
pip install --index-url https://test.pypi.org/simple/ --extra-index-url https://pypi.org/simple devtime-ei
dtc --help
python -c "import importlib.metadata as m; print(m.version('devtime-ei'))"
```

## Real PyPI upload (separate, explicitly approved step only)

macOS / Linux:

```bash
python -m twine upload dist/* -u __token__ -p "$PYPI_API_TOKEN"
```

Windows PowerShell:

```powershell
python -m twine upload dist/* -u __token__ -p $env:PYPI_API_TOKEN
```

## After real PyPI publish, install check

```bash
pipx install devtime-ei
dtc --help
```

## Publishing via GitHub Actions

The manual workflow `.github/workflows/publish-python-package.yml`
(`workflow_dispatch`) can publish to TestPyPI or PyPI using repository secrets
`TEST_PYPI_API_TOKEN` and `PYPI_API_TOKEN`. It never runs on push or tag.
