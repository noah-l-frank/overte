# C++ Documentation Generation

[Doxygen](https://www.doxygen.nl/) is used for generating documentation on parts of the C++ code.


## Prerequisites

**Doxygen** &ge; 1.9.1 - https://www.doxygen.nl/

If you want to run Doxygen from a command prompt, add the Doxygen install's `/bin` directory to your system PATH.


## Documenting

See section 4.3.6 of the [*Coding Standard*](../../CODING_STANDARD.md).


## Running

### Using the Doxywizard GUI

In the Doxywizard program:
- File > Open `/tools/doxygen/Doxyfile`.
- Set a separate `OUTPUT_DIRECTORY`, such as `../../build/doxygen`, then use the
"Run" tab and click "Run Doxygen".
- Once it has compiled the documentation (this may take a while), click "Show HTML Output" to view the documentation generated.

### From a command prompt

Change to the repository's `tools/doxygen` directory. The retained `Doxyfile`
default writes into `build/docs/html`, which is also the Sphinx portal's output.
Use a private configuration copy and set its `OUTPUT_DIRECTORY` to
`../../build/doxygen` before generating C++ documentation, so the two sites do
not overwrite each other. Relative input paths are resolved from this directory.

```
doxygen /path/to/your-local-Doxyfile
```

With the separate output setting above, open `build/doxygen/html/index.html`
from the repository root. This C++ API site is separate from the
[developer portal](../../docs/portal/maintaining.md) and the JSDoc output.

### Tips

- The source code directory listed in the "Wizard" tab is only one of the directories scanned. For the full list, see the
"Expert" tab's input category's settings.
- The output directory is **not** wiped each time you run Doxygen, so you may want to periodically clear it out if you're
finding it contains old, unwanted files.
- If you want to iterate on a particular part of the documentation, you can temporarily change the "Source code directory"
option in the "Wizard" tab of the Doxywizard program.


## Altering the Doxygen configuration

This is most easily accomplished by using the Doxyfile GUI and using it to write a new `Doxyfile` file.
Alternatively, you can edit the `Doxyfile` configuration file in a text editor.


## References

- [Doxygen Website](https://www.doxygen.nl/)
- [Doxygen Tutorial](https://embeddedinventor.com/doxygen-tutorial-getting-started-using-doxygen-on-windows/)
- [Complete Guide On Using Doxygen](https://embeddedinventor.com/guide-to-configure-doxygen-to-document-c-source-code-for-beginners/)
