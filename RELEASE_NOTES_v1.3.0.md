# EchoNote 1.3.0 Release Notes

## Highlights

- Landing page is now fully single-page and aligned with open-source project website best practices.
- Header navigation is hardened for multilingual content and narrow/medium widths.
- Language switching is more stable and accessible (persisted locale + synchronized document language).
- Documentation has been refreshed to reduce drift between implementation and docs.

## Added

- Compact desktop `More` menu behavior for `lg~xl` widths.
- Locale persistence in landing page (`localStorage`) and `<html lang>` synchronization.
- Updated landing docs with `v1.3.0` feature baseline.

## Changed

- Removed legacy `/about` route and template view in landing app.
- Unified breakpoint strategy for menu toggle and menu panel.
- Replaced multi-button language switcher with single-select control.
- Updated project/landing version references to `1.3.0`.

## Fixed

- Fixed narrow-width header issue where clicking the top-right menu button only showed `X` without menu content.
- Fixed header overflow instability in English and French locales.
