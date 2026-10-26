import { mockDiscoveryProvider } from "./services/discoveryProvider";

export type {
  ApiParameter,
  ApiSchemaValue,
  DiscoveredEndpoint,
  DiscoveredService,
  DiscoveryCatalog,
  HttpMethod,
  ParameterLocation,
} from "./types/discovery";

export function getDiscoveryCatalog() {
  return mockDiscoveryProvider.getCatalog();
}
