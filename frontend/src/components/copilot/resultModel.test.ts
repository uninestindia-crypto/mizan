import { describe, expect, it } from "vitest";
import { sampleResult } from "./fixtures";
import {
  buildResultView,
  consensusWords,
  FALLBACK_DISCLOSURE,
  HALAL_HEADING,
  headlineInWords,
  providerName,
  readingWords,
} from "./resultModel";

const models = [
  { id: "openai", label: "OpenAI", ready: true },
  { id: "anthropic", label: "Anthropic", ready: true },
  { id: "gemini", label: "Gemini", ready: true },
  { id: "mistral", label: "Mistral", ready: true },
];

describe("words for a reading", () => {
  it("describes how the evidence reads and never gives advice", () => {
    expect(readingWords("POSITIVE")).toBe("Looks positive");
    expect(readingWords("MIXED")).toBe("Mixed");
    expect(readingWords("NEGATIVE")).toBe("Looks negative");
    expect(readingWords("UNCLEAR")).toBe("Not clear");
  });

  it("copes with a reading it does not know, or none", () => {
    expect(readingWords("SOMETHING_NEW")).toBe("Not clear");
    expect(readingWords(null)).toBe("No reading");
  });

  it("uses no word that tells anyone to trade, and no score", () => {
    const all = ["POSITIVE", "MIXED", "NEGATIVE", "UNCLEAR", null].map(readingWords).join(" ");
    const consensus = ["AGREE", "MAJORITY", "SPLIT", "SINGLE", "NONE"].map(consensusWords).join(" ");
    expect(`${all} ${consensus}`).not.toMatch(/\b(buy|sell|add to|strong|score|rating|stars?|confidence|%)\b/i);
  });

  it("says in words how far the models agree", () => {
    expect(consensusWords("AGREE")).toBe("The models agree");
    expect(consensusWords("SPLIT")).toBe("The models are split");
    expect(consensusWords("SINGLE")).toBe("Only one model answered");
    expect(consensusWords("odd")).toBe("The models did not agree on a reading");
  });

  it("names a provider by its label, or makes its id readable", () => {
    expect(providerName("openai", models)).toBe("OpenAI");
    expect(providerName("open_router", models)).toBe("Open router");
  });

  it("knows the common companies even when the list of models is not at hand", () => {
    expect(providerName("openai", [])).toBe("OpenAI");
    expect(providerName("anthropic", [])).toBe("Anthropic (Claude)");
  });
});

describe("the disclosure and the notes", () => {
  it("carries the engine's disclosure in full", () => {
    const { disclosure } = buildResultView(sampleResult(), models);
    expect(disclosure).toBe("These are opinions from AI models. They are not independent evidence.");
  });

  it("is never without a disclosure, even when the engine sends none", () => {
    for (const disclosure of ["", "   ", undefined as unknown as string]) {
      expect(buildResultView(sampleResult({ disclosure }), models).disclosure).toBe(FALLBACK_DISCLOSURE);
    }
    expect(FALLBACK_DISCLOSURE).toMatch(/not independent evidence/);
  });

  it("keeps every note, in order", () => {
    const result = sampleResult();
    expect(buildResultView(result, models).notes).toEqual(result.notes);
  });
});

