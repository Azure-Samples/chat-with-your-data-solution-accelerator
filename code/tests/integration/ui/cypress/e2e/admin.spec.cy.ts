Cypress.config('baseUrl', Cypress.env('BASE_URL_ADMIN_WEBSITE'))

describe('the cwyd admin website', () => {
  before(() => {
    const myVariable = Cypress.env('BASE_URL_ADMIN_WEBSITE');
    cy.log('My variable:', myVariable);
    cy.visit('/Ingest_Data');
  });

  it('allows file upload', () => {
    cy.get('input[type=file]', { timeout: 30000 }).selectFile('cypress/fixtures/ingest.txt', { force: true });
  });
});
