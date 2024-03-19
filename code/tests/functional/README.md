# Functional Tests

This test suite is designed to run against local instances of the applications that constitute this project.

All tests should treat the applications as closed boxes, interacting only through their defined interfaces, without 
directly invoking any internal methods or functions. Dependencies should be simulated using mock servers.

## Benefits

Functional testing offers several advantages over unit and integration testing:

- **System Validation**: Functional testing validates that the system functions as expected in a real-world scenario, 
  providing a higher level of confidence in the system's overall functionality.
- **User Experience**: It simulates the user's experience more closely than unit or integration tests, ensuring that the 
  system is not only working correctly but also user-friendly.
- **Interactions**: It ensures that all HTTP requests or similar interactions are thoroughly tested, which might not be 
  the case with unit or integration tests.
- **Error Scenarios**: It allows for testing error scenarios with downstream dependencies using mock servers, which can 
  be difficult to simulate in unit or integration tests.
- **Regression Detection**: It's excellent for detecting regressions, where a change or addition breaks existing 
  functionality.

## Test Inclusion Criteria

Given that these tests run instances of the applications and any required mock servers, they are naturally slower. 
Additionally, as each application is treated as a closed box, debugging errors can be more challenging. Therefore, it's 
recommended to cover all possible code paths and scenarios at the unit test level. Consider adding a test to the 
functional test suite when:

- **New Endpoint**: A new endpoint is added. In this case, add tests for both successful and failing requests.
- **Significant Divergence**: There's a significant divergence in functionality within an endpoint.
- **Complex Interactions**: The feature involves complex interactions between different parts of the system that cannot 
  be adequately tested with unit or integration tests.
- **Critical Path**: The feature is part of a critical path in the application. Functional tests can help ensure that 
  the entire path works as expected.
- **Third-Party Integrations**: The feature involves third-party integrations. Functional tests can help ensure that the 
  integration works correctly in a real-world scenario.

## Running the Tests

There are two ways to run the functional tests:
- Navigate to the code directory and run the pytest module with the "functional" marker: 
`cd code && poetry run pytest -m "functional"`
- Use the makefile command: `make functionaltest`