# DevTime v0.1.1 - pipx demo onboarding

An onboarding-focused release. It makes the PyPI/pipx install path the primary way to
try DevTime and adds a one-command demo. No changes to concept detection, risk review,
or scanner behavior.

## Highlights

- **Install from PyPI**: the public distribution is `devtime-ei`
  (`pipx install devtime-ei`). The name `devtime` is reserved on PyPI, so `devtime-ei`
  is the intended public distribution name.
- **New: `dtc demo init`**: copies a small static example repo into
  `./devtime-demo-saas`, so you can try DevTime right after installing from PyPI
  without cloning this repository.
- **New: `dtc demo init --force`**: replaces an existing `./devtime-demo-saas` copy.
- **Docs**: README and QUICKSTART now start from `pipx install devtime-ei` followed by
  `dtc demo init`, with the source install kept as an alternative.

## Names

- The PyPI distribution is `devtime-ei`.
- The Python import package remains `devtime`.
- The CLI command remains `dtc`.

## Try it

```bash
pipx install devtime-ei
dtc demo init
cd devtime-demo-saas
dtc init
dtc scan
dtc concepts
dtc explain "Billing Webhooks"
```

## Safety and scope

- `dtc demo init` only copies static files into the current working directory. It does
  not execute code, install anything, run tests or migrations, or make network calls.
- No changes to concept detection, risk review, or scanner behavior.
- No cloud, no telemetry, no AI, no network behavior added.

## Notes

- The bundled demo ships inside the wheel as package data
  (`devtime/resources/demo-saas/`); the source tree still keeps `examples/demo-saas`
  for source installs.
- Tests added for the demo command and the copied-demo scan flow (97 passing).
