# Use Cypress as a framework for E2E testing

* **Status:** approved
* **Proposer:** @superhindupur
* **Date:** 2024-03-18
* **Technical Story:** [Add E2E test suite](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/419)

## Context and Problem Statement

E2E tests help test the deployed system as a whole, usually from the browser, for web applications like the Chat With Your Data website and admin website.
They provide confidence in the overall functionality of the system, including how the various systems interact with each other.
Since these tests can be slow and complex to set up, we should ideally run a small subset of test cases as E2E tests.

There are several E2E UI testing frameworks out there, and this document looks at which one to use.

## Decision Drivers

* Ease of setup and use.
* It's maintained.
* Ease of setup as a github action.
* It's lightweight, since we will be running only a small number of e2e tests.

## Considered Options

* Selenium
* Cypress
* TestCafe
* Several other options not mentioned here - like TestComplete, Robot Framework etc. They are not lightweight as they support mobile app testing in addition to browser testing, which we do not need.

## Decision Outcome

Cypress, because it meets all the requirements.

## Pros and Cons of the Options

### Selenium

[Selenium](https://www.selenium.dev/) is one of the most widely used UI testing frameworks. It uses Webdriver to automate browser actions.

* Good, because it supports backend programming languages like Java, Python etc.
* Good, because it is maintained.
* Bad, because it requires a lot of boilerplate code.
* Bad, because it requires downloading browser-specific drivers to set up the test environment.

### Cypress

[Cypress](https://www.cypress.io/) is a Javascript-based UI test framework built for the modern web. It operates straight in the browser and doesn't need additional drivers.

* Good, because it is lightweight, no additional driver or dependencies required.
* Good, because it is maintained.
* Good, because it is easy to setup and use.
* There are some drawbacks of Cypress but they're irrelevant to our use case:
    * No support for multiple browser tabs.
    * Doesn't support iFrame testing.
    * Doesn't support testing on Safari and IE browsers. (Chrome, Edge, Firefox etc are supported)

### TestCafe

[TestCafe](https://testcafe.io/) is also a Javascript-based UI framework, and also operates straight in the browser. The only slight disadvantage it has as compared to Cypress is that it has a smaller community supporting/maintaining it.

* Good, because it is lightweight, no additional driver or dependencies required.
* Good, because it is easy to setup and use.
* Good, because it supports multiple tabs and iFrames.
* Bad, because it has a smaller community of maintainers as compared to Cypress.
* Bad, because browsers are not aware that they are running in test mode. So, in some edge cases, automation control can be disrupted.

## Links

* [TestCafe vs Cypress](https://www.browserstack.com/guide/testcafe-vs-cypress)
* [Selenium vs Cypress](https://dzone.com/articles/selenium-vs-cypress-does-cypress-replace-selenium)
