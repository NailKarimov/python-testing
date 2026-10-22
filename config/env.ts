import 'dotenv/config';

/** Reads a variable from the environment (or .env) and falls back to a default. */
function read(name: string, fallback: string): string {
  const value = process.env[name];
  return value && value.trim() !== '' ? value : fallback;
}

/**
 * Test environment settings. Every value can be overridden with an environment
 * variable, so the same suite runs against local, staging or demo targets.
 */
export const env = {
  uiBaseUrl: read('UI_BASE_URL', 'https://www.saucedemo.com'),
  apiBaseUrl: read('API_BASE_URL', 'https://jsonplaceholder.typicode.com'),
  uiUsername: read('UI_USERNAME', 'standard_user'),
  uiPassword: read('UI_PASSWORD', 'secret_sauce'),
};
