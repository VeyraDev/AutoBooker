import { client } from "./client";

export interface NotificationItem {
  id: string;
  type: string;
  title: string;
  body?: string | null;
  payload_json?: Record<string, unknown> | null;
  is_read: boolean;
  created_at?: string | null;
}

export async function listNotifications(): Promise<{ items: NotificationItem[]; unread_count: number }> {
  const { data } = await client.get("/notifications");
  return data;
}

export async function markNotificationRead(id: string): Promise<void> {
  await client.post(`/notifications/${id}/read`);
}

export async function fetchCommunityQrUrl(): Promise<string> {
  const { data } = await client.get<{ url: string }>("/notifications/community-qr");
  return data.url || "";
}
