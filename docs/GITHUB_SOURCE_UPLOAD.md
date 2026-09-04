# GitHub source snapshot

Date: 2026-09-04

The owner explicitly authorized uploading the current source to the public
`gaofeng030816-lab/ResearchMind` repository. This authorizes source visibility,
not a release, a distribution upload, or completion of any development gate.

## Publication boundary

- Publish a sanitized current-source snapshot, not the existing local Git history.
  The old local history contains a credential-like test value and machine-specific
  paths. It remains local; do not push it, its old branches, or tags publicly.
- The test value has been replaced with an unmistakable fake. Local environment
  files, secrets, databases, generated PDFs, caches, and build artifacts are excluded.
- Historical validation documents retain their results; private paths are replaced
  with descriptive placeholders. Source code and generated-test fixtures are included.
- Future uploads must start from the published snapshot lineage. Never force-push
  the older local development history over the public branch.

## Development status at upload time

V2 `2.0.0rc1` remains the accepted internal baseline. V3-G1 is implemented and G2
is active. The owner approved the selected, approved-directory, read-only Zotero
PDF-copy boundary, but implementation was paused for this upload. Direct attachment
import remains disabled, and real Zotero manual acceptance is still outstanding.
See `V3_G2_ZOTERO_VALIDATION.md` for the recorded 341-pass / one-environment-skip
regression; publication does not count as G2 acceptance.

No public Release or release assets are created by this source upload.
