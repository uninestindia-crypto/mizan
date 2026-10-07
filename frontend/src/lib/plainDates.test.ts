import { describe, expect, it } from "vitest";
import { friendlyDates } from "./plainDates";

describe("friendlyDates", () => {
  it("reads a stored date the way a person does", () => {
    expect(friendlyDates("Data to 2021-03-23.")).toBe("Data to 23 Mar 2021.");
    expect(friendlyDates("From 2020-01-02 to 2021-12-31")).toBe("From 2 Jan 2020 to 31 Dec 2021");
  });

  it("leaves what is not a real date, a timestamp, a longer number or a web address exactly as written", () => {
    for (const text of [
      "2021-02-31",
      "2021-13-01",
      "2021-03-23T10:15:00",
      "12021-03-23",
      "2021-03-234",
      "https://example.com/2021-03-23",
      "a-2021-03-23",
    ]) {
      expect(friendlyDates(text)).toBe(text);
    }
  });

  it("changes nothing in a sentence with no date", () => {
    expect(friendlyDates("TCS moved 12% in a year.")).toBe("TCS moved 12% in a year.");
  });
});
