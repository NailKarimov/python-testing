import { test as base, expect } from '@playwright/test';
import { LoginPage } from './pages/LoginPage';
import { InventoryPage } from './pages/InventoryPage';
import { ApiClient } from './api/ApiClient';
import { PostsClient } from './api/PostsClient';

type Fixtures = {
  loginPage: LoginPage;
  inventoryPage: InventoryPage;
  posts: PostsClient;
};

/** Tests ask for ready objects: async ({ loginPage, posts }) => { ... } */
export const test = base.extend<Fixtures>({
  loginPage: async ({ page }, use) => use(new LoginPage(page)),
  inventoryPage: async ({ page }, use) => use(new InventoryPage(page)),
  posts: async ({ request }, use) => use(new PostsClient(new ApiClient(request))),
});

export { expect };
