# Use Github Releases to manage project versioning

* **Status:** proposed
* **Proposer:** @frtibble
* **Date:** 2024-05-02
* **Technical Story:** [https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/651](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/651)

## Context and Problem Statement

Versioning allows users and developers to track changes between deployments, either by comparing code differences between versions or by referring to a changelog.

It also signals to users the nature of the changes, such as breaking changes, new functionality, or bug fixes, through the use of [semantic versioning](https://semver.org/).

Adopting versioning will give us more control over releases and improve communication to our users through changelogs and migration guides.

## Decision Drivers

* Minimal process (it should be straightforward to publish a release)
* Small time overhead (steps should be automated where possible)
* Low maintenance solution

## Considered Options

* GitHub Releases

## Decision Outcome

TBD

## Pros and Cons of the Options

### GitHub Releases

GitHub Releases is a feature which can be enabled directly in the repository, and allows you to create releases with release notes, @mentions of contributors, and link assets such as binaries.

Pros:

* **Supported solution**: GitHub Releases is built-in to GitHub repositories, so is well supported and low overhead to enable. It is used by many product teams, e.g. [vscode](https://github.com/microsoft/vscode), [semantic-kernel](https://github.com/microsoft/semantic-kernel), [WSL](https://github.com/microsoft/WSL), etc.

* **Easy publishing**: You can create, edit and delete releases using the browser or Releases API, which makes it simple to use.

* **Built-in features**: You can compare releases from the repository, see [Comparing releases](https://docs.github.com/en/repositories/releasing-projects-on-github/comparing-releases). You can also see the latest release from the repository homepage.

* **Automation**: There is support to automatically generate [release notes](https://docs.github.com/en/repositories/releasing-projects-on-github/automatically-generated-release-notes) based on changes since the previous release, it also includes who has contributed.

* **Simple**: There are extensive [docs](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases).

Cons:

* **Automatic releases**: Whilst it is straight-forward to publish a release manually, there are extra steps required if we would want to have automatic releases.
    - This [GitHub Blog post](https://github.blog/2021-12-16-5-automations-every-developer-should-be-running/#5-automate-your-releases-and-release-notes-with-github-actions) shares how you can use GitHub Actions to run a workflow which will create a release.
    - If we were to automate the release, we would need to make decisions on the release schedule or trigger, for example, should a new release be created each time a change is merged to `main`? Or should it be done on a schedule such as daily, weekly, etc?
    - If we had an automatic release, how would we deal with cases such as major version changes and making sure breaking changes didn't get included in a minor version release?
* **Manual releases**: If we were to do manual releases, this would be a responsibility that would need to be assigned, for example to a Project Maintainer.

## Proposal

Based on the current activity in the project, we could:

- Elect a Release Driver who will manually go through the steps of creating a release, this could be done during a call with the broader team and should take <30 mins.
- The Release Driver produces documentation to capture the steps and any related team discussion.
- Thereafter, follow a weekly release cadence. It will be the responsibility of the team to decide the release version, and the responsibility of the Release Driver to create the release with that version (which should take <15 mins).
- In the future, review whether further automation is needed, based on experience from previous releases and whether there is a benefit.