describe("each model's reading", () => {
  const view = buildResultView(sampleResult(), models);

  it("shows every model that was asked, including the one that failed", () => {
    expect(view.models).toHaveLength(4);
    expect(view.models.map((m) => m.name)).toEqual(["OpenAI", "Anthropic", "Gemini", "Mistral"]);
  });

  it("names the model and keeps its reasons, risks and what it said was missing", () => {
    const first = view.models[0];
    expect(first).toMatchObject({
      modelName: "gpt-x",
      answered: true,
      reading: "MIXED",
      reasons: ["Steady earnings history"],
      risks: ["Slowing demand abroad"],
      missing: ["No recent filing in the facts"],
    });
  });

  it("shows a failed model as unable to answer, with its own plain reason", () => {
    const failed = view.models[3];
    expect(failed).toMatchObject({ answered: false, reading: null, modelName: "mis-x" });
    expect(failed?.error).toBe("The key was not accepted. Check it in Settings, then Accounts and keys.");
  });

  it("gives a failed model without a reason a plain one instead of nothing", () => {
    const result = sampleResult();
    const bad = result.verdicts[3];
    if (bad) bad.blind.error = null;
    expect(buildResultView(result, models).models[3]?.error).toBe("No reason was given.");
  });

  it("says in words when a model changed its mind as the facts were reordered", () => {
    expect(view.models[0]?.stability).toMatch(/changed its mind when the same facts were shown in a different order/i);
    expect(view.models[1]?.stability).toMatch(/same reading/i);
    expect(view.models[3]?.stability).toBeNull();
  });

  it("says in words how the platform's own pick moved a model", () => {
    expect(view.models[0]?.anchoring).toMatch(/more favourably/);
    expect(view.models[0]?.anchoring).toMatch(/anchoring/);
    expect(view.models[0]?.informed).toContain("Looks positive");
    expect(view.models[1]?.anchoring).toBeNull();
    const less = sampleResult();
    const first = less.verdicts[0];
    if (first) first.shift = -1;
    expect(buildResultView(less, models).models[0]?.anchoring).toMatch(/less favourably/);
    if (first) first.shift = 0;
    expect(buildResultView(less, models).models[0]?.anchoring).toMatch(/did not change/);
  });

  it("reports a second pass that could not answer", () => {
    const result = sampleResult();
    const first = result.verdicts[0];
    if (first?.recheck) Object.assign(first.recheck, { ok: false, error: "Timed out." });
    expect(buildResultView(result, models).models[0]?.recheckProblem).toContain("could not answer");
  });
});

describe("the headline and counts", () => {
  it("keeps the engine's headline and shows the consensus as words", () => {
    const view = buildResultView(sampleResult(), models);
    expect(view.headline).toBe("2 of 3 models that answered read the evidence as mixed.");
    expect(view.consensus).toBe("Most of the models agree");
    expect(view.sharedReading).toBe("Mixed");
    expect(view.answeredLine).toBe("3 of 4 models answered.");
  });

  it("lists the counts of readings in a steady order", () => {
    const view = buildResultView(sampleResult({ counts: { MIXED: 2, NEGATIVE: 1, POSITIVE: 1 } }), models);
    expect(view.counts.map((c) => [c.reading, c.count])).toEqual([
      ["POSITIVE", 1],
      ["MIXED", 2],
      ["NEGATIVE", 1],
    ]);
  });

  it("has no shared reading when the models are split", () => {
    expect(buildResultView(sampleResult({ consensus: "SPLIT", reading: null }), models).sharedReading).toBeNull();
  });

  it("summarises the tone of the news the models read", () => {
    const { newsTones } = buildResultView(sampleResult(), models);
    expect(newsTones).toBe("How the models read the news headlines: neutral: 2, positive: 1.");
    expect(buildResultView(sampleResult({ news_tones: { None: 3 } }), models).newsTones).toBeNull();
  });
});

describe("the headline's reading word", () => {
  it("says the reading the way the badges do, not in raw capitals", () => {
    expect(headlineInWords("2 of 3 models read the facts as MIXED.")).toBe("2 of 3 models read the facts as mixed.");
    expect(headlineInWords("All 3 models read the facts as POSITIVE.")).toBe(
      "All 3 models read the facts as looking positive.",
    );
    expect(headlineInWords("2 of 3 models read the facts as NEGATIVE.")).toBe(
      "2 of 3 models read the facts as looking negative.",
    );
    expect(headlineInWords("1 model read the facts as UNCLEAR.")).toBe("1 model read the facts as not clear.");
  });

  it("changes only whole capitalised reading words and leaves the rest of the sentence alone", () => {
    const text = "2 of 5 models answered, and both read the facts as POSITIVE.";
    expect(headlineInWords(text)).toBe("2 of 5 models answered, and both read the facts as looking positive.");
    expect(headlineInWords("The facts are mixed and positive in places.")).toBe(
      "The facts are mixed and positive in places.",
    );
    expect(headlineInWords("The word NEGATIVELY is not a reading.")).toBe("The word NEGATIVELY is not a reading.");
    expect(headlineInWords("")).toBe("");
  });

  it("is applied to the headline of a result, and to nothing else", () => {
    const view = buildResultView(sampleResult({ headline: "2 of 3 models read the facts as MIXED." }), models);
    expect(view.headline).toBe("2 of 3 models read the facts as mixed.");
    expect(view.notes).toEqual(sampleResult().notes);
  });
});

