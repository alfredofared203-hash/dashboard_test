import type { DiscoveryCatalog } from "../types/discovery";
import { mockDiscoveryCatalog } from "../mocks/discoveryCatalog";

export interface DiscoveryProvider {
  getCatalog(): Promise<DiscoveryCatalog>;
}

export const mockDiscoveryProvider: DiscoveryProvider = {
  async getCatalog() {
    await new Promise<void>((resolve) => window.setTimeout(resolve, 280));
    return mockDiscoveryCatalog;
  },
};
