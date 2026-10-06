import { cleanup, fireEvent, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { card, daily, engine, mine, needsAi, ready } from "../components/agents/agentFixtures";
import { renderApp } from "../components/agents/testHarness";
import { api } from "../lib/api";
import Agents from "./Agents";

vi.mock("../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../lib/api")>();
  return { ...real, api: vi.fn() };
});

beforeEach(() => {
  vi.mocked(api).mockReset();
});
afterEach(cleanup);

// ------------------------------------------------------------------------------------------------ keyboard focus

/** What has focus, as a person would name it: the button's words, or the heading's. */
const focusedName = () => (document.activeElement as HTMLElement | null)?.textContent?.trim() ?? "";
const headingText = (level: number) => screen.getByRole("heading", { level }).textContent;

describe("where keyboard focus goes", () => {
  async function onList() {
    engine({ "DELETE /api/v2/copilot/agents/mine1": { deleted: true } });
    renderApp(<Agents />);
    await screen.findByRole("heading", { name: "My halal check" });
  }
  const deleteButton = () => within(card("My halal check")).getByRole("button", { name: "Delete" });

  it("returns to the Delete button when the question is answered Keep it, or closed with Escape", async () => {
    await onList();
    const keepIt = () => fireEvent.click(screen.getByRole("button", { name: "Keep it" }));
    const escape = () => fireEvent.keyDown(screen.getByRole("dialog"), { key: "Escape" });
    for (const close of [keepIt, escape]) {
      deleteButton().focus();
      fireEvent.click(deleteButton());
      await screen.findByRole("dialog", { name: "Delete My halal check?" });
      close();
      await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
      await waitFor(() => expect(deleteButton()).toHaveFocus());
    }
  });

  it("lands on the My agents heading, not on the page, once the agent is deleted and its button is gone", async () => {
    let agents = [mine, daily];
    engine({
      "GET /api/v2/copilot/agents": () => ({ agents, recipes: [ready, needsAi] }),
      "DELETE /api/v2/copilot/agents/mine1": () => {
        agents = [daily];
        return { deleted: true };
      },
    });
    renderApp(<Agents />);
    await screen.findByRole("heading", { name: "My halal check" });
    deleteButton().focus();
    fireEvent.click(deleteButton());
    await screen.findByRole("dialog");
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(focusedName()).toBe("My agents"));
  });

  it("starts a new form at its heading, and comes back to the New agent button when it is left", async () => {
    await onList();
    const open = screen.getByRole("button", { name: "New agent" });
    open.focus();
    fireEvent.click(open);
    await screen.findByLabelText("Name");
    expect(focusedName()).toBe("New agent");
    expect(headingText(1)).toBe("New agent");
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await screen.findByRole("heading", { name: "My halal check" });
    await waitFor(() => expect(screen.getByRole("button", { name: "New agent" })).toHaveFocus());
  });

  it("comes back to that agent's Edit button after saving, and says what was saved", async () => {
    engine({ "PUT /api/v2/copilot/agents/mine1": { ...mine, name: "Renamed" } });
    renderApp(<Agents />);
    await screen.findByRole("heading", { name: "My halal check" });
    const edit = within(card("My halal check")).getByRole("button", { name: "Edit" });
    edit.focus();
    fireEvent.click(edit);
    await screen.findByRole("checkbox", { name: /Halal screening/ });
    expect(focusedName()).toBe("Edit My halal check");
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    expect(await screen.findByText("Saved Renamed.")).toBeInTheDocument();
    await waitFor(() => expect(within(card("My halal check")).getByRole("button", { name: "Edit" })).toHaveFocus());
  });

  it("goes back to Cancel on Keep editing, and to the Edit button on Discard changes", async () => {
    await onList();
    const edit = within(card("My halal check")).getByRole("button", { name: "Edit" });
    edit.focus();
    fireEvent.click(edit);
    await screen.findByRole("checkbox", { name: /Halal screening/ });
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Changed" } });
    const cancel = screen.getByRole("button", { name: "Cancel" });
    cancel.focus();
    fireEvent.click(cancel);
    await screen.findByRole("dialog", { name: "Leave without saving?" });
    fireEvent.click(screen.getByRole("button", { name: "Keep editing" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(cancel).toHaveFocus());
    fireEvent.click(cancel);
    await screen.findByRole("dialog", { name: "Leave without saving?" });
    fireEvent.click(screen.getByRole("button", { name: "Discard changes" }));
    await screen.findByRole("heading", { name: "My halal check" });
    await waitFor(() => expect(within(card("My halal check")).getByRole("button", { name: "Edit" })).toHaveFocus());
  });

  it("comes back to Copy and edit on a ready-made agent after its copy is saved", async () => {
    engine({ "POST /api/v2/copilot/agents": { ...mine, id: "new1", name: "My copy of Check a stock, step by step" } });
    renderApp(<Agents />);
    await screen.findByRole("heading", { name: "Check a stock, step by step" });
    const copy = within(card("Check a stock, step by step")).getByRole("button", { name: "Copy and edit" });
    copy.focus();
    fireEvent.click(copy);
    await screen.findByRole("checkbox", { name: /Price facts/ });
    fireEvent.click(screen.getByRole("button", { name: "Save" }));
    await screen.findByText("Saved My copy of Check a stock, step by step.");
    const again = () => within(card("Check a stock, step by step")).getByRole("button", { name: "Copy and edit" });
    await waitFor(() => expect(again()).toHaveFocus());
  });
});
