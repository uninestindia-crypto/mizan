import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { AgentTool } from "../../lib/agents";
import { ToolPicker } from "./ToolPicker";

afterEach(cleanup);

// `description` is written for the AI model: it names code and gives instructions. A person must never be shown it.
const TOOLS: AgentTool[] = [
  {
    name: "shariah_check",
    label: "Halal screening",
    help: "Checks a stock against the halal standards and shows every figure it used.",
    description: "Only this tool may state a halal verdict. screen is one of: stock, settings_keys.",
  },
  {
    name: "evidence_status",
    label: "What the evidence says",
    help: "Lets the assistant say plainly what QuantOS's own research has shown.",
    description: "Quote it when asked whether a pick is good.",
  },
];

describe("choosing what an assistant may look at", () => {
  it("shows each choice by its plain label with the plain help line under it", () => {
    render(<ToolPicker tools={TOOLS} selected={[]} onChange={() => undefined} />);
    expect(screen.getByRole("checkbox", { name: /Halal screening/ })).toBeInTheDocument();
    const help = "Checks a stock against the halal standards and shows every figure it used.";
    expect(screen.getByText(help)).toBeInTheDocument();
    expect(screen.getByText("What the evidence says")).toBeInTheDocument();
  });

  it.each(["Only this tool", "settings_keys", "Quote it", "screen is one of", "shariah_check", "evidence_status"])(
    "never shows %s, which is written for the model or is the name a choice is saved under",
    (hidden) => {
      const { container } = render(<ToolPicker tools={TOOLS} selected={[]} onChange={() => undefined} />);
      expect(container.textContent).not.toContain(hidden);
    },
  );

  it("shows no empty line under a label when a tool has no help text", () => {
    const bare: AgentTool[] = [{ name: "find_stock", label: "Find a stock", help: "", description: "For the model." }];
    const { container } = render(<ToolPicker tools={bare} selected={[]} onChange={() => undefined} />);
    expect(container.textContent).toBe("Find a stock");
    expect(container.querySelectorAll("span.block")).toHaveLength(1);
  });

  it("ticks what is selected and reports the saved names when one is clicked", () => {
    const onChange = vi.fn();
    render(<ToolPicker tools={TOOLS} selected={["shariah_check"]} onChange={onChange} />);
    expect(screen.getByRole("checkbox", { name: /Halal screening/ })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: /What the evidence says/ })).not.toBeChecked();
    fireEvent.click(screen.getByRole("checkbox", { name: /What the evidence says/ }));
    expect(onChange).toHaveBeenCalledWith(["shariah_check", "evidence_status"]);
  });
});
