import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import Tools from "./Tools";

// The AI apps card has its own tests; here it is a stand-in so only the tabs are under test.
vi.mock("../components/AgentCliBridge", () => ({ AgentCliBridge: () => <p>AI apps card</p> }));

afterEach(cleanup);

function openTools() {
  render(
    <MemoryRouter initialEntries={["/tools/agents"]}>
      <Routes>
        <Route path="/tools/:tool" element={<Tools />} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("the tabs on the Tools screen", () => {
  it("call the AI apps tab by that name, not by a developer's name for it", () => {
    openTools();
    const tabs = screen.getByRole("navigation", { name: "Tools" });
    expect(tabs.textContent).toBe("Trade costsPosition sizeOptions payoffAI apps");
    expect(screen.getByRole("link", { name: "AI apps" })).toHaveAttribute("href", "/tools/agents");
    expect(document.body.textContent).not.toMatch(/Coding agents/i);
  });

  it("show the AI apps card under that tab", () => {
    openTools();
    expect(screen.getByText("AI apps card")).toBeInTheDocument();
  });
});
