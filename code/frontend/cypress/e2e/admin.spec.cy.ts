Cypress.config('baseUrl', 'https://cwyd34-website-24okrcyuljemk-admin.azurewebsites.net')

describe('the cwyd admin website', () => {
  before(() => {
    cy.visit('/Ingest_Data');
  });

  it('allows file upload', () => {
    cy.get('input[type=file]', { timeout: 30000 }).selectFile('cypress/fixtures/ingest.txt', { force: true });
  });
});
