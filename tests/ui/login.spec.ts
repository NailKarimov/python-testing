import { test, expect, env } from '../../src';

test.describe('Login', () => {
  test.beforeEach(async ({ loginPage }) => {
    await loginPage.open();
  });

  test(
    'user with valid credentials sees the product list',
    { tag: '@smoke' },
    async ({ loginPage, inventoryPage, page }) => {
      await loginPage.login(env.uiUsername, env.uiPassword);

      await expect(page).toHaveURL(/inventory\.html/);
      await expect(inventoryPage.title).toHaveText('Products');
      await expect(inventoryPage.items).not.toHaveCount(0);
    },
  );

  test('locked out user gets an error message', async ({ loginPage }) => {
    await loginPage.login('locked_out_user', env.uiPassword);

    await expect(loginPage.error).toContainText('Sorry, this user has been locked out');
  });

  test('empty form shows "Username is required"', async ({ loginPage }) => {
    await loginPage.submit.click();

    await expect(loginPage.error).toContainText('Username is required');
  });
});

test.describe('Cart', () => {
  test('adding a product updates the cart badge', async ({ loginPage, inventoryPage }) => {
    await loginPage.open();
    await loginPage.login(env.uiUsername, env.uiPassword);

    await inventoryPage.addToCart('sauce-labs-backpack');

    await expect(inventoryPage.cartBadge).toHaveText('1');
  });
});
