# Contributing

Use Python 3.11 or later. Run `python -m unittest discover -s tests -v` before submitting changes. Keep runtime dependencies optional and document prerequisites for platform tools.

Developer-facing studio UI, diagnostics, templates and tutorials must use Hindi. Reuse Bhash's existing keyword spellings. Source identifiers and contributor documentation may use English. Display IDs, URLs and version numbers as opaque values with Hindi explanations.

Treat the Hindi project files as authoritative. Keep Android generation in its adapter and make future desktop/web adapters consume shared models. Include regression tests for parsing, project recovery and code generation changes. Never commit local compiler binaries, SDKs, build output, credentials or signing keys.

Contributions are provided under Apache-2.0. Bhash compiler development belongs in https://github.com/bhashitva/bhash.
