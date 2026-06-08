"use client";

import { useState } from "react";
import { Check, FileText, Loader2, Pencil, X } from "lucide-react";
import { client } from "@/lib/api";
import { useBank } from "@/lib/bank-context";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";

interface DocumentContentEditorProps {
  document: EditableDocument;
  maxHeightClassName?: string;
  onSaved?: (document: unknown) => void;
  onQueued?: () => void;
}

interface EditableDocument {
  id: string;
  original_text?: string;
  retain_params?: {
    context?: string;
    event_date?: string;
    metadata?: Record<string, string>;
    entities?: Array<{ text: string; type?: string }>;
    observation_scopes?: "per_tag" | "combined" | "all_combinations" | string[][];
    strategy?: string;
  };
  tags?: string[];
}

function buildRetainItem(
  document: EditableDocument,
  content: string
): Parameters<typeof client.retain>[0]["items"][number] {
  const retainParams = document.retain_params ?? {};
  const item: Parameters<typeof client.retain>[0]["items"][number] = {
    content,
    document_id: document.id,
    update_mode: "replace",
  };

  if (retainParams.context) item.context = retainParams.context;
  if (retainParams.event_date) item.timestamp = retainParams.event_date;
  if (retainParams.metadata && Object.keys(retainParams.metadata).length > 0) {
    item.metadata = retainParams.metadata;
  }
  if (retainParams.entities && retainParams.entities.length > 0) {
    item.entities = retainParams.entities;
  }
  if (document.tags && document.tags.length > 0) {
    item.tags = document.tags;
  }
  if (retainParams.observation_scopes !== undefined) {
    item.observation_scopes = retainParams.observation_scopes;
  }
  if (retainParams.strategy) {
    item.strategy = retainParams.strategy;
  }

  return item;
}

function isBatchSyncRejection(error: unknown) {
  const message = error instanceof Error ? error.message : String(error);
  return (
    message.includes("HINDSIGHT_API_RETAIN_BATCH_ENABLED=true") ||
    message.includes("Batch API is enabled")
  );
}

export function DocumentContentEditor({
  document,
  maxHeightClassName = "max-h-[300px]",
  onSaved,
  onQueued,
}: DocumentContentEditorProps) {
  const { currentBank } = useBank();
  const [editing, setEditing] = useState(false);
  const [contentInput, setContentInput] = useState("");
  const [saving, setSaving] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  const originalText = document?.original_text ?? "";

  const startEdit = () => {
    setContentInput(originalText);
    setStatus(null);
    setEditing(true);
  };

  const cancelEdit = () => {
    setEditing(false);
    setContentInput("");
    setStatus(null);
  };

  const saveContent = async () => {
    if (!currentBank || !document) return;

    const newContent = contentInput;
    if (!newContent.trim()) return;

    const item = buildRetainItem(document, newContent);

    setSaving(true);
    setStatus(null);
    try {
      try {
        await client.retain({
          bank_id: currentBank,
          items: [item],
          async: false,
        });
        const refreshed = await client.getDocument(document.id, currentBank);
        onSaved?.(refreshed);
        setStatus("Document saved. Retain completed and consolidation was queued if enabled.");
      } catch (error) {
        if (!isBatchSyncRejection(error)) {
          throw error;
        }
        // Batch retain mode rejects sync requests because they can outlive the HTTP request.
        // Queue the same replace retain instead so document edits still work in that deployment mode.
        const queued = await client.retain({
          bank_id: currentBank,
          items: [item],
          async: true,
        });
        const operationId = (queued as { operation_id?: string }).operation_id;
        onQueued?.();
        setStatus(
          operationId
            ? `Document update queued. Operation: ${operationId}`
            : "Document update queued. Retain will run in the background."
        );
      }
      setEditing(false);
      setContentInput("");
    } catch (error) {
      console.error("Error updating document content:", error);
      setStatus(`Error updating document: ${(error as Error).message}`);
    } finally {
      setSaving(false);
    }
  };

  if (editing) {
    return (
      <div className="space-y-2">
        <Textarea
          value={contentInput}
          onChange={(e) => setContentInput(e.target.value)}
          className="min-h-[300px] p-4 bg-muted rounded-lg border-border text-sm whitespace-pre-wrap font-mono text-foreground resize-y"
          autoFocus
        />
        <div className="flex items-center justify-between gap-2">
          <p className="text-xs text-muted-foreground">
            Saving re-ingests this document and replaces its derived memories.
          </p>
          <div className="flex gap-2">
            <Button
              size="sm"
              onClick={saveContent}
              disabled={saving || !contentInput.trim()}
              className="h-7 px-3 gap-1 text-xs"
            >
              {saving ? (
                <Loader2 className="h-3 w-3 animate-spin" />
              ) : (
                <Check className="h-3 w-3" />
              )}
              Save
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={cancelEdit}
              disabled={saving}
              className="h-7 px-3 gap-1 text-xs"
            >
              <X className="h-3 w-3" />
              Cancel
            </Button>
          </div>
        </div>
        {status && (
          <p
            className={`text-xs ${
              status.startsWith("Error") ? "text-destructive" : "text-muted-foreground"
            }`}
          >
            {status}
          </p>
        )}
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between gap-2 mb-2">
        <div className="flex items-center gap-1.5 text-xs font-bold text-muted-foreground uppercase">
          <FileText className="w-3.5 h-3.5" />
          Original Text
          <span className="font-normal normal-case text-muted-foreground/70">
            &middot; {originalText.length.toLocaleString()} chars
          </span>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={startEdit}
          className="h-7 px-2 gap-1 text-xs"
        >
          <Pencil className="h-3 w-3" />
          Edit
        </Button>
      </div>
      <div
        className={`p-4 bg-muted rounded-lg border border-border overflow-y-auto ${maxHeightClassName}`}
      >
        <pre className="text-sm whitespace-pre-wrap font-mono text-foreground">{originalText}</pre>
      </div>
      {status && (
        <p
          className={`mt-2 text-xs ${
            status.startsWith("Error") ? "text-destructive" : "text-muted-foreground"
          }`}
        >
          {status}
        </p>
      )}
    </div>
  );
}
