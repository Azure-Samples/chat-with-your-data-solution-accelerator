# Use GitHub Releases to manage project versioning

* **Status:** approved
* **Proposer:** @frtibble
* **Date:** 2024-05-02
* **Technical Story:** [https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/651](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/651)

## Context and Problem Statement

Versioning allows users and developers to track changes between deployments, either by comparing code differences between versions or by referring to a changelog.

It also signals to users the nature of the changes, such as breaking changes, new functionality, or bug fixes, through the use of [semantic versioning](https://semver.org/).

Currently CWYD does not provide versioned releases.

Adopting versioning will give us more control over releases and improve communication to our users through changelogs and migration guides.

## Decision Drivers

* Minimal process (it should be straightforward to publish a release)
* Small time overhead (steps should be automated where possible)
* Low maintenance solution

## Considered Options

* GitHub Releases

## Decision Outcome

The decision is to use a combination of GitHub Releases and GitHub Actions to create a mostly automated process for creating releases, with a manual option too.

## Pros and Cons of the Options

### GitHub Releases

GitHub Releases is a feature which can be enabled directly in the repository, and allows you to create releases with release notes, @mentions of contributors, and link assets such as binaries.

Pros:

* **Supported solution**: GitHub Releases is built-in to GitHub repositories, so is well supported and low overhead to enable. It is used by many product teams, e.g. [vscode](https://github.com/microsoft/vscode), [semantic-kernel](https://github.com/microsoft/semantic-kernel), [WSL](https://github.com/microsoft/WSL), etc.

* **Easy publishing**: You can create, edit and delete releases using the browser or Releases API, which makes it simple to use.

* **Built-in features**: You can compare releases from the repository, see [Comparing releases](https://docs.github.com/en/repositories/releasing-projects-on-github/comparing-releases). You can also see the latest release from the repository homepage.

* **Automation**: There is support to automatically generate [release notes](https://docs.github.com/en/repositories/releasing-projects-on-github/automatically-generated-release-notes) based on changes since the previous release, it also includes who has contributed.

* **Simple**: There is extensive [documentation available](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases).

* **Automated releases**: Using GitHub actions, it is also possible to automate the entire release, by generating a new version tag and creating a release with generated release notes.

## Proposal

- **Sprint Champion**: The Sprint Champion is responsible for reviewing any automated and manual releases which may occur during the sprint.
- **Release cadence**:
    - **Automated** releases will happen on each green PR merge. We will use GitHub actions to automate the release. This follows our current release cadence with the addition of adding a version. Note: Releasing smaller changesets is preferred in general since it is less riskier and easier to troubleshoot as compared to collecting changes for a week and releasing everything together.
    - **Manual** releases will happen ad-hoc where required, such as for important bug fixes. These can be created manually and will be documented in the Release Guide.
- **Release guide**: Create a Release Guide which includes what is required for automated and manual releases, define the versioning format (semantic versioning) and guidelines around what is considered a breaking change.
- **How to automate**:
    - When introducing automated versioning, there are a few things we need to consider:
        - **major/minor/patch** versions: Each release is tagged with a semantic version which is based on the change included (e.g. breaking change, feature, bug fix).
        - **Changelog**: A changelog must be included which details the changes that are included in the release.
    - The [**semantic-release-action**](https://github.com/codfish/semantic-release-action?tab=readme-ov-file#semantic-release-action) GitHub Action automates releases. It looks at commit messages to automatically generate the version number and to generate the changelog.
        - It uses [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/), meaning we'd need to follow a convention of labelling PRs with `fix`/`feat`/`BREAKING CHANGE`, etc, in order to be picked up by the release generator. It uses these labels to create the correct version.
        - As a consequence, current dependabot PRs would not trigger a release PR. These would be in main until an automatic or manual release was triggered.
