# Versioning and releases

## One product version

The root `manifest.json` field `version` is the only machine-readable source
of the Pallet product version. Use full `MAJOR.MINOR.PATCH`, for example
`0.8.1`, with no `v` prefix in JSON and no shortened `0.8` or `6.4` labels.
Bundled providers ship together and inherit this version; their manifests
must not declare independent product versions. Do not add a duplicate
VERSION file or hardcode a release number into the QML runtime.

Documentation may show historical version numbers when clearly labeled.
Do not rewrite old commits, invent missing releases, or move published tags
merely to make the history look tidy. Earlier 0.6.x references are history,
not alternative current versions. The earlier chat announcement 'v0.0' was
not a real release; the manifest in that commit was 0.8.0.

## Bump policy

Pallet is still in initial development (`0.y.z`). Until 1.0:

- Patch (`0.8.0` -> `0.8.1`): bug fixes, reliability work, documentation,
  tests, or tooling bundled into a maintenance release.
- Minor (`0.8.x` -> `0.9.0`): a coherent new user-facing capability or an
  incompatible pre-1.0 change. Explain breaking changes in the changelog.
- Do not bump the version for every work-in-progress commit. Group changes
  into a tested release. Reserve 1.0.0 for an explicitly defined stable
  compatibility contract, not for a cosmetic redesign alone.

This is Pallet's pre-1.0 project policy. Semantic Versioning permits an
unstable public API during initial development. After 1.0 use major bumps
for incompatible public API changes, minor for compatible additions, and
patch for compatible fixes. See https://semver.org/.

## Tags, titles, and commits

- Manifest version: `0.8.1`.
- Release tag: `v0.8.1` (exactly `v` plus the manifest version).
- Release title: `Pallet v0.8.1`.
- Ordinary commits: `fix(host): drain final query on EOF`, `feat(obsidian): ...`,
  `docs: ...`, or `test: ...`; a version in every commit subject is unnecessary.
- Schema version, currently `schemaVersion: 1`, describes the Omarchy
  manifest format, not the Pallet release. Do not bump it when Pallet updates.
- Provider protocol compatibility is documented in docs/PROVIDERS.md. Do not
  introduce a fake product-version field as a wire-protocol handshake.

## Release checklist

1. Review the changes and choose the bump using this policy.
2. Update the root manifest and add the matching top released CHANGELOG
   section in the same commit. Keep upcoming work under [Unreleased].
3. Run `python3 scripts/check_release.py` and
   `python3 -m unittest discover -s tests -v`.
4. Run `omarchy plugin validate .` and native QML/Hyprland tests on a machine
   that actually has those dependencies. Python tests do not prove UI or
   Obsidian integration works.
5. Push the release commit, review CI, then separately approve and create
   an immutable `vX.Y.Z` tag on that tested commit and publish release notes.
   A commit changing the manifest is not itself a tag or GitHub Release.
6. Tag CI checks the tag against the manifest. It reports mismatches; it
   cannot prevent an already pushed tag or undo it. Do not move a published
   tag to repair a mismatch.

The validation script does not modify files, create tags, or publish releases.
It checks full version format, changelog alignment, bundled-provider version
policy, and Python syntax. Tag checks additionally require exact agreement
with the root manifest. CI does not install apps or access personal vaults.
