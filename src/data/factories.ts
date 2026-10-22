import { faker } from '@faker-js/faker';
import { NewPost } from '../api/PostsClient';

/** Builds a valid post; pass overrides to create boundary or negative cases. */
export function buildPost(overrides: Partial<NewPost> = {}): NewPost {
  return {
    userId: faker.number.int({ min: 1, max: 10 }),
    title: faker.lorem.sentence({ min: 3, max: 8 }),
    body: faker.lorem.paragraph(),
    ...overrides,
  };
}
