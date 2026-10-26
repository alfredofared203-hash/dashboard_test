import { useCallback, useEffect, useState } from "react";
import type { DiscoveryCatalog, DiscoveryStatus } from "../types/discovery";
import {
  mockDiscoveryProvider,
  type DiscoveryProvider,
} from "../services/discoveryProvider";

export interface DiscoveryCatalogState {
  catalog: DiscoveryCatalog;
  status: DiscoveryStatus;
  error: string | null;
  reload: () => void;
}

export function useDiscoveryCatalog(
  provider: DiscoveryProvider = mockDiscoveryProvider,
): DiscoveryCatalogState {
  const [catalog, setCatalog] = useState<DiscoveryCatalog>({ services: [], endpoints: [] });
  const [status, setStatus] = useState<DiscoveryStatus>("loading");
  const [error, setError] = useState<string | null>(null);
  const [requestKey, setRequestKey] = useState(0);

  const reload = useCallback(() => {
    setRequestKey((current) => current + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    setStatus("loading");
    setError(null);

    Promise.resolve().then(() => provider.getCatalog()).then(
      (result) => {
        if (cancelled) return;
        setCatalog(result);
        setStatus(result.services.length > 0 ? "success" : "empty");
      },
      (reason: unknown) => {
        if (cancelled) return;
        setError(reason instanceof Error ? reason.message : "The discovery catalog could not be loaded.");
        setStatus("error");
      },
    );

    return () => {
      cancelled = true;
    };
  }, [provider, requestKey]);

  return { catalog, status, error, reload };
}
