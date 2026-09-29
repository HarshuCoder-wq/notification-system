// OneSignal Web Push helpers. The browser is linked to our user via external_id = user.id,
// so the backend can target a user with include_aliases.external_id.
import OneSignal from "react-onesignal";

const APP_ID = import.meta.env.VITE_ONESIGNAL_APP_ID;
let ready = null;

export function initPush() {
  if (!APP_ID) return Promise.resolve(false);
  if (!ready) {
    ready = OneSignal.init({
      appId: APP_ID,
      allowLocalhostAsSecureOrigin: true,
      serviceWorkerPath: "OneSignalSDKWorker.js",
    })
      .then(() => true)
      .catch((e) => {
        console.warn("OneSignal init failed", e);
        return false;
      });
  }
  return ready;
}

export async function linkUser(userId) {
  if (await initPush()) await OneSignal.login(String(userId));
}

export async function unlinkUser() {
  if (await initPush()) await OneSignal.logout();
}

export async function subscribe() {
  if (!(await initPush())) throw new Error("OneSignal is not configured (VITE_ONESIGNAL_APP_ID)");
  await OneSignal.Notifications.requestPermission();
  await OneSignal.User.PushSubscription.optIn();
  return isSubscribed();
}

export async function isSubscribed() {
  if (!(await initPush())) return false;
  return Boolean(OneSignal.User.PushSubscription.optedIn);
}

export async function onSubscriptionChange(cb) {
  if (await initPush()) OneSignal.User.PushSubscription.addEventListener("change", () => cb(isSubscribed()));
}
