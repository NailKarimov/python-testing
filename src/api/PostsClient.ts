import { APIResponse } from '@playwright/test';
import { ApiClient } from './ApiClient';

export type Post = {
  id: number;
  userId: number;
  title: string;
  body: string;
};

export type NewPost = Omit<Post, 'id'>;

/** Endpoints of the /posts resource. One client per resource keeps tests readable. */
export class PostsClient {
  constructor(private readonly api: ApiClient) {}

  list(): Promise<APIResponse> {
    return this.api.send('GET', '/posts');
  }

  get(id: number): Promise<APIResponse> {
    return this.api.send('GET', `/posts/${id}`);
  }

  create(post: NewPost): Promise<APIResponse> {
    return this.api.send('POST', '/posts', post);
  }
}
