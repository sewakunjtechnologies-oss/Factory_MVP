import { useEffect, useRef } from "react";

import { useDashboard } from "./useDashboard";
import { cancelFactoryAttentionNotifications, scheduleFactoryAttentionNotifications } from "../native/factoryNotifications";

const TWO_HOURS_MINUTES = 120;

export function useApkAlertNotifications() {
  const dashboard = useDashboard();
  const lastSignatureRef = useRef<string>("");

  useEffect(() => {
    const data = dashboard.data;
    if (!data) return;

    const alertCount = data.alerts.filter((alert) => !alert.is_resolved).length;
    const shortageCount = data.fabric_shortages;
    const signature = `${alertCount}:${shortageCount}`;
    if (lastSignatureRef.current === signature) return;
    lastSignatureRef.current = signature;

    if (alertCount <= 0 && shortageCount <= 0) {
      void cancelFactoryAttentionNotifications();
      return;
    }

    void scheduleFactoryAttentionNotifications({
      alertCount,
      shortageCount,
      intervalMinutes: TWO_HOURS_MINUTES,
    });
  }, [dashboard.data]);
}
