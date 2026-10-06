import { AlertCircle, CheckCircle2, Upload } from "lucide-react";
import { type DragEvent, useRef, useState } from "react";
import { errorMessage } from "../lib/api";
import { type EnvUpload, readEnvFiles } from "../lib/envFile";
import { useImportCredentials } from "../lib/queries";
import type { EnvImportReply, EnvImportRow, EnvImportStatus } from "../lib/types";
import { Badge, Button, Callout, Card, CardHeader, cx, Dialog } from "./ui";

/** Statuses the founder can choose to save. The others are shown for explanation only. */
const SAVEABLE: ReadonlySet<EnvImportStatus> = new Set(["new", "replace"]);

const STATUS_BADGE: Record<"new" | "replace" | "same", { tone: "up" | "warn" | "neutral"; text: string }> = {
  new: { tone: "up", text: "New" },
  replace: { tone: "warn", text: "Replaces saved key" },
  same: { tone: "neutral", text: "Already saved" },
};

function names(rows: EnvImportRow[], status: EnvImportStatus): string[] {
  return rows.filter((row) => row.status === status).map((row) => row.name);
}

/**
 * Settings > Accounts & keys: add many keys at once from .env, .env.local and similar files.
 *
 * The files are read here and sent only to the local engine, which replies with names and statuses, never values.
 * Nothing is saved until the review is confirmed. The file text is held only while the review is open.
 */
