# Use pytest-httpserver as a mock server for funcitonal testing

* **Status:** approved
* **Proposer:** @adamdougal
* **Date:** 2024-03-15
* **Technical Story:** [https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/420](https://github.com/Azure-Samples/chat-with-your-data-solution-accelerator/issues/420)


## Context and Problem Statement

Functional tests run against a closed boxed running version of the application. This means we are unable to stub out 
http requests at the code level. Requiring us to use mock http servers. There are many mock http servers out there, 
which one should we use?

## Decision Drivers

* Ease of use
* It's maintained
* Quick to setup
* Ability to mock responses, including errors
* Does not introduce another programming language, and ideally runtime

## Considered Options

* Custom built
* [WireMock](https://wiremock.org/)
* [pytest-httpserver](https://pypi.org/project/pytest_httpserver/)
* [aoai-simulated-api](https://github.com/stuartleeks/aoai-simulated-api)

## Decision Outcome

pytest-httpserver because it meets all of our requirements

### Positive Consequences

* Good, because it does not introduce another programming language or runtime
* Good, because it's well maintained
* Good, because has built in integration with out testing library, pytest. Therefore is quick setup.
* Good, because it does allow us to simulate all types of errors e.g. timeouts

### Negative Consequences

N/A

## Pros and Cons of the Options

### Custom Built

This option requires us to build everything from scratch. It looks fairly straight forward to do based on some 
suggestions here [https://stackoverflow.com/questions/21877387/mocking-a-http-server-in-python](https://stackoverflow.com/questions/21877387/mocking-a-http-server-in-python).

* Good, because full flexibility to return anything we want, including simulating faults
* Good, because it does not introduce another programming language or runtime
* Bad, because a potentially larger up front cost to develop
* Bad, because it will require maintenance

### WireMock

WireMock is a java lirary that can be interacted with using the [wiremock python library](https://pypi.org/project/wiremock/).

* Good, because it allows us to return anything we want, including simulating faults
* Good, because it's well maintained
* Good, because it's quick to setup
* Bad, because it introduces another programming runtime

### pytest-httpserver

pytest-httpserver is a python library that creates a mock server that can be primed with responses. It can return bad
status codes, but it doesn't have built in funtionality to simulate faults and timeouts in the same way as WireMock can. 
However, it does allow us to define our own custom response handler to simulate faults e.g:

```python
    def handler(_) -> werkzeug.Response:
        time.sleep(10)
        return werkzeug.Response({"foo": "bar"}, status=200)

    httpserver.expect_request("/foobar").respond_with_handler(handler)
```

An issue has been raised [here](https://github.com/csernazs/pytest-httpserver/issues/290) to get this feature built in.

* Good, because it does not introduce another programming language or runtime
* Good, because it's well maintained
* Good, because has built in integration with out testing library, pytest. Therefore is quick setup.
* Good, because it does allow us to simulate all types of errors e.g. timeouts

### aoai-simulated-api

aoai-simulated-api is a python library build by a Microsoft employee. It aims to create a simulated API implementation
specifically for Azure OpenAI.

* Good, because it does not introduce another programming language or runtime
* Good, because it potentially simulates the main downstream service more accurately, though we may not need this 
  accuracy in these tests with the introduction of E2E integrated test
* Bad, because it's very new, meaning it's unclear how it will be maintained and it could change significantly
* Bad, because it does not allow us to prime specific respones and faults
* Bad, becuase if we needed to mock anything other than Azure OpenAI, we'd need to introduce another type of mock server
