// Phone reminders about due wzorce (Web Push) - thin wrappers over fetchAPI
import { fetchAPI } from "./client";

export interface PushConfig {
  /** false when the server has no VAPID keys - the feature is hidden */
  enabled: boolean;
  public_key: string | null;
  /** "HH:MM", Europe/Warsaw */
  weekday_time: string;
  weekend_time: string;
  /** Devices of this account with reminders on */
  devices: number;
}

const json = (method: string, body?: unknown): RequestInit => ({
  method,
  body: body === undefined ? undefined : JSON.stringify(body),
});

export const pushApi = {
  config: () => fetchAPI<PushConfig>("/api/push/config"),

  subscribe: (subscription: PushSubscriptionJSON) =>
    fetchAPI<PushConfig>("/api/push/subscriptions", json("POST", subscription)),

  unsubscribe: (endpoint: string) =>
    fetchAPI<PushConfig>("/api/push/subscriptions/delete", json("POST", { endpoint })),

  saveTimes: (weekday_time: string, weekend_time: string) =>
    fetchAPI<PushConfig>("/api/push/settings", json("PUT", { weekday_time, weekend_time })),

  test: () => fetchAPI<{ sent: number; failed: number }>("/api/push/test", json("POST")),
};
