import { useState } from "react";
import { Plus } from "lucide-react";
import { useAddCustomCli } from "../../lib/queries";
import { Button, Callout, Dialog } from "../ui";

interface AddCustomCliModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function AddCustomCliModal({ open, onOpenChange }: AddCustomCliModalProps) {
  const addCli = useAddCustomCli();
  const [name, setName] = useState("");
  const [maker, setMaker] = useState("");
  const [command, setCommand] = useState("");
  const [installCmd, setInstallCmd] = useState("");
  const [updateCmd, setUpdateCmd] = useState("");
  const [description, setDescription] = useState("");
  const [docsUrl, setDocsUrl] = useState("");
  const [statusArgs, setStatusArgs] = useState("--version");
  const [autoUpdate, setAutoUpdate] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const trimmedName = name.trim();
    const trimmedMaker = maker.trim();
    const trimmedCommand = command.trim();
    const trimmedInstall = installCmd.trim();
    const trimmedUpdate = updateCmd.trim();

    if (!trimmedName || !trimmedMaker || !trimmedCommand || !trimmedInstall || !trimmedUpdate) {
      setError("Please fill in all required fields.");
      return;
    }

    const slug = trimmedName
      .toLowerCase()
      .replace(/[^a-z0-9_-]+/g, "-")
      .replace(/^-+|-+$/g, "");

    try {
      await addCli.mutateAsync({
        id: slug,
        name: trimmedName,
        maker: trimmedMaker,
        command: trimmedCommand,
        install_cmd: trimmedInstall,
        update_cmd: trimmedUpdate,
        description: description.trim() || `Enterprise AI assistant from ${trimmedMaker}.`,
        docs_url: docsUrl.trim(),
        status_args: statusArgs.trim() || "--version",
        auto_update: autoUpdate ? 1 : 0,
      });
      setName("");
      setMaker("");
      setCommand("");
      setInstallCmd("");
      setUpdateCmd("");
      setDescription("");
      setDocsUrl("");
      setStatusArgs("--version");
      setAutoUpdate(true);
      onOpenChange(false);
    } catch (err: any) {
      setError(err?.message ?? "Failed to add company app.");
    }
  };

  return (
    <Dialog
      open={open}
      onOpenChange={onOpenChange}
      title="Add company app"
      description="Register your organization's AI assistant so QuantOS Copilot can query it directly with drive isolation."
      wide
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        {error && <Callout tone="danger">{error}</Callout>}

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label className="block text-[12px] font-medium text-ink-2 mb-1">
              App Name <span className="text-brand">*</span>
            </label>
            <input
              type="text"
              required
              placeholder="e.g. Acme Copilot"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-[13px] text-ink focus:border-brand focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-[12px] font-medium text-ink-2 mb-1">
              Maker or organization <span className="text-brand">*</span>
            </label>
            <input
              type="text"
              required
              placeholder="e.g. Acme Corp"
              value={maker}
              onChange={(e) => setMaker(e.target.value)}
              className="w-full rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-[13px] text-ink focus:border-brand focus:outline-none"
            />
          </div>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <div>
            <label className="block text-[12px] font-medium text-ink-2 mb-1">
              Program name <span className="text-brand">*</span>
            </label>
            <input
              type="text"
              required
              placeholder="e.g. acme-agent"
              value={command}
              onChange={(e) => setCommand(e.target.value)}
              className="w-full rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-[13px] text-ink font-mono focus:border-brand focus:outline-none"
            />
          </div>

          <div>
            <label className="block text-[12px] font-medium text-ink-2 mb-1">
              Check status flag
            </label>
            <input
              type="text"
              placeholder="--version"
              value={statusArgs}
              onChange={(e) => setStatusArgs(e.target.value)}
              className="w-full rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-[13px] text-ink font-mono focus:border-brand focus:outline-none"
            />
          </div>
        </div>

        <div>
          <label className="block text-[12px] font-medium text-ink-2 mb-1">
            Setup instruction <span className="text-brand">*</span>
          </label>
          <input
            type="text"
            required
            placeholder="e.g. acme-setup"
            value={installCmd}
            onChange={(e) => setInstallCmd(e.target.value)}
            className="w-full rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-[13px] text-ink font-mono focus:border-brand focus:outline-none"
          />
          <p className="mt-0.5 text-[11px] text-ink-3">Executed in a background job when you choose Install.</p>
        </div>

        <div>
          <label className="block text-[12px] font-medium text-ink-2 mb-1">
            Update instruction <span className="text-brand">*</span>
          </label>
          <input
            type="text"
            required
            placeholder="e.g. acme-setup --refresh"
            value={updateCmd}
            onChange={(e) => setUpdateCmd(e.target.value)}
            className="w-full rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-[13px] text-ink font-mono focus:border-brand focus:outline-none"
          />
          <p className="mt-0.5 text-[11px] text-ink-3">Executed when you choose Update or on auto-update.</p>
        </div>

        <div>
          <label className="block text-[12px] font-medium text-ink-2 mb-1">
            Description
          </label>
          <input
            type="text"
            placeholder="e.g. Internal company assistant"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            className="w-full rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-[13px] text-ink focus:border-brand focus:outline-none"
          />
        </div>

        <div>
          <label className="block text-[12px] font-medium text-ink-2 mb-1">
            Web page address (Optional)
          </label>
          <input
            type="url"
            placeholder="https://company.internal/assistant"
            value={docsUrl}
            onChange={(e) => setDocsUrl(e.target.value)}
            className="w-full rounded-lg border border-line bg-surface-2 px-3 py-1.5 text-[13px] text-ink focus:border-brand focus:outline-none"
          />
        </div>

        <div className="flex items-center gap-2 pt-1">
          <input
            type="checkbox"
            id="auto-update-check"
            checked={autoUpdate}
            onChange={(e) => setAutoUpdate(e.target.checked)}
            className="size-4 rounded border-line text-brand focus:ring-brand accent-brand"
          />
          <label htmlFor="auto-update-check" className="text-[12.5px] text-ink cursor-pointer select-none">
            Update this app automatically
          </label>
        </div>

        <div className="flex justify-end gap-2 border-t border-line/60 pt-3">
          <Button type="button" variant="secondary" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="submit" loading={addCli.isPending} icon={<Plus className="size-3.5" aria-hidden />}>
            Add company app
          </Button>
        </div>
      </form>
    </Dialog>
  );
}
