Cypress.config('baseUrl', Cypress.env('FRONTEND_WEBSITE_NAME'))

describe('the cwyd user website', () => {
  before(() => {
    cy.visit('/');
  });

  it('answers user chat', () => {
    cy.get('textarea').type('Hello{enter}');

    cy.get('div[class*="chatMessageUserMessage"]').then(($div) => {
      cy.log('Text from user chat:', $div.text());
      expect($div).to.exist;
      expect($div.text()).to.contain('Hello');
    });

    cy.get('div[class*="answerText"]', { timeout: 30000 }).then(($div) => {
      cy.log('Text from AI:', $div.text());
      expect($div).to.exist;
    });
  });
});
