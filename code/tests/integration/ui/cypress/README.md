# Running UI Tests

Run the command for cypress tests (to run in headless mode)

```
npx cypress run --env BASE_URL_ADMIN_WEBSITE=https://example-admin.com,BASE_URL_USER_WEBSITE=https://example.com
```

If you want to run the tests in interactive mode (in a browser)

```
npx cypress --env BASE_URL_ADMIN_WEBSITE=https://example-admin.com,BASE_URL_USER_WEBSITE=https://example.com
```

Then follow the instructions on the opened electron browser