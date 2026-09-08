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
