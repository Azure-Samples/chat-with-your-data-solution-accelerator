# Backend API Tests

At present, there are three sets of tests:

- `default` - This is the base configuration. The majority of tests should be added here.
- `without_data` - This configuration does not include any of the `AZURE_SEARCH` environment variables
- `sk_orchestrator` - This configuration uses Semantic Kernel as the orchestrator

Each set of tests starts its own instance of the backend API on a different port.

When adding new tests, first check to see if it is possible to add the tests to an
existing set of tests, rather than creating a new set, as this removes the need for
starting up a new instance of the application on another port.

New environment variables common to all tests can be directly added to the `config`
dict in [app_config.py](../app_config.py), while variables only needed for one set
of tests can be added to the `app_config` fixture in the respective `conftest.py`
file, e.g. [./default/conftest.py](./default/conftest.py).

```py
@pytest.fixture(scope="package")
def app_config(make_httpserver, ca):
    logging.info("Creating APP CONFIG")
    with ca.cert_pem.tempfile() as ca_temp_path:
        app_config = AppConfig(
            {
                "AZURE_OPENAI_ENDPOINT": f"https://localhost:{make_httpserver.port}/",
                "AZURE_SEARCH_SERVICE": f"https://localhost:{make_httpserver.port}/",
                "AZURE_CONTENT_SAFETY_ENDPOINT": f"https://localhost:{make_httpserver.port}/",
                "SSL_CERT_FILE": ca_temp_path,
                "CURL_CA_BUNDLE": ca_temp_path,
                "NEW_ENV_VAR": "VALUE",
            }
        )
        logging.info(f"Created app config: {app_config.get_all()}")
        yield app_config
```

To remove an environment variable from the default defined in the `AppConfig` class,
set its value to `None`.

```py
@pytest.fixture(scope="package")
def app_config(make_httpserver, ca):
    logging.info("Creating APP CONFIG")
    with ca.cert_pem.tempfile() as ca_temp_path:
        app_config = AppConfig(
            {
                "AZURE_OPENAI_ENDPOINT": f"https://localhost:{make_httpserver.port}/",
                "AZURE_SEARCH_SERVICE": f"https://localhost:{make_httpserver.port}/",
                "AZURE_CONTENT_SAFETY_ENDPOINT": f"https://localhost:{make_httpserver.port}/",
                "SSL_CERT_FILE": ca_temp_path,
                "CURL_CA_BUNDLE": ca_temp_path,
                "ENV_VAR_TO_REMOVE": None,
            }
        )
        logging.info(f"Created app config: {app_config.get_all()}")
        yield app_config
```
