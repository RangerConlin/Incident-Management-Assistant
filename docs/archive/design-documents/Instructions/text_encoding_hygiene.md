# Text Encoding Hygiene

- All repo text files must be UTF-8 (no BOM) with LF line endings.
- Avoid pasting from Word/PDF. Paste as plain text and replace curly quotes/dashes as needed.
- Symptoms to watch for include mojibake where apostrophes, dashes, or currency symbols render as garbled multi-character sequences.
- Audit locally with `python tools/encoding_audit.py --summary`.
- CI gate: `python tools/encoding_audit.py --fail-on-find`.
- Fix approach: reopen with UTF-8 encoding, retype the affected characters, or convert the file encoding to UTF-8.
- On Windows consoles, set UTF-8 code page first when needed: `chcp 65001`.
- Install pre-commit hooks once with `pipx install pre-commit` or `pip install pre-commit`, then run `pre-commit install`.
- Run local checks with `pre-commit run --all-files`.
- Current encoding gate fails on decode errors only; once mojibake cleanup is complete, flip the hook to `--fail-kinds decode-error,mojibake,control,replacement`.
