import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { useState } from "react";
import { afterEach, describe, expect, it } from "vitest";
import { Button, Dialog, Field, Input, Select } from "./ui";

afterEach(cleanup);

/** A button that opens a window by state, the way every window in the app is opened (there is no Radix trigger). */
function Opener({ fallback }: { fallback?: () => HTMLElement | null }) {
  const [open, setOpen] = useState(false);
  const [gone, setGone] = useState(false);
  const remove = () => {
    setGone(true);
    setOpen(false);
  };
  const footer = (
    <>
      <Button onClick={() => setOpen(false)}>Keep it</Button>
      <Button onClick={remove}>Remove</Button>
    </>
  );
  return (
    <div>
      {!gone && <Button onClick={() => setOpen(true)}>Delete</Button>}
      <Dialog open={open} onOpenChange={setOpen} title="Delete it?" fallbackFocus={fallback} footer={footer}>
        Sure?
      </Dialog>
      <h2 tabIndex={-1}>Fallback place</h2>
    </div>
  );
}

function openFrom(button: HTMLElement) {
  button.focus();
  fireEvent.click(button);
  return screen.findByRole("dialog");
}

describe("a window opened by state", () => {
  it("gives focus back to the control it was opened from when Escape closes it", async () => {
    render(<Opener />);
    const opener = screen.getByRole("button", { name: "Delete" });
    const dialog = await openFrom(opener);
    expect(dialog.contains(document.activeElement)).toBe(true);
    fireEvent.keyDown(dialog, { key: "Escape" });
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(opener).toHaveFocus());
  });

  it("gives focus back when one of its own buttons closes it", async () => {
    render(<Opener />);
    const opener = screen.getByRole("button", { name: "Delete" });
    await openFrom(opener);
    fireEvent.click(screen.getByRole("button", { name: "Keep it" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(opener).toHaveFocus());
  });

  it("goes to the fallback when the control is gone, and leaves focus alone when there is none", async () => {
    const view = render(<Opener fallback={() => screen.getByText("Fallback place")} />);
    await openFrom(screen.getByRole("button", { name: "Delete" }));
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(screen.getByText("Fallback place")).toHaveFocus());
    view.unmount();

    render(<Opener />);
    await openFrom(screen.getByRole("button", { name: "Delete" }));
    fireEvent.click(screen.getByRole("button", { name: "Remove" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).toBeNull());
    await waitFor(() => expect(document.body).toHaveFocus());
  });
});

describe("a field and the line under it", () => {
  it("ties the problem to its control, and says the control is invalid", () => {
    render(
      <Field label="Name" htmlFor="n" error="Give your agent a name." hint="Up to 60 letters.">
        <Input id="n" />
      </Field>,
    );
    const box = screen.getByLabelText("Name");
    const line = screen.getByText("Give your agent a name.");
    expect(box).toHaveAttribute("aria-describedby", line.id);
    expect(line.id).not.toBe("");
    expect(box).toHaveAttribute("aria-invalid", "true");
    expect(screen.queryByText("Up to 60 letters.")).toBeNull();
    expect(box).toHaveAccessibleDescription("Give your agent a name.");
  });

  it("ties the hint to the control when there is no problem, and does not call it invalid", () => {
    render(
      <Field label="Stock" htmlFor="s" hint="Type the NSE symbol.">
        <Input id="s" />
      </Field>,
    );
    const box = screen.getByLabelText("Stock");
    expect(box).toHaveAccessibleDescription("Type the NSE symbol.");
    expect(box).not.toHaveAttribute("aria-invalid");
  });

  it("keeps what the control already says about itself, and an explicit invalid", () => {
    render(
      <>
        <p id="extra">Extra help.</p>
        <Field label="Size" htmlFor="z" error="Too big.">
          <Input id="z" aria-describedby="extra" aria-invalid="false" />
        </Field>
      </>,
    );
    const box = screen.getByLabelText("Size");
    expect(box).toHaveAccessibleDescription("Extra help. Too big.");
    expect(box).toHaveAttribute("aria-invalid", "false");
  });

  it("works for a Select, and for an input with a prefix", () => {
    render(
      <>
        <Field label="Universe" htmlFor="u" error="Pick one.">
          <Select id="u">
            <option>NIFTY</option>
          </Select>
        </Field>
        <Field label="Price" htmlFor="p" error="Not a number.">
          <Input id="p" prefix="₹" />
        </Field>
      </>,
    );
    expect(screen.getByLabelText("Universe")).toHaveAccessibleDescription("Pick one.");
    expect(screen.getByLabelText("Price")).toHaveAccessibleDescription("Not a number.");
  });

  it("adds nothing when there is no line under the control, or the control is not the labelled one", () => {
    render(
      <>
        <Field label="Plain" htmlFor="a">
          <Input id="a" />
        </Field>
        <Field label="Other" htmlFor="b" error="Bad.">
          <Input id="not-b" aria-label="Unlabelled" />
        </Field>
      </>,
    );
    expect(screen.getByLabelText("Plain")).not.toHaveAttribute("aria-describedby");
    expect(screen.getByLabelText("Unlabelled")).not.toHaveAttribute("aria-describedby");
  });
});

describe("the danger button", () => {
  it("uses dark writing in the dark theme, where its red is light and white would be too faint", () => {
    render(<Button variant="danger">Delete</Button>);
    expect(screen.getByRole("button", { name: "Delete" }).className).toContain("dark:text-on-brand");
  });
});
