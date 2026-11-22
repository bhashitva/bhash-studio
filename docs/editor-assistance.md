# संपादक सहायता और भाष 0.28.0

Yantra uses compiler **0.28.0** for builds, source analysis and native debugging.
The Windows installer fetches the checksum-pinned official JAR, including its
published compression providers. Existing custom compiler paths remain selectable
under **औज़ार → औज़ार सेटिंग**.

## इंटरनेट के बिना संदर्भ

Open **सहायता → मानक पुस्तकालय खोजें…** (`Ctrl+Shift+L`) or
**सहायता → शब्द और ढाँचे खोजें…**. Search in Hindi or English, filter the topic
and entry kind, then read the signature, parameters, result, restrictions and
examples. The library catalog covers 131 types, including inherited members.
Internal compiler APIs are hidden, as in the VS Code and notebook browsers.
All 57 keywords/contextual words and 25 notebook construct templates are included.

**कोड डालें** replaces the selection in the source that opened the browser.
The first argument is selected. Press Tab for subsequent placeholders. Multiline
templates retain indentation. Ctrl+Z undoes the insertion. **उदाहरण डालें** inserts
an available example into that source. Examples may require imports, declarations
and enclosing functions described in their documentation. Neither operation
executes code. A changed source, selection or tab requires reopening the browser.
**कॉपी करें** also works while browsing without an open source file.

## कंपाइलर से सहायता

The **संपादन** menu provides compiler completion (`Ctrl+Shift+Space`), hover/type
information (`Ctrl+K`), definition (`F12`), references (`Shift+F12`), project rename
(`F2`) and quick fixes (`Ctrl+.`). Existing lightweight completion remains on
`Ctrl+Space`. Both open unsaved buffers and other project sources participate.
Rename and fixes update editable buffers. Save the changes when ready or undo
them per file. Source/version checks reject stale results before applying edits.
The compiler supplies fixes for supported diagnostics, including missing union
match cases and invalid Unicode joiners. A full JDK and the configured compiler
are required for these actions. Searchable reference data is available offline.

Editor checks now include names and types across source files. Signature help
uses the compiler to resolve overloads, nullable types and generic methods.

## रिक्त-सुरक्षा और नई भाषा सुविधाएँ

Choose **परियोजना → रिक्त-सुरक्षा परिवेश…** for `legacy` or opt-in `strict`.
This persists `nullSafety` in the project's `bhash.project` and propagates it to
editor analysis and generated web/Android projects. Existing projects default
to `legacy`. The selector retains other manifest fields.

Compiler 0.28.0 supports nullable types and safe access/coalescing, constructor
field initialization, inference, constrained generic methods, tagged unions,
exhaustive matching and typed Result/Unit. Native variable inspection accepts
runtime ABI 17 and 18. Rebuild native applications with the selected compiler.

Compression and typed C bindings follow the compiler's platform restrictions.
Android and browser targets reject C bindings. MySQL and SQL Server applications
need the external database/driver prerequisites documented by Bhash. Choosing a
new compiler does not provision a database server.

- [Null safety](https://github.com/bhashitva/bhash/tree/main/tutorial/null-safety)
- [Everyday language improvements](https://github.com/bhashitva/bhash/tree/main/tutorial/safer-everyday)
- [Compression and C bindings](https://github.com/bhashitva/bhash/tree/main/tutorial/compression)
- [Hindi book](https://github.com/bhashitva/bhash/tree/main/book)

## Reference updates

Maintainers can regenerate the bundled data with Node.js and an exact upstream
source checkout. End users need neither Node.js nor a source checkout.

```sh
node scripts/sync_reference.mjs /path/to/bhash EXACT_40_CHARACTER_COMMIT
```

The generator reuses the VS Code/Jupyter snippets and shared library models.
The bundled JSON records its source revision and compiler version.
