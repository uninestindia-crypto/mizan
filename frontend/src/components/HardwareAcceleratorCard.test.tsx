import { cleanup, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../lib/api";
import { renderApp, routeApi } from "./agents/testHarness";
import { HardwareAcceleratorCard } from "./HardwareAcceleratorCard";

vi.mock("../lib/api", async (importOriginal) => {
  const real = await importOriginal<typeof import("../lib/api")>();
  return { ...real, api: vi.fn() };
});

const DEVICE = { available: true, name: "Processor", category: "CPU", provider: "CPU", details: "8 cores", status: "Ready" };

function topology(embeddingStatus: string) {
  return {
    active_target: "auto",
    effective_target: "cpu",
    platform: "Windows",
    architecture: "ARM64",
    devices: { npu: { ...DEVICE, category: "NPU" }, gpu: { ...DEVICE, category: "GPU" }, cpu: DEVICE },
    local_models: [
      {
        id: "cand_ridge_v1",
        name: "Governed Single-Instrument Ridge",
        category: "L2-Regularized Linear Alpha",
        size: "~5 MB",
        recommended_hardware: "CPU SIMD",
        status: "READY",
        description: "A ridge model.",
      },
      {
        id: "embeddinggemma-2",
        name: "EmbeddingGemma 2 (text, about 270M)",
        category: "Semantic Embeddings & Search",
        size: "~330 MB download",
        recommended_hardware: "NPU / CPU",
        status: embeddingStatus,
        description: "Google's embedding model.",
      },
    ],
  };
}

describe("HardwareAcceleratorCard model list", () => {
  beforeEach(() => {
    vi.mocked(api).mockReset();
  });
  afterEach(cleanup);

  it("does not say a model is running when it is not installed", async () => {
    routeApi({ "GET /api/v2/system/hardware": topology("NOT INSTALLED") });
    renderApp(<HardwareAcceleratorCard />);
    expect(await screen.findByText("EmbeddingGemma 2 (text, about 270M)")).toBeInTheDocument();
    expect(screen.getByText("NOT INSTALLED")).toBeInTheDocument();
    expect(screen.getAllByText("Not running on this computer")).toHaveLength(1);
    // the ridge model, which is ready, still shows it runs
    expect(screen.getAllByText("In-Process")).toHaveLength(1);
  });

  it("says a ready model runs in this app", async () => {
    routeApi({ "GET /api/v2/system/hardware": topology("READY") });
    renderApp(<HardwareAcceleratorCard />);
    expect(await screen.findByText("EmbeddingGemma 2 (text, about 270M)")).toBeInTheDocument();
    expect(screen.getAllByText("In-Process")).toHaveLength(2);
    expect(screen.queryByText("Not running on this computer")).toBeNull();
  });
});
