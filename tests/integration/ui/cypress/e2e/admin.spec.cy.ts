Cypress.config('baseUrl', Cypress.env('ADMIN_WEBSITE_NAME'))

describe('the cwyd admin website', () => {
  before(() => {
    cy.visit('/Ingest_Data');
  });

  it('allows file upload', () => {
    cy.get('input[type=file]', { timeout: 30000 }).selectFile('../../../data/PerksPlus.pdf', { force: true });
    cy.get('div[data-testid*="stNotificationContentSuccess"]', { timeout: 30000 }).then(($div) => {
      expect($div.text()).to.contain('1 documents uploaded');
    });
  });
});
