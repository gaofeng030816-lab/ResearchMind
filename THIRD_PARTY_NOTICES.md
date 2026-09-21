# Third-party notices

ResearchMind includes a locally bundled browser build of `pdfjs-dist` 6.3.289,
the npm distribution of Mozilla PDF.js. PDF.js is Copyright Mozilla Foundation
and contributors and is licensed under the Apache License, Version 2.0.

The corresponding license text is distributed in
`src/researchmind/pdf/viewer_component/LICENSE.pdfjs.txt`. Source and project
documentation are available from https://github.com/mozilla/pdf.js and
https://mozilla.github.io/pdf.js/getting_started/.

The locked frontend dependency graph is recorded in
`src/researchmind/pdf/viewer_component/frontend/package-lock.json`. The committed
production bundle contains one JavaScript and one CSS asset and makes no external
network request while rendering a local PDF.

ResearchMind also uses the MIT-licensed Python Tree-sitter binding and the
MIT-licensed `tree-sitter-c`, `tree-sitter-java`, and `tree-sitter-julia` grammar
bindings for local, static source parsing. These packages do not execute imported
source code. Project documentation and license information are available from:

- https://github.com/tree-sitter/py-tree-sitter
- https://github.com/tree-sitter/tree-sitter-c
- https://github.com/tree-sitter/tree-sitter-java
- https://github.com/tree-sitter/tree-sitter-julia

Other direct Python runtime dependencies are installed separately by the package
manager rather than copied into the ResearchMind wheel. Their published licenses are:

- `openai`: Apache-2.0;
- `streamlit`: Apache-2.0;
- `python-dotenv`: BSD-3-Clause;
- `PyMuPDF`: dual licensed under AGPL-3.0 or an Artifex commercial license.

The current V3 candidate is for local internal acceptance only. Before any public
distribution, the project must select and document a PyMuPDF-compatible licensing
route and repeat the complete dependency/license review. Internal acceptance is not
a public-distribution license decision.
