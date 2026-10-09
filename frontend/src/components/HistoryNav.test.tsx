import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { Link, MemoryRouter, Route, Routes, useLocation } from "react-router";
import { afterEach, describe, expect, it } from "vitest";
import { HistoryNav } from "./HistoryNav";

import { TooltipProvider } from "./ui";

afterEach(cleanup);

function TestApp({ initialEntries = ["/"] }: { initialEntries?: string[] }) {
  return (
    <TooltipProvider>
      <MemoryRouter initialEntries={initialEntries}>
        <div>
          <HistoryNav />
          <nav>
            <Link to="/">Home</Link>
            <Link to="/markets">Markets</Link>
            <Link to="/stock/TCS">Stock</Link>
          </nav>
          <CurrentPath />
          <Routes>
            <Route path="/" element={<div>Home Page</div>} />
            <Route path="/markets" element={<div>Markets Page</div>} />
            <Route path="/stock/:symbol" element={<div>Stock Page</div>} />
          </Routes>
        </div>
      </MemoryRouter>
    </TooltipProvider>
  );
}

function CurrentPath() {
  const location = useLocation();
  return <div data-testid="current-path">{location.pathname}</div>;
}

describe("HistoryNav (Forward and Back buttons)", () => {
  it("renders disabled back and forward buttons on initial entry", () => {
    render(<TestApp />);
    const backBtn = screen.getByRole("button", { name: "Go back" });
    const forwardBtn = screen.getByRole("button", { name: "Go forward" });

    expect(backBtn).toBeInTheDocument();
    expect(forwardBtn).toBeInTheDocument();
    expect(backBtn).toBeDisabled();
    expect(forwardBtn).toBeDisabled();
  });

  it("enables back button when navigating to a new route", () => {
    render(<TestApp />);
    const backBtn = screen.getByRole("button", { name: "Go back" });
    const forwardBtn = screen.getByRole("button", { name: "Go forward" });

    expect(screen.getByTestId("current-path")).toHaveTextContent("/");
    expect(backBtn).toBeDisabled();

    // Navigate to Markets
    fireEvent.click(screen.getByText("Markets"));
    expect(screen.getByTestId("current-path")).toHaveTextContent("/markets");

    expect(backBtn).toBeEnabled();
    expect(forwardBtn).toBeDisabled();
  });

  it("navigates back when clicking back button and enables forward button", () => {
    render(<TestApp />);
    const backBtn = screen.getByRole("button", { name: "Go back" });
    const forwardBtn = screen.getByRole("button", { name: "Go forward" });

    // Navigate to Markets, then Stock
    fireEvent.click(screen.getByText("Markets"));
    expect(screen.getByTestId("current-path")).toHaveTextContent("/markets");

    fireEvent.click(screen.getByText("Stock"));
    expect(screen.getByTestId("current-path")).toHaveTextContent("/stock/TCS");

    // Click Back -> goes to Markets
    fireEvent.click(backBtn);
    expect(screen.getByTestId("current-path")).toHaveTextContent("/markets");
    expect(backBtn).toBeEnabled();
    expect(forwardBtn).toBeEnabled();

    // Click Forward -> goes to Stock
    fireEvent.click(forwardBtn);
    expect(screen.getByTestId("current-path")).toHaveTextContent("/stock/TCS");
    expect(backBtn).toBeEnabled();
    expect(forwardBtn).toBeDisabled();
  });

  it("supports keyboard navigation with Alt+ArrowLeft and Alt+ArrowRight", () => {
    render(<TestApp />);

    fireEvent.click(screen.getByText("Markets"));
    expect(screen.getByTestId("current-path")).toHaveTextContent("/markets");

    // Press Alt + Left
    fireEvent.keyDown(window, { key: "ArrowLeft", altKey: true });
    expect(screen.getByTestId("current-path")).toHaveTextContent("/");

    // Press Alt + Right
    fireEvent.keyDown(window, { key: "ArrowRight", altKey: true });
    expect(screen.getByTestId("current-path")).toHaveTextContent("/markets");
  });

  it("supports hardware mouse navigation with buttons 3 (back) and 4 (forward)", () => {
    render(<TestApp />);

    fireEvent.click(screen.getByText("Markets"));
    expect(screen.getByTestId("current-path")).toHaveTextContent("/markets");

    // Mouse back button (button: 3)
    fireEvent.mouseUp(window, { button: 3 });
    expect(screen.getByTestId("current-path")).toHaveTextContent("/");

    // Mouse forward button (button: 4)
    fireEvent.mouseUp(window, { button: 4 });
    expect(screen.getByTestId("current-path")).toHaveTextContent("/markets");
  });
});
