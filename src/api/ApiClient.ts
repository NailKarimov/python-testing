import { APIRequestContext, APIResponse, test } from '@playwright/test';

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

/**
 * Thin wrapper over Playwright's APIRequestContext.
 * Every request and response is attached to the test report, so a failed
 * API test can be debugged from the Allure report alone.
 */
export class ApiClient {
  constructor(private readonly request: APIRequestContext) {}

  async send(method: Method, url: string, body?: unknown): Promise<APIResponse> {
    const response = await this.request.fetch(url, { method, data: body });
    await this.attach(method, url, body, response);
    return response;
  }

  private async attach(method: Method, url: string, body: unknown, response: APIResponse): Promise<void> {
    const text = await response.text();
    const report = [
      `${method} ${response.url()}`,
      body === undefined ? '' : `Request body:\n${JSON.stringify(body, null, 2)}`,
      `Status: ${response.status()}`,
      `Response body:\n${text.slice(0, 5_000)}`,
    ]
      .filter(Boolean)
      .join('\n\n');
    await test.info().attach(`${method} ${url}`, { body: report, contentType: 'text/plain' });
  }
}
