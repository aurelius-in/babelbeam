export type PublicConfig = {
  app_name: string;
  provider_mode: string;
  simulated: boolean;
  price_cents: number;
  trial_days: number;
  currency: string;
  student_price_cents: number;
  max_student_listeners: number;
  included_class_seconds: number;
  plan_limits_approved: boolean;
  limits_are_proposed: boolean;
  minors_enabled: boolean;
  production_billing_enabled: boolean;
  billing_implemented: boolean;
};

export type BannerState = "simulated" | "live" | "unknown";

export function bannerState(
  config: PublicConfig | null,
  fetchFailed: boolean,
): BannerState {
  if (fetchFailed || config === null) {
    return "unknown";
  }
  return config.simulated ? "simulated" : "live";
}

export function formatUsd(cents: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
  }).format(cents / 100);
}

export function formatMinutes(seconds: number): number {
  return Math.round(seconds / 60);
}
