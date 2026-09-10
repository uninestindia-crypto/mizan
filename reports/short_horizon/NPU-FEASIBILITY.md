# Snapdragon Hexagon NPU inference feasibility — bounded test

**Verdict: `NPU_UNREACHABLE`. CPU execution is retained. The blocker is structural, not a tuning
problem, and it is one the founder can remove — but not one an agent should remove unilaterally.**

Probe: `scripts/npu_feasibility_probe.py`. Machine-readable evidence:
`reports/short_horizon/npu-feasibility-probe.json`.

Reproduce with:

```bash
.venv/Scripts/python.exe scripts/npu_feasibility_probe.py
```

## What was measured

| Check | Result |
|---|---|
| NPU hardware present | **Yes.** `Snapdragon(R) X - X126100 - Qualcomm(R) Hexagon(TM) NPU`, Windows PnP status `OK` |
| Processor | `ARMv8 (64-bit) Family 8 Model 1 Revision 201, Qualcomm Technologies Inc` |
| Python interpreter architecture | **`AMD64` (x86-64)**, read from the interpreter's own PE header (`0x8664`) |
| `sysconfig.get_platform()` | `win-amd64` |
| Installed `torch` wheel tag | `cp313-cp313-win_amd64` |
| QNN backend libraries found | **0 of 4** (`QnnHtp.dll`, `QnnHtpV73Stub.dll`, `QnnSystem.dll`, `QnnCpu.dll`) |
| `onnxruntime` in the QuantOS environment | not installed |
| CPU baseline | **5.94 ms** per 512³ float32 matmul, **45.2 GFLOP/s** (numpy 2.5.2, 20 repeats) |

## The finding that decides it

**The entire QuantOS Python environment is an x86-64 build running under Windows-on-ARM emulation.**

This was not obvious and is worth stating carefully, because the most natural way to check it gives
the wrong answer:

- `platform.machine()` returns `ARM64` in some shells and `AMD64` in others, because it reports the
  *processor* and is sensitive to how `PROCESSOR_ARCHITECTURE` was propagated. It is not a statement
  about the process.
- The **PE header** of `python.exe` is a statement about the process, and it reads `0x8664` = AMD64
  for both `.venv\Scripts\python.exe` and the base interpreter at
  `C:\Users\teenl\AppData\Local\Programs\Python\Python313\python.exe`.
- `sysconfig.get_platform()` agrees: `win-amd64`. So does every wheel installed into it.

An emulated x86-64 process **cannot load ARM64 DLLs**. The Qualcomm QNN HTP backend — the only route
to the Hexagon NPU — ships as ARM64 only. So the NPU is unreachable from this environment regardless
of what is installed into it.

### The trap this avoids

`uv pip install onnxruntime-qnn` **resolves successfully** here — it offers `onnxruntime-qnn==2.5.0`.
Installing it would have appeared to work. At runtime it would have provided no
`QNNExecutionProvider`, ONNX Runtime would have fallen back to CPU silently, and the resulting
timings would have looked like "the NPU gives negligible benefit."

That conclusion would have been false, and worse, it would have been *reported* as a measurement.
The probe checks interpreter architecture **before** it reports any timing precisely so this cannot
happen.

## What would be required to actually test the NPU

All four, in order. Each is a real cost, and the first is a machine-level change.

1. **A native ARM64 CPython.** None is installed — `C:\Users\teenl\AppData\Local\Programs\Python`
   contains only the x86-64 `Python313`. `uv` cannot supply one here: `uv` is itself
   `x86_64-pc-windows-msvc`, so `uv python list --all-platforms` enumerates no `aarch64` build. This
   needs a download from python.org and an install, which is a founder decision about their machine,
   not something a bounded feasibility test should do on its own.
2. **A rebuilt QuantOS environment against that interpreter.** Every wheel currently installed is
   `win_amd64`. `numpy`, `scipy` and `torch` would all need their `win_arm64` equivalents, and any
   that lack one become a blocker in turn.
3. **The Qualcomm QNN SDK / AI Engine Direct runtime**, providing the HTP backend libraries.
4. **Model conversion to ONNX with an NPU-supported operator set**, then quantisation — the HTP
   backend is int8/int16-oriented, and a float32 model that converts cleanly may still fall back to
   CPU per-operator.

## What this changes about the study — nothing

Per the brief: *"If NPU conversion fails or provides negligible benefit, retain CPU execution and
document the result."*

CPU execution is retained. **Accounting and risk controls are untouched**, which was a constraint
rather than an outcome: nothing in this probe reads or writes a portfolio, a model, a cost rule or a
governor limit. It measures the environment and writes one JSON file.

The CPU baseline above is the reproducible floor the short-horizon study is measured against, and it
is recorded now so that any future NPU number has something honest to be compared with — measured on
the same machine, under the same emulation, with a stated method.

## Honest limits of this probe

- **The CPU baseline is a dense matmul, not a model forward pass.** It needs no checkpoint and no
  network, so it reproduces anywhere, but it is a floor for comparison rather than a proxy for
  end-to-end inference latency. TimesFM forward-pass timings are measured separately in the isolated
  environment and reported with the short-horizon results.
- **45.2 GFLOP/s is an emulated number.** A native ARM64 build would likely be faster on the same
  silicon. How much faster is not measured here and must not be guessed — it is one of the things a
  native environment would let someone find out.
- **"NPU unreachable" is a statement about this environment, not about the hardware.** The NPU is
  present and healthy. Nothing here says it would not help; it says the current environment cannot
  ask it.
