# Third-party notices

This isolated experiment uses `pdfjs-dist` 6.3.289, the prebuilt npm distribution
of Mozilla PDF.js. PDF.js is Copyright Mozilla Foundation and contributors and is
licensed under the Apache License, Version 2.0:

https://www.apache.org/licenses/LICENSE-2.0

Source and documentation: https://github.com/mozilla/pdf.js and
https://mozilla.github.io/pdf.js/getting_started/

`package-lock.json` fixes the experimental dependency graph. `node_modules` and the
compiled bundle are generated locally and are not committed. Any future production
distribution must repeat license, maintenance, supply-chain, and bundle review.
