# Development

Install the package in a virtual environment with `python -m pip install -e .`.

Run `python -m unittest discover -s tests -v`. Pure Python tests cover synthetic camera recovery, bad geometry, image normalization, server handoff, and CLI errors. When Blender is on PATH (or `STAGECRAFT_TEST_BLENDER` names its executable), the integration test exports a real `.blend`, reopens it in Blender, and checks primitive counts, reference packing, and image-space projections.

Run `node --test tests/test_session.cjs` with Node.js 22 or newer to check the production session gate and browser script syntax. CI runs these checks. They do not exercise DOM events or replace the browser check below.

The browser UI can be checked with `stagecraft align --root ROOT --project NAME --scene NAME`. Test pointer dragging, keyboard movement, reset, invalid save, repeated valid saves, page reload, Finish alignment session, and resume. Confirm the active project and paths are visible. The server binds only loopback, uses a random session path, checks Host and Origin, limits POST body size, and serves fixed resources. It is a local interactive helper, not a public web service.
