import { type AgentTool, toggleTool } from "../../lib/agents";

interface Props {
  tools: AgentTool[];
  selected: string[];
  onChange: (names: string[]) => void;
}

const ROW_CLASS = "flex h-full cursor-pointer items-start gap-2.5 rounded-xl border border-line p-3 hover:bg-surface-2";

/** What an agent may look at: the plain label and description of each, never the name it is saved under. */
export function ToolPicker({ tools, selected, onChange }: Props) {
  return (
    <ul className="grid gap-2 sm:grid-cols-2">
      {tools.map((tool) => (
        <li key={tool.name}>
          <label className={ROW_CLASS}>
            <input
              type="checkbox"
              className="mt-0.5 size-4 accent-[var(--q-brand)]"
              checked={selected.includes(tool.name)}
              onChange={() => onChange(toggleTool(selected, tool.name))}
            />
            <span className="min-w-0">
              <span className="block text-sm font-medium text-ink">{tool.label}</span>
              <span className="block text-[12.5px] text-ink-3">{tool.description}</span>
            </span>
          </label>
        </li>
      ))}
    </ul>
  );
}
