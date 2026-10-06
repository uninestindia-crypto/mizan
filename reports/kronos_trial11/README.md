# Running Kronos trial 11 (the biggest model, five paths)

This is the largest released Kronos model, `Kronos-base`, run the way its authors average predictions: five sampled
paths per name. It is **one trial**, declared in `TRIAL-LEDGER.md`, scored **once**. It needs a GPU to be practical.

**What you get back is one file**, `kronos-forecasts.json`. Scoring happens in the repository afterwards.

## What it needs, and what it does not

- Needs: a Python 3.12 machine with internet, and ideally an NVIDIA GPU.
- Does not need: the repository, any market-data login, a broker, or any key. The model's inputs are the file
  `kronos-inputs.json.gz` (45 NSE large-cap names, adjusted daily bars). It is Upstox-derived market data, so
  **upload it only as a private dataset, never public**.
- Every download is checked against a hash written in `TRIAL-LEDGER.md`. A wrong file stops the run.

## Option A: Kaggle (free GPU, recommended)

1. Download `kronos-trial11-package.zip` and unzip it.
2. On kaggle.com: **Create, New Dataset**. Upload `generate_kronos_forecasts.py`, `kronos_trial11.py` and
   `kronos-inputs.json.gz`. Set it to **Private**. Name it `kronos-trial11`.
3. **Create, New Notebook.** In the notebook settings choose **Accelerator: GPU** (T4 or P100) and turn **Internet
   on**. Click **Add Input** and pick your `kronos-trial11` dataset.
4. Run these cells (the dataset folder is under `/kaggle/input/`; adjust the name if Kaggle shows a different one):

```python
!pip -q install einops huggingface_hub safetensors tqdm pandas
!mkdir -p /kaggle/working/run && cp /kaggle/input/kronos-trial11/* /kaggle/working/run/
%cd /kaggle/working/run
!python kronos_trial11.py prepare   --workspace ws
!python kronos_trial11.py selfcheck --workspace ws
!python kronos_trial11.py forecast  --workspace ws --out kronos-forecasts.json
```

5. `selfcheck` must print `OK: the inputs reproduce the declared plan`. `forecast` prints the device it uses; it must
   say `cuda`. When it finishes, download `/kaggle/working/run/kronos-forecasts.json` from the notebook's Output tab.
6. Put that file at `reports/kronos_trial11/kronos-forecasts.json` in the repository, or give it to the agent, and
   run `python scripts/score_kronos_trial11.py`.

If the session stops part-way, run the last cell again: it resumes from its checkpoint. For a long unattended run use
**Save Version, Save & Run All** so Kaggle keeps the output. I could not measure GPU speed from here (no GPU in the
building container); on a T4 I expect well under a few hours, but that is a guess.

## Option B: your laptop

```bash
pip install torch numpy pandas einops huggingface_hub safetensors tqdm
python kronos_trial11.py prepare   --workspace ws
python kronos_trial11.py selfcheck --workspace ws
python kronos_trial11.py forecast  --workspace ws --out kronos-forecasts.json
```

Inside the repository, use `python scripts/kronos_trial11.py ...`. **On a CPU this takes days**: measured 694.5 s per
decision date on four cores, 529 dates, about 102 hours. It is practical only with an NVIDIA GPU
(`--device cuda`). Do not lower the path count or switch to a smaller model to make it fit: the declaration forbids
it, and the trial then waits.

## The rules that make the result mean something

- **The first complete run is the one scored.** If you start it on Kaggle and also on a laptop, whichever finishes
  first (23,805 forecasts, integrity check passes) is scored and the other is discarded **unscored**. Do not compare
  them, and do not re-run because a result is disappointing.
- **No fallback.** Never one path, never `Kronos-small`.
- `scripts/score_kronos_trial11.py` refuses a second scoring, whatever the file is called.
