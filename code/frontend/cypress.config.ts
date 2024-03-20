import { defineConfig } from "cypress";

export default defineConfig({
  e2e: {

    baseUrl: 'https://cwyd34-website-24okrcyuljemk.azurewebsites.net',

    setupNodeEvents(on, config) {
      // implement node event listeners here
    },
  },
});
