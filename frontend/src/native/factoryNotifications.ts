import { Capacitor, registerPlugin } from "@capacitor/core";

interface FactoryNotificationsPlugin {
  isAvailable(): Promise<{ native: boolean; permissionGranted: boolean }>;
  ensurePermission(): Promise<{ granted: boolean }>;
  scheduleFactoryAlerts(options: {
    alertCount: number;
    shortageCount: number;
    intervalMinutes: number;
  }): Promise<{ scheduled?: boolean; intervalMinutes?: number }>;
  cancelFactoryAlerts(): Promise<void>;
}

const FactoryNotifications = registerPlugin<FactoryNotificationsPlugin>("FactoryNotifications");

export function canUseNativeNotifications(): boolean {
  return Capacitor.isNativePlatform() && Capacitor.isPluginAvailable("FactoryNotifications");
}

export async function ensureNativeNotificationPermission(): Promise<boolean> {
  if (!canUseNativeNotifications()) return false;
  try {
    const result = await FactoryNotifications.ensurePermission();
    return Boolean(result.granted);
  } catch {
    return false;
  }
}

export async function scheduleFactoryAttentionNotifications(input: {
  alertCount: number;
  shortageCount: number;
  intervalMinutes?: number;
}): Promise<boolean> {
  if (!canUseNativeNotifications()) return false;
  const granted = await ensureNativeNotificationPermission();
  if (!granted) return false;
  await FactoryNotifications.scheduleFactoryAlerts({
    alertCount: input.alertCount,
    shortageCount: input.shortageCount,
    intervalMinutes: input.intervalMinutes ?? 120,
  });
  return true;
}

export async function cancelFactoryAttentionNotifications(): Promise<void> {
  if (!canUseNativeNotifications()) return;
  try {
    await FactoryNotifications.cancelFactoryAlerts();
  } catch {
    /* ignore cleanup failures */
  }
}
