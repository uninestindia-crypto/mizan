import { describe, expect, it } from "vitest";
import { ApiError, errorMessage } from "./api";
import { moneyProblems, plainValidation } from "./rules";

describe("moneyProblems", () => {
  it("accepts the defaults", () => {
    expect(moneyProblems("1000000", "1", "2")).toEqual({});
  });

  it("reports every problem at once, with the limit in the words", () => {
    const problems = moneyProblems("5", "500", "0");
    expect(problems.capital).toContain("at least ₹1,000");
    expect(problems.risk).toContain("10% or less");
    expect(problems.daily).toBe("Enter more than 0%.");
  });

  it("treats an empty or non-numeric box as a missing number, not a crash", () => {
    expect(moneyProblems("", "1", "2").capital).toBe("Enter a number.");
    expect(moneyProblems("abc", "", "").risk).toBe("Enter more than 0%.");
  });
});

describe("plainValidation", () => {
  it("replaces developer wording with a sentence", () => {
    expect(plainValidation("money.capital", "Input should be greater than or equal to 1000")).toBe("Money you trade with must be at least 1,000.");
    expect(plainValidation("money.risk_per_trade_pct", "Input should be less than or equal to 10")).toBe("Risk per trade can be at most 10.");
    expect(plainValidation("broker.delivery_per_order", "Input should be a valid decimal")).toBe("Delivery brokerage needs to be a number.");
    expect(plainValidation("capital", "Input should be greater than or equal to 10000")).toBe("Starting capital must be at least 10,000.");
  });

  it("never leaks a dotted field name for an unknown field", () => {
    expect(plainValidation("some.new_field", "Input should be a valid number")).toBe("new field needs to be a number.");
  });
});

describe("errorMessage", () => {
  it("humanises the engine's generic validation error", () => {
    const error = new ApiError("VALIDATION_ERROR", "Request validation failed against schema.", 422, {
      errors: [{ location: ["body", "capital"], message: "Input should be greater than or equal to 10000" }],
    });
    expect(errorMessage(error)).toBe("Starting capital must be at least 10,000.");
  });

  it("humanises a settings error that carries the field in the message", () => {
    const error = new ApiError("INVALID_SETTINGS", "money.capital: Input should be a valid decimal", 422);
    expect(errorMessage(error)).toBe("Money you trade with needs to be a number.");
  });

  it("leaves other errors alone", () => {
    expect(errorMessage(new ApiError("LAB_REFUSED", "Fast average must be shorter.", 400))).toBe("Fast average must be shorter.");
  });
});
