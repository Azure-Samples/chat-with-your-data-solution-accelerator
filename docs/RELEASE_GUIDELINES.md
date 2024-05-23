# Release Guidelines

These guidelines are intended for developers who are active maintainers of this project, and gives guidance on how releases are managed.

# Releases

This repository uses GitHub's in-built [Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository) feature.

- **Latest release**: If you navigate to the main page of this repository, you'll find **Releases** on the right-hand side.
- **Manual release**: From the **Releases** tab, it is possible to create a manual release by following these instructions on [Creating a release](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository#creating-a-release).
- **Automated release**: In addition, this repository is configured to allow for automated releases, using GitHub Actions.

# Automated releases

In order to automate the generation of a changelog, the creation of a release, and the bumping of a version number, we use the [Conventional Changelog Action](https://github.com/TriPSs/conventional-changelog-action).

It works by inferring from the commit history what changes have been made, and hence what version should be assigned. This is why it is important for Pull Request titles to adhere to the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) specification, which many repositories use. This convention uses types such as `docs`, `fix`, `feat`, etc to label commits and PRs.

From these, the [semantic version](https://semver.org/) of a release can be identified. For example a release which consists of a PR which adds a feature (`feat`) would result in an increment of the Minor part of the semantic version, e.g. 1.1.0 -> 1.2.0.

Using the Conventional Changelog Action along with GitHub Releases takes all of the manual work out of creating a release.

# Conventional Changelog Action

## Usage

We use the [Conventional Changelog](https://github.com/TriPSs/conventional-changelog-action) GitHub Action, which you can find in `./github/workflows/create-release.yml`.

Once a PR is merged to `main`, the Action will automatically run. It will automatically generate a changelog, and if that changelog is empty, then no release is made. This would be the case for merges to `main` that include `docs`, `chore`, etc.

Once a merge to `main` is completed that would result in a major/minor/patch version increase (such as `feat`, `fix`, etc.) then a changelog will be generated, and this will trigger a release to be published automatically with the appropriate version number.

By default, `semantic-release` only includes `fix`, `feat`, and `perf` commit types in the release. Our project includes all commit types in their release notes, while still using `semantic-release`'s commit analyzer to only create releases for `fix`, `feat`, and `perf` commits.

Note that, it is not possible to automate the update of a `CHANGELOG` as this would require the GitHub token to have permissions to push commits to the repository, which cannot be enabled.

## Security

The GitHub Action to create the release requires only the GitHub token, as this has sufficient permissions for it to checkout main (and read the commit history) and to create a release for the repository.

# Conventional Commits

This is a [specification](https://www.conventionalcommits.org/en/v1.0.0/) which is commonly used to help communicate the nature of the changes in a pull request or commit. As in our case, it makes it easier to use automated tooling based on those namings. For this repository, we ask the PRs should be prefixed with one of the following `types`:
  * feat: A new feature
  * fix: A bug fix
  * docs: Documentation only changes
  * style: Changes that do not affect the meaning of the code (white-space, formatting, missing semi-colons, etc)
  * refactor: A code change that neither fixes a bug nor adds a feature
  * perf: A code change that improves performance
  * test: Adding missing tests or correcting existing tests
  * build: Changes that affect the build system or external dependencies (example scopes: gulp, broccoli, npm)
  * ci: Changes to our CI configuration files and scripts (example scopes: Travis, Circle, BrowserStack, SauceLabs)
  * chore: Other changes that don't modify src or test files
  * revert: Reverts a previous commit
  * !: A breaking change is indicated with a `!` after the listed prefixes above, e.g. `feat!`, `fix!`, `refactor!`, etc.


# Semantic Versioning

[Semantic Versioning (SemVer)](https://semver.org/) provides a set of rules to determine what version number a piece of software should have.

The guidance states:

> Given a version number MAJOR.MINOR.PATCH, increment the:
>
> MAJOR version when you make incompatible API changes
> MINOR version when you add functionality in a backward compatible manner
> PATCH version when you make backward compatible bug fixes
> Additional labels for pre-release and build metadata are available as extensions to the MAJOR.MINOR.PATCH format.

## What should I do if I introduce a breaking change?

If you must introduce a breaking change, then the Pull Request should clearly indicate this by adding a `!` after the prefix type, for example `feat!`, `fix!`, `refactor!`, etc. This will correlate to a `major` semantic version increase.
