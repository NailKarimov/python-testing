import { Page } from '@playwright/test';

/** Common behaviour for all page objects: every page knows its own path. */
export abstract class BasePage {
  protected abstract readonly path: string;

  constructor(readonly page: Page) {}

  async open(): Promise<void> {
    await this.page.goto(this.path);
  }
}
