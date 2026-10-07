import { cleanup, fireEvent, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../../../lib/api";
import { openDrawer, Shell } from "../chatTestKit";
import { renderApp } from "../testHarness";
import { BASE, callsStarting, FakeEngine, listedTitles, openHistory, SEED, searchBox } from "./historyKit";

vi.mock("../../../lib/api", async (importOriginal) => {
  const original = await importOriginal<typeof import("../../../lib/api")>();
  return { ...original, api: vi.fn() };
});

beforeEach(() => {
  vi.mocked(api).mockReset();
  window.localStorage.clear();
});

afterEach(cleanup);

async function showHistory() {
  const engine = new FakeEngine(SEED);
  renderApp(<Shell />);
  openDrawer();
  await screen.findByRole("dialog");
  await openHistory();
  await screen.findByRole("list", { name: "Your saved chats" });
  return engine;
}

const renameButton = (title: string) => screen.getByRole("button", { name: `Rename chat: ${title}` });
const deleteButton = (title: string) => screen.getByRole("button", { name: `Delete chat: ${title}` });
const nameField = () => screen.getByRole("textbox", { name: "Chat name" });

function startRename(title: string, typed: string) {
  fireEvent.click(renameButton(title));
  fireEvent.change(nameField(), { target: { value: typed } });
}

describe("renaming a chat", () => {
  it("edits the name in place, with the old name ready to change", async () => {
    await showHistory();
    fireEvent.click(renameButton("is AAA halal?"));
    expect(nameField()).toHaveValue("is AAA halal?");
    expect(nameField()).toHaveFocus();
    expect(nameField()).toHaveAttribute("maxlength", "80");
  });

  it("saves the new name when the form is sent (Enter), and the list shows it", async () => {
    const engine = await showHistory();
    startRename("is AAA halal?", "Halal picks");
    fireEvent.submit(nameField().closest("form") as HTMLFormElement);
    await waitFor(() => expect(listedTitles()).toContain("Halal picks"));
    expect(listedTitles()).not.toContain("is AAA halal?");
    expect(callsStarting("PUT", `${BASE}/chat-a`)[0]?.[2]).toEqual({ title: "Halal picks" });
    expect(engine.chats.find((chat) => chat.id === "chat-a")?.title).toBe("Halal picks");
    expect(screen.queryByRole("textbox", { name: "Chat name" })).toBeNull();
    await waitFor(() => expect(renameButton("Halal picks")).toHaveFocus());
  });

  it("saves with the Save name button as well", async () => {
    await showHistory();
    startRename("show my watchlist", "Watchlist check");
    fireEvent.click(screen.getByRole("button", { name: "Save name" }));
    await waitFor(() => expect(listedTitles()).toContain("Watchlist check"));
  });

  it("cancels on Escape without asking the engine, and stays in the list", async () => {
    await showHistory();
    startRename("is AAA halal?", "something else");
    fireEvent.keyDown(nameField(), { key: "Escape" });
    expect(screen.queryByRole("textbox", { name: "Chat name" })).toBeNull();
    expect(callsStarting("PUT", BASE)).toHaveLength(0);
    expect(listedTitles()).toContain("is AAA halal?");
    expect(screen.getByRole("region", { name: "Your chats" })).toBeInTheDocument();
    await waitFor(() => expect(renameButton("is AAA halal?")).toHaveFocus());
  });

  it("cancels with the Cancel button, and closes quietly when the name did not change", async () => {
    await showHistory();
    startRename("is AAA halal?", "other");
    fireEvent.click(screen.getByRole("button", { name: "Cancel rename" }));
    fireEvent.click(renameButton("is AAA halal?"));
    fireEvent.submit(nameField().closest("form") as HTMLFormElement);
    expect(screen.queryByRole("textbox", { name: "Chat name" })).toBeNull();
    expect(callsStarting("PUT", BASE)).toHaveLength(0);
  });

  it("shows the engine's own sentence when the name is refused, and keeps the box open", async () => {
    const engine = await showHistory();
    startRename("is AAA halal?", "   ");
    fireEvent.submit(nameField().closest("form") as HTMLFormElement);
    const sentence = await screen.findByRole("alert");
    expect(sentence).toHaveTextContent("Give the chat a name.");
    expect(nameField()).toHaveAttribute("aria-invalid", "true");
    expect(engine.chats.find((chat) => chat.id === "chat-a")?.title).toBe("is AAA halal?");
  });
});

describe("deleting a chat", () => {
  it("asks first, in plain words, with Keep ready", async () => {
    await showHistory();
    fireEvent.click(deleteButton("is AAA halal?"));
    expect(screen.getByText("Delete this chat? This cannot be undone.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Keep" })).toHaveFocus();
    expect(callsStarting("DELETE", BASE)).toHaveLength(0);
  });

  it("keeps the chat on Keep, and on Escape", async () => {
    await showHistory();
    fireEvent.click(deleteButton("is AAA halal?"));
    fireEvent.click(screen.getByRole("button", { name: "Keep" }));
    fireEvent.click(deleteButton("is AAA halal?"));
    fireEvent.keyDown(screen.getByRole("button", { name: "Keep" }), { key: "Escape" });
    expect(screen.queryByText("Delete this chat? This cannot be undone.")).toBeNull();
    expect(listedTitles()).toContain("is AAA halal?");
    expect(callsStarting("DELETE", BASE)).toHaveLength(0);
    expect(screen.getByRole("region", { name: "Your chats" })).toBeInTheDocument();
    await waitFor(() => expect(deleteButton("is AAA halal?")).toHaveFocus());
  });

  it("deletes the chat once confirmed, takes it off the list, and puts focus in the search box", async () => {
    await showHistory();
    fireEvent.click(deleteButton("is AAA halal?"));
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(listedTitles()).toEqual(["show my watchlist", "how is INFY doing?"]));
    expect(callsStarting("DELETE", `${BASE}/chat-a`)).toHaveLength(1);
    expect(searchBox()).toHaveFocus();
  });

  it("deletes only the chat that was asked about", async () => {
    const engine = await showHistory();
    fireEvent.click(deleteButton("how is INFY doing?"));
    fireEvent.click(screen.getByRole("button", { name: "Delete" }));
    await waitFor(() => expect(listedTitles()).toHaveLength(2));
    expect(engine.chats.map((chat) => chat.id).sort()).toEqual(["chat-a", "chat-b"]);
  });
});

describe("clearing all history", () => {
  it("asks first and says what is lost, and Keep leaves everything", async () => {
    await showHistory();
    fireEvent.click(screen.getByRole("button", { name: "Clear all history" }));
    const sentence = "Clear all history? Every saved chat will be deleted. This cannot be undone.";
    expect(screen.getByText(sentence)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Keep" }));
    expect(listedTitles()).toHaveLength(3);
    expect(callsStarting("DELETE", BASE)).toHaveLength(0);
    expect(screen.getByRole("button", { name: "Clear all history" })).toBeInTheDocument();
  });

  it("deletes every chat once confirmed, and shows the empty list", async () => {
    const engine = await showHistory();
    fireEvent.click(screen.getByRole("button", { name: "Clear all history" }));
    fireEvent.click(screen.getByRole("button", { name: "Clear all" }));
    const empty = "No saved chats yet. Ask the Copilot something and it will appear here.";
    expect(await screen.findByText(empty)).toBeInTheDocument();
    expect(engine.chats).toEqual([]);
    expect(callsStarting("DELETE", BASE).map(([path]) => path)).toEqual([BASE]);
  });
});
