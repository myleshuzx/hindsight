import { NextRequest, NextResponse } from "next/server";
import { lowLevelClient, sdk } from "@/lib/hindsight-client";

type RetainItem = {
  content: string;
  timestamp?: string | null;
  context?: string | null;
  metadata?: Record<string, string> | null;
  document_id?: string | null;
  entities?: Array<{ text: string; type?: string | null }> | null;
  tags?: string[] | null;
  observation_scopes?: "per_tag" | "combined" | "all_combinations" | string[][] | null;
  strategy?: string | null;
  update_mode?: "replace" | "append" | null;
};

type RetainProxyBody = {
  bank_id?: string;
  agent_id?: string;
  items?: RetainItem[];
  document_id?: string;
  document_tags?: string[];
  observation_scopes?: RetainItem["observation_scopes"];
};

function responseErrorMessage(error: unknown) {
  if (error && typeof error === "object") {
    const record = error as Record<string, unknown>;
    if (typeof record.detail === "string") return record.detail;
    if (typeof record.message === "string") return record.message;
  }
  return "Failed to batch retain";
}

export async function POST(request: NextRequest) {
  try {
    const body = (await request.json()) as RetainProxyBody;
    const bankId = body.bank_id || body.agent_id;

    if (!bankId) {
      return NextResponse.json({ error: "bank_id is required" }, { status: 400 });
    }

    const { items, document_id, document_tags, observation_scopes } = body;
    if (!items || items.length === 0) {
      return NextResponse.json({ error: "items are required" }, { status: 400 });
    }

    // Map observation_scopes into each item if provided at request level
    const mappedItems: RetainItem[] = observation_scopes
      ? items.map((item) => ({
          ...item,
          observation_scopes: item.observation_scopes ?? observation_scopes,
        }))
      : items;

    const finalItems: RetainItem[] = document_id
      ? mappedItems.map((item) => ({
          ...item,
          document_id: item.document_id ?? document_id,
        }))
      : mappedItems;

    const response = await sdk.retainMemories({
      client: lowLevelClient,
      path: { bank_id: bankId },
      body: {
        items: finalItems,
        async: false,
        document_tags,
      },
    });

    if (!response.data) {
      const errorMessage = responseErrorMessage(response.error);
      return NextResponse.json(
        { error: errorMessage, details: JSON.stringify(response.error) },
        { status: 400 }
      );
    }

    return NextResponse.json(response.data, { status: 200 });
  } catch (error: unknown) {
    console.error("Error batch retain:", error);

    const typedError = error as { message?: string; details?: unknown; statusCode?: unknown };
    const errorMessage = typedError.message || String(error);
    const errorDetails = typedError.details;
    const statusCode = typedError.statusCode;

    // If we have a statusCode, use it
    if (statusCode && typeof statusCode === "number") {
      return NextResponse.json(
        { error: errorMessage, details: errorDetails },
        { status: statusCode }
      );
    }

    // Otherwise, return generic 500 error
    return NextResponse.json({ error: errorMessage || "Failed to batch retain" }, { status: 500 });
  }
}
