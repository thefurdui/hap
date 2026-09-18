# Versioning and releases

`VERSION` is the single source of the release number. It contains a stable `MAJOR.MINOR.PATCH`, without a `v` prefix or leading zeroes. Tags use `vMAJOR.MINOR.PATCH`. The current release tooling supports stable releases; prerelease and build metadata suffixes are not accepted.

For future releases, use [Semantic Versioning](https://semver.org/spec/v2.0.0.html): patch for compatible fixes, minor for compatible features, and major for incompatible changes. The compatibility contract includes documented commands, flags, environment variables, defaults, and persisted project/registry formats. Conventional commits describe each change; release selection remains an explicit maintainer decision.

v1.2.0 retains the requested version for this migration release, including its documented changes to defaults. This is a transition exception: future incompatible defaults or formats require a major version bump.

## Preparing a release

1. Set `VERSION` to the intended release number.
2. Add its dated entry at the top of `CHANGELOG.md`, documenting compatibility and migration changes. Historical entries stay intact.
3. Run `make release-prepare`. It validates the version and release notes, then synchronizes `bin/hap`, `install.sh`, the README installation tag, and `SHA256SUMS`. The executable and installer retain embedded values so installed copies do not need the repository's `VERSION` file or Git.
4. Run `make check` and review the diff. Stage the intended changes and create the release commit.
5. Create an annotated tag on that commit, then run `make check-tag`.

For v1.2.0, the final commands are:

```sh
git commit -m "chore(release): v1.2.0"
git tag -a v1.2.0 -m "hap v1.2.0"
make check-tag
```

`make check-release` verifies generated versions, the newest changelog entry, and payload checksums. `make check-tag` additionally requires an annotated tag matching `VERSION`, pointing at `HEAD`, with a clean working tree. CI runs this tag check on tag builds and the normal checks on branches and pull requests.

Release tags are immutable: never move or overwrite an existing release tag. Correct a released defect in a new version. Commit/tag creation is local; pushing commits and tags or publishing a hosted release is a separate action.

After any change to a downloadable file during development, run `make release-prepare` again and commit the regenerated checksum manifest with that change.
