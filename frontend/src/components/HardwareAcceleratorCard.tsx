import {
  CheckCircle2,
  Cpu,
  Sparkles,
  Zap,
} from "lucide-react";
import { Badge, Callout, Card, CardHeader, cx, Segmented, Skeleton } from "./ui";
import { useHardwareInfo, useSetHardwareAccelerator } from "../lib/queries";
import type { AcceleratorTarget } from "../lib/types";

export function HardwareAcceleratorCard() {
  const hardware = useHardwareInfo();
  const setAccelerator = useSetHardwareAccelerator();

  if (hardware.isPending) {
    return (
      <Card>
        <CardHeader
          title="Hardware Acceleration & Local AI Engine"
          subtitle="Detecting neural processing unit (NPU), graphics card (GPU), and processor..."
        />
        <div className="space-y-4 p-5">
          <Skeleton className="h-10 w-full" />
          <div className="grid gap-3 sm:grid-cols-3">
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
            <Skeleton className="h-24 w-full" />
          </div>
        </div>
      </Card>
    );
  }

  if (hardware.isError || !hardware.data) {
    return null;
  }

  const data = hardware.data;
  const currentTarget = data.active_target;
  const effectiveTarget = data.effective_target.toUpperCase();

  const npu = data.devices.npu;
  const gpu = data.devices.gpu;
  const cpu = data.devices.cpu;

  const targetOptions: { value: AcceleratorTarget; label: string }[] = [
    { value: "auto", label: "Auto (Fastest)" },
    ...(npu.available ? [{ value: "npu" as AcceleratorTarget, label: "NPU (Neural)" }] : []),
    { value: "gpu" as AcceleratorTarget, label: "GPU (Graphics)" },
    { value: "cpu" as AcceleratorTarget, label: "CPU (Core SIMD)" },
  ];

  return (
    <Card className="border-line/70 shadow-sm">
      <CardHeader
        title="Hardware Acceleration & Local AI Engine"
        subtitle={`Active Compute: ${effectiveTarget} · ${data.platform} (${data.architecture})`}
        action={
          <Badge tone={data.devices[data.effective_target]?.available ? "up" : "neutral"} className="flex items-center gap-1">
            <Zap className="size-3" aria-hidden />
            {effectiveTarget} Accelerated
          </Badge>
        }
      />

      <div className="space-y-6 p-5">
        {/* Accelerator Switcher */}
        <div>
          <div className="mb-2 flex items-center justify-between">
            <label className="text-xs font-semibold uppercase tracking-wider text-ink-3">
              Compute Target
            </label>
            <span className="text-xs text-ink-3">
              {currentTarget === "auto"
                ? `System directed to ${effectiveTarget} engine`
                : `Explicitly locked to ${currentTarget.toUpperCase()}`}
            </span>
          </div>

          <Segmented
            label="Hardware accelerator target"
            value={currentTarget}
            onChange={(val) => setAccelerator.mutate(val as AcceleratorTarget)}
            options={targetOptions}
          />
        </div>

        {/* Device Topology Cards */}
        <div className="grid gap-3 sm:grid-cols-3">
          {/* NPU */}
          <div
            className={cx(
              "relative rounded-xl border p-4 transition-all",
              data.effective_target === "npu"
                ? "border-brand/40 bg-brand/5 shadow-xs"
                : "border-line/60 bg-surface-2/40 hover:border-line",
            )}
          >
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-ink-2">
                <Sparkles className="size-3.5 text-brand" aria-hidden />
                NPU Core
              </span>
              <Badge tone={npu.available ? "up" : "neutral"}>
                {npu.status}
              </Badge>
            </div>
            <div className="mt-2.5 truncate font-medium text-ink text-[13px]" title={npu.name}>
              {npu.name}
            </div>
            <div className="mt-1 text-xs text-ink-3">
              {npu.provider} · Ultra-low power
            </div>
            <p className="mt-2 line-clamp-2 text-[11.5px] leading-relaxed text-ink-3">
              {npu.details}
            </p>
          </div>

          {/* GPU */}
          <div
            className={cx(
              "relative rounded-xl border p-4 transition-all",
              data.effective_target === "gpu"
                ? "border-brand/40 bg-brand/5 shadow-xs"
                : "border-line/60 bg-surface-2/40 hover:border-line",
            )}
          >
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-ink-2">
                <Zap className="size-3.5 text-amber-500" aria-hidden />
                GPU Engine
              </span>
              <Badge tone={gpu.available ? "up" : "neutral"}>
                {gpu.status}
              </Badge>
            </div>
            <div className="mt-2.5 truncate font-medium text-ink text-[13px]" title={gpu.name}>
              {gpu.name}
            </div>
            <div className="mt-1 text-xs text-ink-3">
              {gpu.provider} · High Throughput
            </div>
            <p className="mt-2 line-clamp-2 text-[11.5px] leading-relaxed text-ink-3">
              {gpu.details}
            </p>
          </div>

          {/* CPU */}
          <div
            className={cx(
              "relative rounded-xl border p-4 transition-all",
              data.effective_target === "cpu"
                ? "border-brand/40 bg-brand/5 shadow-xs"
                : "border-line/60 bg-surface-2/40 hover:border-line",
            )}
          >
            <div className="flex items-center justify-between">
              <span className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-ink-2">
                <Cpu className="size-3.5 text-sky-500" aria-hidden />
                CPU Cores
              </span>
              <Badge tone={cpu.available ? "up" : "neutral"}>
                {cpu.status}
              </Badge>
            </div>
            <div className="mt-2.5 truncate font-medium text-ink text-[13px]" title={cpu.name}>
              {cpu.name}
            </div>
            <div className="mt-1 text-xs text-ink-3">
              {cpu.provider} · Universal
            </div>
            <p className="mt-2 line-clamp-2 text-[11.5px] leading-relaxed text-ink-3">
              {cpu.details}
            </p>
          </div>
        </div>

        {/* Integrated Local Models Gallery */}
        <div className="border-t border-line/60 pt-5">
          <div className="mb-3 flex items-center justify-between">
            <div>
              <h4 className="text-sm font-semibold text-ink">Integrated Local Models</h4>
              <p className="text-xs text-ink-3">
                Zero-terminal local inference running natively on your selected accelerator.
              </p>
            </div>
            <Badge tone="brand" className="hidden sm:inline-flex">
              Self-Contained Runner
            </Badge>
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            {data.local_models.map((model) => (
              <div
                key={model.id}
                className="flex flex-col justify-between rounded-xl border border-line/60 bg-surface p-3.5 shadow-2xs"
              >
                <div>
                  <div className="flex items-center justify-between gap-1">
                    <span className="truncate font-semibold text-ink text-[12.5px]">
                      {model.name}
                    </span>
                    <Badge tone={model.status.startsWith("ACTIVE") ? "up" : "neutral"}>
                      {model.status}
                    </Badge>
                  </div>
                  <div className="mt-1 text-[11px] font-medium text-ink-3">
                    {model.category} · {model.size}
                  </div>
                  <p className="mt-2 text-[11.5px] leading-relaxed text-ink-2">
                    {model.description}
                  </p>
                </div>
                <div className="mt-3 flex items-center justify-between border-t border-line/40 pt-2.5 text-[11px] text-ink-3">
                  <span>Target: {model.recommended_hardware}</span>
                  {model.status.startsWith("ACTIVE") || model.status === "READY" ? (
                    <span className="flex items-center gap-1 font-medium text-up">
                      <CheckCircle2 className="size-3" aria-hidden />
                      In-Process
                    </span>
                  ) : (
                    <span className="font-medium text-ink-3">Not running on this computer</span>
                  )}
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Zero Terminal Callout */}
        <Callout tone="info" className="text-[12px] leading-relaxed">
          <span className="font-semibold">Zero-Terminal Guarantee: </span>
          All local models are fully self-contained within QuantOS. You will never need to install
          external Python packages, run terminal commands, or configure GPU drivers.
        </Callout>
      </div>
    </Card>
  );
}
