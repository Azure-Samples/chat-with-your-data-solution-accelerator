# Azure Functions Tests

The functional tests for Azure Functions do not run the Azure functions locally, but instead invoke the entrypoints of the Python functions directly within each test.

For example, consider the following:

```py
import azure.functions as func

app = func.FunctionApp()

@app.function_name(name="HttpTrigger1")
@app.route(route="req")
def main(req):
    user = req.params.get("user")
    return f"Hello, {user}!"
```

Instead of making an HTTP request to `/api/req` from within a test, import the function directly and call the function with a payload similar to what would be
expected when running in Azure.


```py
import azure.functions as func

def test_main():
    # given
    req = func.HttpRequest(
        method="GET",
        url="http://localhost:7071/api/req",
        body=b"",
        params={
            "user": "world",
        },
    )

    # when
    res = main.build().get_user_function()(req)

    # then
    assert res == "Hello, world!"
```

Downstream dependcies are mocked using [pytest-httpserver](https://pytest-httpserver.readthedocs.io/).
