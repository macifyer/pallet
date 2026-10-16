# Changelog

Release numbers come from the root manifest.json. This changelog starts with
0.8.1; it is not a reconstructed or retagged history of earlier commits.

## [Unreleased]

## [0.8.1]

### Fixed
- Wait for the final pending search on stdin EOF before terminating providers.
  A piped request now gets a response within the existing merge deadline.
- Await provider shutdown and kill children that ignore termination.

### Development
- Define the root manifest as the single source of the product version.
- Document full three-part versions, v-prefixed release tags, and separate
  schema/protocol compatibility from product release numbers.
- Add isolated host regression tests, release-validation tests, and CI for
  Python syntax and release metadata. No Hyprland or personal vault required.

Earlier development milestones are recorded in git history. Documentation for
0.8.0 scoped actions remains applicable; this patch adds no new Obsidian,
AI, yazi, fzf, or onboarding functionality.
