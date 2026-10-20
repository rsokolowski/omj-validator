// This browser's push subscription (reminders about due wzorce)
import { pushApi } from "@/lib/api/push";

const FORGET_TIMEOUT_MS = 2000;

export async function currentSubscription(): Promise<PushSubscription | null> {
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) return null;
  const registration = await navigator.serviceWorker.getRegistration("/");
  return (await registration?.pushManager.getSubscription()) ?? null;
}

/**
 * Switch reminders off on this device (logout). Never throws and never takes
 * longer than FORGET_TIMEOUT_MS - logging out must not depend on it.
 */
export async function forgetThisDevice(): Promise<void> {
  const forget = (async () => {
    const subscription = await currentSubscription();
    if (!subscription) return;
    const endpoint = subscription.endpoint;
    await pushApi.unsubscribe(endpoint).catch(() => undefined);
    await subscription.unsubscribe();
  })().catch(() => undefined);
  await Promise.race([forget, new Promise((resolve) => setTimeout(resolve, FORGET_TIMEOUT_MS))]);
}
