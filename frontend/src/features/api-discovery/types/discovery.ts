export type HttpMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
export type ServiceAvailability = "available" | "degraded";
export type ParameterLocation = "path" | "query" | "header" | "body";
export type ApiSchemaValue =
  | string
  | number
  | boolean
  | null
  | ApiSchemaValue[]
  | { [key: string]: ApiSchemaValue };

export interface DiscoveredService {
  id: string;
  name: string;
  description: string;
  status: ServiceAvailability;
  endpointCount: number;
}

export interface ApiParameter {
  name: string;
  location: ParameterLocation;
  type: string;
  required: boolean;
  description: string;
}

export interface ApiAuthentication {
  required: boolean;
  type: string;
  requiredHeaders: string[];
  scopes?: string[];
  description: string;
}

export interface ApiResponseSchema {
  statusCode: number;
  description: string;
  schema: ApiSchemaValue;
}

export interface DiscoveredEndpoint {
  id: string;
  serviceId: string;
  name: string;
  method: HttpMethod;
  path: string;
  description: string;
  authentication: ApiAuthentication;
  parameters: ApiParameter[];
  requestSchema: ApiSchemaValue | null;
  responseSchemas: ApiResponseSchema[];
}

export interface DiscoveryCatalog {
  services: DiscoveredService[];
  endpoints: DiscoveredEndpoint[];
}

export type DiscoveryStatus = "loading" | "success" | "empty" | "error";
