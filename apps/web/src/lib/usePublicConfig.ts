import { useEffect, useState } from "react";
import { type PublicConfig } from "./publicConfig";

export function usePublicConfig(): { config: PublicConfig | null; fetchFailed: boolean } {
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [fetchFailed, setFetchFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/v1/public/config")
      .then(async (response) => {
        if (!response.ok) {
          throw new Error("config unavailable");
        }
        return (await response.json()) as PublicConfig;
      })
      .then((data) => {
        if (!cancelled) {
          setConfig(data);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setFetchFailed(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return { config, fetchFailed };
}

export function useApiHealth(): "loading" | "online" | "offline" {
  const [status, setStatus] = useState<"loading" | "online" | "offline">("loading");

  useEffect(() => {
    let cancelled = false;
    fetch("/api/v1/health")
      .then((response) => {
        if (!cancelled) {
          setStatus(response.ok ? "online" : "offline");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setStatus("offline");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return status;
}
