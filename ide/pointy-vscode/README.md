
# Pointy-lang VSCode Extension (syntax highlighting)

This minimal extension provides **syntax highlighting** for *Pointy-lang* `.pty` files.
It highlights:
- **Events** (entity names like `Extract`, `LoadDB`, `SuccessNotify`)
- **Operators** (`->`, `|->`, `||`, `*3`, `|X|`, parentheses, commas)
- **Configuration** keys (`key = value`)
- **Comments** starting with `#`

## Install locally
1. Run `vsce package`
2. Then run `code --install-extension pointy-lang-0.1.0.vsix` (or use `Extension: Install from VSIX...` in VSCode).
3. Or for development, open the folder in VSCode and press F5 to run a dev host.

## Notes
- The grammar is a TextMate grammar and intentionally conservative. You can tweak `syntaxes/pointy.tmLanguage.json` to refine tokenization.