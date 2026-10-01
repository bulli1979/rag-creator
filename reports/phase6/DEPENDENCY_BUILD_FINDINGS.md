# Clean-build gate — not passed

The declared dependency Dockerfile was built with `--pull --no-cache` on this
aarch64 host. Fresh stages plus the final application COPY produce
`notbot-phase6:clean-final-20261001`, image
`sha256:e12b11d560f34b89883de1170ae1ccf847e6edfdea72c6321673648a7da54ff5`.
Base: `python:3.12-slim-bookworm`, resolved digest
`sha256:392307d22300de8b5986851a12d9176dfc0fc073e65bf6523ebd7dcbeb23564e`.

`pip check` fails with:

```
nvidia-cusparselt-cu13 0.8.1 is not supported on this platform
```

Installed wheel metadata has tag `py3-none-manylinux2014_sbsa`, despite an
aarch64 wheel filename. The same version/tag is present in the retained working
image. This is an observed platform-tag inconsistency, not proof of a broken GPU.
Do not edit wheel metadata or suppress the check to make acceptance green.

What does pass:

- Critical imports including torch, SentenceTransformer, unstructured, psycopg2
  and the API (`clean-build.json`).
- 119 offline fixtures at the time of that clean-image run
  (`clean-fixtures.json`; the final working-image run includes the subsequently
  added runtime-pointer harness test, 120/120).
- Basic CUDA matrix multiplication, torch 2.14.1+cu130 (`clean-cuda-smoke.json`).
- Isolated restored-v9 API health, embeddings and three cited instrument smokes
  (`clean-build-restore.json`). This is not the final-v10 restore receipt.

Resolved package versions are recorded in `clean-build.json`. Floating ranges
resolved differently from the working image, including torch 2.14.1 versus 2.14.0
and markdownify 1.2.3 versus 1.2.2. A passing fresh build today would not by itself
prove reproducibility on another date.

The clean dependency image was NOT promoted. The local testing API runs final
application code layered over the retained working dependencies:
`observatory-document-api:phase6-final-20261001`, image
`sha256:999eefe41c1c724b2e56c8671a6edb6dd63882f1fe1cba9aaa339d262ffe3787`.
Its exact final-v10 full restore passes separately (`final-restore.json`).

Before release: establish a supported ARM/GPU dependency lock or resolve the
upstream wheel-tag problem, then repeat package consistency, imports, GPU tests,
full fixtures and acceptance on that exact image. Neither basic CUDA execution
nor the API smokes close the package-consistency gate.
