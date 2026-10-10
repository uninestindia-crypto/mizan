# Third-party notices

QuantOS contains or was informed by the open-source projects below. Their notices are kept here so that copies of QuantOS
carry them.

## Qlib (Microsoft) — MIT licence

Source: https://github.com/microsoft/qlib

Code derived from Qlib:

- `src/quant_system/research/qlib/riskmodel.py`, from `qlib/model/riskmodel/base.py` and `qlib/model/riskmodel/shrink.py`
  (corrected and changed; the differences are listed at the top of that file).
- `src/quant_system/research/qlib/alpha158.py` (the Alpha158 factor formulas, from `qlib/contrib/data/handler.py`).

```
MIT License

Copyright (c) Microsoft Corporation.

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE
```

## PyBroker — Apache 2.0 with the Commons Clause

Source: https://github.com/edtechre/pybroker. Copyright (C) 2023 Edward West.

`src/pybroker/` is a vendored copy of the PyBroker engine. The per-file copyright and licence headers were removed from that copy
on 2026-10-10 (commit `f75e8570a`), so they are not repeated in the files; this notice is where the source and licence are
recorded. PyBroker is licensed under
Apache 2.0 **with the Commons Clause License Condition v1.0**, which says the licence does not grant the right to "Sell" the
software, where "Sell" means providing to third parties, for a fee or other consideration (including hosting or
consulting/support services), a product or service whose value derives, entirely or substantially, from the functionality of
the software.

**Open question for the founder:** if QuantOS is ever offered for a fee, the shipped PyBroker copy may fall under that
condition. This needs a decision (a commercial licence from the author, or replacing the engine) before any paid release.
Nothing new is copied from PyBroker; ideas learned from it are written fresh.
