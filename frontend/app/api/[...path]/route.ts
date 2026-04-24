import type { NextRequest } from "next/server";

type RouteParams = Promise<{ path: string[] }>;

function buildTargetUrl(baseUrl: string, path: string[], search: string): string {
  const normalizedBaseUrl = baseUrl.endsWith("/") ? baseUrl.slice(0, -1) : baseUrl;
  return `${normalizedBaseUrl}/api/${path.join("/")}${search}`;
}

function buildForwardHeaders(request: NextRequest, apiKey: string): Headers {
  const headers = new Headers(request.headers);
  headers.delete("x-api-key");
  headers.delete("host");
  headers.delete("content-length");
  headers.set("x-api-key", apiKey);
  return headers;
}

function buildForwardInit(request: NextRequest, headers: Headers): RequestInit {
  if (request.method === "GET" || request.method === "HEAD") {
    return {
      method: request.method,
      headers,
    };
  }

  return {
    method: request.method,
    headers,
    body: request.body,
    duplex: "half",
  } as RequestInit;
}

async function proxy(request: NextRequest, context: { params: RouteParams }): Promise<Response> {
  const apiBaseUrl = process.env.API_BASE_URL;
  const apiKey = process.env.API_KEY;

  if (!apiBaseUrl || !apiKey) {
    return new Response("BFF not configured", { status: 500 });
  }

  const { path } = await context.params;
  const search = new URL(request.url).search;
  const targetUrl = buildTargetUrl(apiBaseUrl, path, search);
  const headers = buildForwardHeaders(request, apiKey);

  console.info("BFF proxy outbound request", {
    method: request.method,
    targetUrl,
    hasApiKey: true,
  });

  const upstreamResponse = await fetch(targetUrl, buildForwardInit(request, headers));
  const responseHeaders = new Headers();
  const contentType = upstreamResponse.headers.get("content-type");

  if (contentType) {
    responseHeaders.set("content-type", contentType);
  }

  return new Response(upstreamResponse.body, {
    status: upstreamResponse.status,
    headers: responseHeaders,
  });
}

export async function GET(request: NextRequest, context: { params: RouteParams }): Promise<Response> {
  return proxy(request, context);
}

export async function POST(request: NextRequest, context: { params: RouteParams }): Promise<Response> {
  return proxy(request, context);
}

export async function PUT(request: NextRequest, context: { params: RouteParams }): Promise<Response> {
  return proxy(request, context);
}

export async function DELETE(request: NextRequest, context: { params: RouteParams }): Promise<Response> {
  return proxy(request, context);
}

export async function PATCH(request: NextRequest, context: { params: RouteParams }): Promise<Response> {
  return proxy(request, context);
}

export async function OPTIONS(request: NextRequest, context: { params: RouteParams }): Promise<Response> {
  return proxy(request, context);
}

export async function HEAD(request: NextRequest, context: { params: RouteParams }): Promise<Response> {
  return proxy(request, context);
}
