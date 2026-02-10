# FuzzForge Modules SDK

...

# Setup 

- start the podman user socket

```shell
systemctl --user start podman.socket
```

NB : you can also automaticllay start it at boot 

```shell
systemctl --user enable --now podman.socket
```

## HACK : fix missing `fuzzforge-modules-sdk`

- if you have this error when using some fuzzforge-modules-sdk deps :

```shell
❯ make format
uv run ruff format ./src ./tests
  × No solution found when resolving dependencies:
  ╰─▶ Because fuzzforge-modules-sdk was not found in the package registry and your project depends on fuzzforge-modules-sdk==0.0.1, we can
      conclude that your project's requirements are unsatisfiable.
      And because your project requires opengrep[lints], we can conclude that your project's requirements are unsatisfiable.
make: *** [Makefile:30: format] Error 1
```

- build a wheel package of fuzzforge-modules-sdk

```shell
cd fuzzforge_ng/fuzzforge-modules/fuzzforge-modules-sdk
uv build
```

- then inside your module project, install it

```shell
cd fuzzforge_ng_modules/mymodule
uv sync --all-extras --find-links ../../fuzzforge_ng/dist/
```

# Usage

## Prepare

- enter venv (or use uv run)

```shell
source .venv/bin/activate
```

- create a new module

```shell
fuzzforge-modules-sdk new module --name my_new_module --directory ../fuzzforge_ng_modules/
```

- build the base image 

```shell
fuzzforge-modules-sdk build image
```