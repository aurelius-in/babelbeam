import { bannerState, type PublicConfig } from "../lib/publicConfig";
import { useI18n } from "../app/i18n";

export function SimulatedModeBanner({
  config,
  fetchFailed,
}: {
  config: PublicConfig | null;
  fetchFailed: boolean;
}) {
  const { t } = useI18n();
  const state = bannerState(config, fetchFailed);
  if (state === "live") {
    return null;
  }
  const text = state === "simulated" ? t("simulated") : t("unknown");

  return (
    <div className={`sim-banner sim-banner-${state}`} role="status">
      {text}
    </div>
  );
}
