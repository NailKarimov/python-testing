import { test, expect, buildPost, Post } from '../../src';

test.describe('Posts API', () => {
  test('GET /posts returns a non-empty list', { tag: '@smoke' }, async ({ posts }) => {
    const response = await posts.list();

    expect(response.status()).toBe(200);
    const body = (await response.json()) as Post[];
    expect(body.length).toBeGreaterThan(0);
  });

  test('GET /posts/{id} returns a post with the expected shape', async ({ posts }) => {
    const response = await posts.get(1);

    expect(response.status()).toBe(200);
    expect(await response.json()).toEqual({
      id: 1,
      userId: expect.any(Number),
      title: expect.any(String),
      body: expect.any(String),
    });
  });

  test('POST /posts creates a post and echoes the payload', async ({ posts }) => {
    const payload = buildPost();

    const response = await posts.create(payload);

    expect(response.status()).toBe(201);
    expect(await response.json()).toMatchObject({ ...payload, id: expect.any(Number) });
  });

  test('GET /posts/{id} for a missing post returns 404', async ({ posts }) => {
    const response = await posts.get(0);

    expect(response.status()).toBe(404);
  });
});
