# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.0] - 2026-09-26

### Added
- **Fancy TUI redesign** with modern Dracula-inspired theme
- **Poster art support** — async loading of movie/series posters from Cinemeta
- **Stream type badges** — DIRECT, DEBRID, MAGNET indicators in quality picker
- **Rich detail panel** with kind badges, genres, and synopsis
- **Comprehensive animations** — fade-in, slide-up, pulse glow, shimmer effects
- **Responsive layout** — adapts to terminal width
- **Reduced motion support** — respects `prefers-reduced-motion`
- **GitHub Actions CI/CD** — tests, linting, build, and PyPI publish on tag
- **CONTRIBUTING.md** — contribution guidelines
- **CODE_OF_CONDUCT.md** — Contributor Covenant v2.1
- **Ruff configuration** for linting and formatting

### Changed
- Complete CSS rewrite with CSS custom properties
- Improved keyboard shortcuts (added `d` for download, `i` for info)
- Better notifications with timeout and severity
- Enhanced episode/quality picker modals with styling
- Updated README with badges and screenshots section

### Fixed
- Config download directory now properly loaded from config.toml
- License format in pyproject.toml

## [0.2.0] - 2026-09-26

### Added
- **Stremio source** (Cinemeta catalogue + Torrentio streams)
- Movie, series, and anime search via Cinemeta API
- Episode picker for series/anime
- Quality picker with seeders/size display
- Magnet link playback via webtorrent/peerflix
- Debrid support (RealDebrid, AllDebrid, Premiumize, etc.)
- Watch history and library (favorites)
- Downloads via yt-dlp
- Local files source
- Config via config.toml and env vars
- MIT license

### Changed
- Renamed from `stream-tui` to `torrentio-tui`
- Package structure: `stream_tui` → `torrentio_tui`
- CLI command: `stream-tui` → `torrentio-tui`
- Config directory: `~/.config/stream-tui` → `~/.config/torrentio-tui`
- Env vars: `STREAM_TUI_*` → `TORRENTIO_TUI_*`

## [0.1.0] - 2026-09-26

### Added
- Initial scaffold with Textual TUI
- Local files source
- Basic search, episode/quality selection
- Playback via mpv/vlc
- Watch history and library
- Plugin architecture for sources

[0.3.0]: https://github.com/yubiiixtreme/torrentio-tui/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/yubiiixtreme/torrentio-tui/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/yubiiixtreme/torrentio-tui/releases/tag/v0.1.0