export function EnvImport() {
  const importer = useImportCredentials();
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  const [uploads, setUploads] = useState<EnvUpload[]>([]);
  const [problems, setProblems] = useState<string[]>([]);
  const [preview, setPreview] = useState<EnvImportReply | null>(null);
  const [selected, setSelected] = useState<ReadonlySet<string>>(new Set());
  const [saved, setSaved] = useState<EnvImportReply | null>(null);
  const [failure, setFailure] = useState<string | null>(null);

  const closeReview = () => {
    setUploads([]);
    setPreview(null);
    setSelected(new Set());
    setFailure(null);
  };

  const take = async (files: File[]) => {
    if (files.length === 0) return;
    setSaved(null);
    setFailure(null);
    const read = await readEnvFiles(files);
    setProblems(read.problems);
    if (read.uploads.length === 0) return;
    importer.mutate(
      { files: read.uploads, dryRun: true },
      {
        onSuccess: (reply) => {
          setUploads(read.uploads);
          setPreview(reply);
          setSelected(new Set(reply.rows.filter((row) => SAVEABLE.has(row.status)).map((row) => row.name)));
        },
        onError: (err) => setFailure(errorMessage(err)),
      },
    );
  };

  const save = () =>
    importer.mutate(
      { files: uploads, dryRun: false, names: [...selected] },
      {
        onSuccess: (reply) => {
          setSaved(reply);
          closeReview();
        },
        onError: (err) => setFailure(errorMessage(err)),
      },
    );

  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    void take([...event.dataTransfer.files]);
  };

  const rows = preview?.rows ?? [];
  const choices = rows.filter((row) => row.status === "new" || row.status === "replace" || row.status === "same");
  const saveable = choices.filter((row) => SAVEABLE.has(row.status));
  const groups = [...new Set(choices.map((row) => row.group ?? "Other"))];
  const allSelected = saveable.length > 0 && saveable.every((row) => selected.has(row.name));
  const toggle = (name: string, on: boolean) =>
    setSelected((prev) => {
      const next = new Set(prev);
      if (on) next.add(name);
      else next.delete(name);
      return next;
    });

  const savedCount = saved?.results?.filter((r) => r.outcome === "saved").length ?? 0;
  const refused = saved?.results?.filter((r) => r.outcome === "refused") ?? [];

  return (
    <Card>
      <CardHeader
        title="Import keys from a file"
        subtitle="Instead of pasting each key, choose your .env or .env.local file. You review what was found before anything is saved."
      />
      <div
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        className={cx(
          "flex flex-col items-center gap-3 rounded-xl border border-dashed px-4 py-6 text-center transition-colors",
          dragging ? "border-brand bg-brand/5" : "border-line-strong",
        )}
      >
        <Upload className="size-6 text-ink-3" aria-hidden />
        <div>
          <div className="text-sm font-medium text-ink">Drop your .env files here</div>
          <div className="mt-1 max-w-xl text-[12.5px] text-ink-3">
            You can add several at once, such as .env and .env.local. The file stays where it is and is not changed. It is read in this window and
            sent only to QuantOS on this computer.
          </div>
        </div>
        <Button variant="secondary" loading={importer.isPending && preview === null} onClick={() => input.current?.click()}>
          Choose files
        </Button>
        <input
          ref={input}
          type="file"
          multiple
          hidden
          aria-label="Choose .env files"
          onChange={(event) => {
            void take([...(event.target.files ?? [])]);
            event.target.value = "";
          }}
        />
      </div>

      {problems.map((problem) => (
        <p key={problem} className="mt-3 text-[12.5px] text-warn">
          {problem}
        </p>
      ))}
      {failure && preview === null && (
        <p role="alert" className="mt-3 text-[13px] text-down">
          {failure}
        </p>
      )}
      {saved && (
        <Callout
          tone={savedCount > 0 ? "success" : "warn"}
          className="mt-4"
          title={savedCount > 0 ? `Saved ${savedCount} ${savedCount === 1 ? "key" : "keys"} to Windows Credential Manager` : "Nothing was saved"}
        >
          {savedCount > 0 && "They are active now. The cards below show which ones are stored."}
          {refused.length > 0 && (
            <ul className="mt-1 list-disc pl-5">
              {refused.map((item) => (
                <li key={item.name}>
                  <span className="font-mono text-[12px]">{item.name}</span>: {item.message}
                </li>
              ))}
            </ul>
          )}
        </Callout>
      )}

      <Dialog
        wide
        open={preview !== null}
        onOpenChange={(open) => {
          if (!open) closeReview();
        }}
        title="Review the keys found"
        description={`Read ${uploads.length} ${uploads.length === 1 ? "file" : "files"}. Nothing is saved until you press Save.`}
        footer={
          saveable.length === 0 ? (
            <Button variant="secondary" onClick={closeReview}>
              Close
            </Button>
          ) : (
            <>
              <Button variant="ghost" onClick={closeReview}>
                Cancel
              </Button>
              <Button onClick={save} disabled={selected.size === 0 || !preview?.available} loading={importer.isPending}>
                {selected.size === 1 ? "Save 1 key" : `Save ${selected.size} keys`}
              </Button>
            </>
          )
        }
      >
        {preview && !preview.available && (
          <Callout tone="warn" title="Keys cannot be saved on this computer" className="mb-4">
            Windows Credential Manager is not available here, so there is nowhere safe to keep them. You can still review what the file holds.
          </Callout>
        )}
        {choices.length === 0 ? (
          <Callout tone="info" title="No new keys to add">
            {rows.length === 0
              ? "That file has no keys in it."
              : "None of the keys in that file are ones QuantOS stores, or they are blank."}
          </Callout>
        ) : (
          <div className="max-h-[50vh] overflow-y-auto rounded-xl border border-line">
            <label className="flex items-center gap-3 border-b border-line bg-surface-2/60 px-3 py-2 text-[12.5px] font-medium text-ink-2">
              <input
                type="checkbox"
                className="size-4 accent-brand"
                checked={allSelected}
                disabled={saveable.length === 0}
                onChange={(event) => setSelected(new Set(event.target.checked ? saveable.map((row) => row.name) : []))}
              />
              Select all new and changed keys
            </label>
            {groups.map((group) => (
              <div key={group}>
                <div className="bg-surface-2/30 px-3 py-1.5 text-[11.5px] font-semibold uppercase tracking-wide text-ink-3">{group}</div>
                <ul className="divide-y divide-line">
                  {choices
                    .filter((row) => (row.group ?? "Other") === group)
                    .map((row) => {
                      const badge = STATUS_BADGE[row.status as "new" | "replace" | "same"];
                      return (
                        <li key={row.name}>
                          <label className={cx("flex items-start gap-3 px-3 py-2.5", row.status === "same" && "opacity-70")}>
                            <input
                              type="checkbox"
                              className="mt-1 size-4 accent-brand"
                              checked={selected.has(row.name)}
                              disabled={row.status === "same"}
                              onChange={(event) => toggle(row.name, event.target.checked)}
                            />
                            <span className="min-w-0 flex-1">
                              <span className="block text-[13.5px] font-medium text-ink">{row.label}</span>
                              <span className="block break-all font-mono text-[11.5px] text-ink-3">
                                {row.name}
                                {row.source ? ` · from ${row.source}` : ""}
                              </span>
                              {row.shadowed.length > 0 && (
                                <span className="mt-0.5 block text-[11.5px] text-ink-3">
                                  Also set to a different value in {row.shadowed.join(", ")}. The value from {row.source} is used.
                                </span>
                              )}
                            </span>
                            <Badge tone={badge.tone}>{badge.text}</Badge>
                          </label>
                        </li>
                      );
                    })}
                </ul>
              </div>
            ))}
          </div>
        )}

        {preview && <LeftOut rows={rows} unreadable={preview.unrecognised_lines} />}
        {failure && preview !== null && (
          <p role="alert" className="mt-3 flex items-center gap-2 text-[13px] text-down">
            <AlertCircle className="size-4 shrink-0" aria-hidden />
            {failure}
          </p>
        )}
        {preview && preview.available && choices.length > 0 && (
          <p className="mt-3 flex items-center gap-2 text-[12px] text-ink-3">
            <CheckCircle2 className="size-3.5 shrink-0" aria-hidden />
            Saved keys go to Windows Credential Manager, the same place as keys you paste.
          </p>
        )}
      </Dialog>
    </Card>
  );
}

/** What was in the files but will not be saved, and why. Names only. */
function LeftOut({ rows, unreadable }: { rows: EnvImportRow[]; unreadable: number }) {
  const blank = names(rows, "empty");
  const tooLong = names(rows, "too_long");
  const unused = names(rows, "unmanaged");
  if (blank.length + tooLong.length + unused.length + unreadable === 0) return null;
  return (
    <div className="mt-4 space-y-1.5 text-[12.5px] text-ink-3">
      <div className="font-medium text-ink-2">Not being saved</div>
      {unused.length > 0 && (
        <p>
          <span className="text-ink-2">Not used by QuantOS ({unused.length}):</span> <span className="break-words font-mono text-[11.5px]">{unused.join(", ")}</span>
        </p>
      )}
      {blank.length > 0 && (
        <p>
          <span className="text-ink-2">Left blank in the file:</span> <span className="break-words font-mono text-[11.5px]">{blank.join(", ")}</span>
        </p>
      )}
      {tooLong.length > 0 && (
        <p>
          <span className="text-ink-2">Too long to store:</span> <span className="break-words font-mono text-[11.5px]">{tooLong.join(", ")}</span>
        </p>
      )}
      {unreadable > 0 && <p>{unreadable} {unreadable === 1 ? "line" : "lines"} could not be read as NAME=value.</p>}
    </div>
  );
}