describe("whose reading it is", () => {
  it("calls it the shared reading when several models answered", () => {
    expect(buildResultView(sampleResult(), models).readingLabel).toBe("Shared reading");
  });

  it("calls it its own reading when only one model answered", () => {
    const view = buildResultView(sampleResult({ consensus: "SINGLE", answered: 1, asked: 3 }), models);
    expect(view.readingLabel).toBe("Its reading");
    expect(view.sharedReading).toBe("Mixed");
  });
});

describe("a stock the engine could not find", () => {
  const none = sampleResult({
    headline: "QuantOS has no price data for ZZZ, so no AI model was asked.",
    consensus: "NONE",
    reading: null,
    asked: 0,
    answered: 0,
    counts: {},
    news_tones: {},
    verdicts: [],
    dissent: [],
    notes: [],
    halal: null,
    facts: null,
  });

  it("is marked empty so the screen shows the headline and the disclosure only", () => {
    const view = buildResultView(none, models);
    expect(view.empty).toBe(true);
    expect(view.headline).toBe("QuantOS has no price data for ZZZ, so no AI model was asked.");
    expect(view.disclosure).toBe("These are opinions from AI models. They are not independent evidence.");
  });

  it("is not empty when any model was asked", () => {
    expect(buildResultView(sampleResult(), models).empty).toBe(false);
  });
});

describe("dissenters", () => {
  it("lists who read it differently, with their reasons and risks", () => {
    const view = buildResultView(sampleResult(), models);
    expect(view.dissent).toEqual([
      expect.objectContaining({
        name: "Anthropic",
        modelName: "claude-x",
        reading: "POSITIVE",
        reasons: ["Strong order book"],
        risks: ["Currency swings"],
      }),
    ]);
    expect(view.noDissent).toBe(false);
  });

  it("says plainly when every model agreed", () => {
    const view = buildResultView(sampleResult({ consensus: "AGREE", dissent: [] }), models);
    expect(view.noDissent).toBe(true);
  });
});

describe("the screener's halal result", () => {
  it("is labelled as the screener's, not the models'", () => {
    const view = buildResultView(sampleResult(), models);
    expect(view.halal?.heading).toBe(HALAL_HEADING);
    expect(HALAL_HEADING).toBe("Halal screening (from the platform's screener, not from the AI models)");
  });

  it("shows both standards, the ratios and the data status", () => {
    const halal = buildResultView(sampleResult(), models).halal;
    expect(halal?.dataStatus).toBe("Unverified sample data");
    expect(halal?.dataNotice).toBe("Illustrative sample figures.");
    expect(halal?.standards.map((s) => [s.name, s.status])).toEqual([
      ["AAOIFI", "Passes"],
      ["TASIS", "Questionable"],
    ]);
    expect(halal?.standards[0]?.ratios).toEqual([{ name: "Debt ratio", line: "12.35%, limit 30%" }]);
    expect(halal?.standards[1]?.ratios[0]?.line).toBe("29%, limit 30%. Close to the limit");
    expect(halal?.disclaimer).toBe("A screening aid, not a religious ruling.");
  });

  it("explains a stock the screener does not cover instead of leaving a blank", () => {
    const view = buildResultView(
      sampleResult({
        halal: {
          covered: false,
          data_status: "UNVERIFIED_SAMPLE",
          message: "QuantOS cannot screen TCS.",
          standards: [],
          disclaimer: "x",
        },
      }),
      models,
    );
    expect(view.halal).toMatchObject({ covered: false, message: "QuantOS cannot screen TCS.", standards: [] });
  });

  it("has no halal block when the engine sent none", () => {
    expect(buildResultView(sampleResult({ halal: null }), models).halal).toBeNull();
  });
});

describe("what the models were shown", () => {
  it("lists every section, which came from outside, and what was unavailable", () => {
    const { facts } = buildResultView(sampleResult(), models);
    expect(facts.sections).toEqual([
      { title: "Price history facts", summary: "Up 12% in a year.", fromOutside: false },
      { title: "Recent headlines", summary: "Three headlines.", fromOutside: true },
    ]);
    expect(facts.unavailable).toEqual(["Live price"]);
  });
});
