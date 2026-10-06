import { type AgentTool, toggleTool } from "../../lib/agents";

interface Props {
  tools: AgentTool[];
  selected: string[];
  onChange: (names: string[]) => void;
}

const ROW_CLASS = "flex h-full cursor-pointer items-start gap-2.5 rounded-xl border border-line p-3 hover:bg-surface-2";

interface RowProps {
  tool: AgentTool;
  checked: boolean;
  onToggle: () => void;
}

function ToolRow({ tool, checked, onToggle }: RowProps) {
  return (
    <label className={ROW_CLASS}>
      <input type="checkbox" className="mt-0.5 size-4 accent-[var(--q-brand)]" checked={checked} onChange={onToggle} />
      <span className="min-w-0">
        <span className="block text-sm font-medium text-ink">{tool.label}</span>
        {tool.help ? <span className="block text-[12.5px] text-ink-3">{tool.help}</span> : null}
      </span>
    </label>
  );
}

/**
 * What an agent may look at: the plain label and help line of each. Never the name it is saved under, and never its
 * `description`, which is written for the AI model (it names code and gives instructions).
 */
export function ToolPicker({ tools, selected, onChange }: Props) {
  return (
    <ul className="grid gap-2 sm:grid-cols-2">
      {tools.map((tool) => (
        <li key={tool.name}>
          <ToolRow
            tool={tool}
            checked={selected.includes(tool.name)}
            onToggle={() => onChange(toggleTool(selected, tool.name))}
          />
        </li>
      ))}
    </ul>
  );
}
