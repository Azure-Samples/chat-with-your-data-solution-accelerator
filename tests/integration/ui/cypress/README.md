# Running UI Tests

Run the command for cypress tests (to run in headless mode)

```
npx cypress run --env ADMIN_WEBSITE_NAME=https://example-admin.com,FRONTEND_WEBSITE_NAME=https://example.com
```

If you want to run the tests in interactive mode (in a browser)

```
npx cypress open --env ADMIN_WEBSITE_NAME=https://example-admin.com,FRONTEND_WEBSITE_NAME=https://example.com
```

Then follow the instructions on the opened electron browser