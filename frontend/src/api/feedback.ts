import { client } from "./client";

export async function submitFeedback(payload: {
  type: string;
  content: string;
  page_url?: string;
  book_id?: string;
}): Promise<void> {
  await client.post("/feedback", payload);
}
