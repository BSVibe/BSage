"use client";

import { useCallback, useRef, useState } from "react";
import { api } from "../../api/client";
import { Icon } from "../common/Icon";

type Status = "idle" | "uploading" | "running" | "done" | "error";

export interface PluginUploadModalProps {
  /** Plugin name to invoke after upload completes (e.g. chatgpt-memory-input). */
  pluginName: string;
  /** Modal title shown to the user. */
  title: string;
  /** Short subtitle / accepted-file hint. */
  subtitle?: string;
  /** Comma-separated `accept` list for the file input. */
  accept?: string;
  /** Closes the modal — caller controls visibility. */
  onClose: () => void;
  /** Optional callback fired once the plugin run completes. */
  onComplete?: (results: unknown[]) => void;
}

export function PluginUploadModal({
  pluginName,
  title,
  subtitle,
  accept,
  onClose,
  onComplete,
}: PluginUploadModalProps) {
  const [file, setFile] = useState<File | null>(null);
  const [status, setStatus] = useState<Status>("idle");
  const [error, setError] = useState<string | null>(null);
  const [progress, setProgress] = useState<string>("");
  const inputRef = useRef<HTMLInputElement>(null);

  const onPick = useCallback((picked: File | null) => {
    setFile(picked);
    setError(null);
    setStatus("idle");
  }, []);

  const onDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    const dropped = e.dataTransfer.files?.[0];
    if (dropped) onPick(dropped);
  }, [onPick]);

  const submit = useCallback(async () => {
    if (!file) return;
    setError(null);
    try {
      setStatus("uploading");
      setProgress(`Uploading ${file.name}…`);
      const upload = await api.uploadFile(file);

      setStatus("running");
      setProgress(`Running ${pluginName}…`);
      const result = await api.runWithInput(pluginName, {
        upload_id: upload.upload_id,
        path: upload.path,
        filename: upload.filename,
      });

      setStatus("done");
      setProgress("");
      onComplete?.(result.results);
    } catch (err) {
      setStatus("error");
      setError(err instanceof Error ? err.message : String(err));
    }
  }, [file, pluginName, onComplete]);

  const busy = status === "uploading" || status === "running";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur"
      onClick={busy ? undefined : onClose}
    >
      <div
        className="w-full max-w-md rounded-xl bg-surface border border-white/10 p-6"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between mb-4">
          <div>
            <h2 className="font-headline font-bold text-on-surface">{title}</h2>
            {subtitle && (
              <p className="text-xs text-gray-400 mt-1">{subtitle}</p>
            )}
          </div>
          <button
            onClick={onClose}
            disabled={busy}
            className="text-gray-500 hover:text-gray-300 disabled:opacity-40"
            aria-label="Close"
          >
            <Icon name="close" size={20} />
          </button>
        </div>

        <div
          onDragOver={(e) => e.preventDefault()}
          onDrop={onDrop}
          onClick={() => !busy && inputRef.current?.click()}
          className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
            file ? "border-accent-light/40 bg-accent-light/5" : "border-white/10 hover:border-white/20"
          } ${busy ? "pointer-events-none opacity-60" : ""}`}
        >
          <Icon
            name={file ? "description" : "upload_file"}
            className="mx-auto mb-2 text-gray-400"
            size={32}
          />
          {file ? (
            <>
              <p className="text-sm text-on-surface truncate">{file.name}</p>
              <p className="text-[10px] text-gray-500 mt-1">
                {(file.size / 1024).toFixed(1)} KB
              </p>
            </>
          ) : (
            <>
              <p className="text-sm text-gray-300">Drop file here or click to choose</p>
              {accept && (
                <p className="text-[10px] text-gray-500 mt-1">Accepted: {accept}</p>
              )}
            </>
          )}
          <input
            ref={inputRef}
            type="file"
            accept={accept}
            className="hidden"
            onChange={(e) => onPick(e.target.files?.[0] ?? null)}
          />
        </div>

        {progress && (
          <p className="text-xs text-gray-400 mt-4 font-mono">{progress}</p>
        )}
        {error && (
          <p className="text-xs text-red-400 mt-4 font-mono break-words">{error}</p>
        )}
        {status === "done" && (
          <p className="text-xs text-accent-light mt-4">Import complete.</p>
        )}

        <div className="flex justify-end gap-2 mt-6">
          <button
            onClick={onClose}
            disabled={busy}
            className="px-4 py-2 rounded-lg text-sm text-gray-300 hover:bg-white/5 disabled:opacity-40"
          >
            {status === "done" ? "Close" : "Cancel"}
          </button>
          {status !== "done" && (
            <button
              onClick={submit}
              disabled={!file || busy}
              className="px-4 py-2 rounded-lg bg-accent-light text-gray-950 font-bold text-sm disabled:opacity-40"
            >
              {busy ? "Working…" : "Import"}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
