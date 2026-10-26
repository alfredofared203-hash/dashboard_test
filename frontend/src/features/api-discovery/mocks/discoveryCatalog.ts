import type {
  DiscoveryCatalog,
  DiscoveredEndpoint,
  DiscoveredService,
} from "../types/discovery";

const services: DiscoveredService[] = [
  {
    id: "backend",
    name: "Backend API",
    description: "Core application and health endpoints",
    status: "available",
    endpointCount: 2,
  },
  {
    id: "orders",
    name: "Orders Service",
    description: "Order lookup and submission metadata",
    status: "degraded",
    endpointCount: 3,
  },
  {
    id: "frontend",
    name: "Frontend Gateway",
    description: "Frontend-facing configuration endpoints",
    status: "available",
    endpointCount: 1,
  },
];

const endpoints: DiscoveredEndpoint[] = [
  {
    id: "backend-health",
    serviceId: "backend",
    name: "Get service health",
    method: "GET",
    path: "/health",
    description: "Returns the advertised health state of the backend service.",
    authentication: { required: false, type: "None", requiredHeaders: [], description: "No authentication is declared for this endpoint." },
    parameters: [],
    requestSchema: null,
    responseSchemas: [{ statusCode: 200, description: "Service health metadata", schema: { type: "object", properties: { status: { type: "string", enum: ["healthy", "degraded"] }, version: { type: "string" } }, required: ["status", "version"] } }],
  },
  {
    id: "backend-version",
    serviceId: "backend",
    name: "Get service version",
    method: "GET",
    path: "/version",
    description: "Describes the version and build metadata exposed by the service.",
    authentication: { required: false, type: "None", requiredHeaders: [], description: "No authentication is declared for this endpoint." },
    parameters: [],
    requestSchema: null,
    responseSchemas: [{ statusCode: 200, description: "Version metadata", schema: { type: "object", properties: { version: { type: "string" }, build: { type: "string" } }, required: ["version"] } }],
  },
  {
    id: "orders-list",
    serviceId: "orders",
    name: "List orders",
    method: "GET",
    path: "/orders",
    description: "Returns order summaries with optional status and pagination filters.",
    authentication: { required: true, type: "Bearer token", requiredHeaders: ["Authorization"], scopes: ["orders:read"], description: "A bearer token with orders:read scope is required." },
    parameters: [
      { name: "status", location: "query", type: "string", required: false, description: "Optional order state filter." },
      { name: "page", location: "query", type: "integer", required: false, description: "Page number, starting at 1." },
      { name: "Authorization", location: "header", type: "string", required: true, description: "Bearer access token." },
    ],
    requestSchema: null,
    responseSchemas: [{ statusCode: 200, description: "Order collection", schema: { type: "object", properties: { items: { type: "array", items: { type: "object", properties: { id: { type: "string" }, status: { type: "string" }, total: { type: "number" }, currency: { type: "string" } } } }, page: { type: "integer" }, total: { type: "integer" } }, required: ["items", "page", "total"] } }],
  },
  {
    id: "orders-get",
    serviceId: "orders",
    name: "Get order",
    method: "GET",
    path: "/orders/{id}",
    description: "Returns order details, line items, and current status.",
    authentication: { required: true, type: "Bearer token", requiredHeaders: ["Authorization"], scopes: ["orders:read"], description: "A bearer token with orders:read scope is required." },
    parameters: [
      { name: "id", location: "path", type: "string", required: true, description: "Stable order identifier." },
      { name: "Authorization", location: "header", type: "string", required: true, description: "Bearer access token." },
    ],
    requestSchema: null,
    responseSchemas: [{ statusCode: 200, description: "Order details", schema: { type: "object", properties: { id: { type: "string" }, status: { type: "string" }, items: { type: "array", items: { type: "object", properties: { sku: { type: "string" }, quantity: { type: "integer" } }, required: ["sku", "quantity"] } }, total: { type: "number" } }, required: ["id", "status", "items", "total"] } }],
  },
  {
    id: "orders-create",
    serviceId: "orders",
    name: "Create order",
    method: "POST",
    path: "/orders",
    description: "Describes the payload accepted to create a new order.",
    authentication: { required: true, type: "Bearer token", requiredHeaders: ["Authorization", "Content-Type"], scopes: ["orders:write"], description: "A bearer token with orders:write scope is required." },
    parameters: [
      { name: "Authorization", location: "header", type: "string", required: true, description: "Bearer access token." },
      { name: "Content-Type", location: "header", type: "string", required: true, description: "Expected value: application/json." },
      { name: "body", location: "body", type: "CreateOrderRequest", required: true, description: "Order items and customer reference." },
    ],
    requestSchema: {
      type: "object",
      properties: {
        customerId: { type: "string" },
        items: {
          type: "array",
          items: {
            type: "object",
            properties: {
              sku: { type: "string" },
              quantity: { type: "integer", minimum: 1 },
            },
            required: ["sku", "quantity"],
          },
        },
      },
      required: ["customerId", "items"],
    },
    responseSchemas: [{ statusCode: 201, description: "Created order", schema: { type: "object", properties: { id: { type: "string" }, status: { type: "string" } }, required: ["id", "status"] } }],
  },
  {
    id: "frontend-config",
    serviceId: "frontend",
    name: "Get public application config",
    method: "GET",
    path: "/config",
    description: "Describes non-secret configuration exposed to the frontend client.",
    authentication: { required: false, type: "None", requiredHeaders: [], description: "This catalog entry is marked public." },
    parameters: [],
    requestSchema: null,
    responseSchemas: [{ statusCode: 200, description: "Public application settings", schema: { type: "object", properties: { appName: { type: "string" }, supportUrl: { type: "string", format: "uri" } }, required: ["appName"] } }],
  },
];

export const mockDiscoveryCatalog: DiscoveryCatalog = { services, endpoints };
