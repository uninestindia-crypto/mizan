# Completed work: use the real EmbeddingGemma 2 and say honestly what runs

STATUS: COMPLETED (committed on `main`, not pushed, not released)  
OWNER: Claude Code (Sonnet 5.5)  
TOOL: Claude Code  
STARTED_UTC: 2026-10-10T05:35:00Z  
COMPLETED_UTC: 2026-10-10  
STARTING_REVISION: d8862d7f2e1cca308da28c0971ff3bebfa8a3737  
WORKTREE_OR_BRANCH: `D:\Quant OS Project\Mizan` on `main` (shared checkout; no other agent was running on this machine)

## Objective

GOAL_LINE: G5 (and G1). Founder instruction, 2026-10-10: fix the EmbeddingGemma problem using EmbeddingGemma 2 (Google, October 2026),
not the first-generation model.

Findings that drove the work (sources: Google's EmbeddingGemma page, the Hugging Face model card and API, checked 2026-10-10):

- Real repository `google/embeddinggemma-2`: ungated, Apache 2.0, 744,371,512 parameters (BF16), about 3.0 GB. Text-only configuration
  (`vision_config` and `audio_config` set to `None`) is about 270M parameters. Native output 768, Matryoshka 512/256/128.
- The code's default `google/embeddinggemma-270m` is not a repository (public search for author `google`, name `embeddinggemma` lists
  `embeddinggemma-2`, `-300m` and two 300m quantised variants).
- The old in-process path mean-pooled the raw `AutoModel` output; the card's pipeline is mean pooling, a 512 to 768 projection and
  normalisation, with task prefixes. It also reloaded the model on every call and padded short vectors with zeros.
- The shipped app and the dev venv bundle no torch, transformers or sentence-transformers, so a factory-new laptop always used the
  keyword-and-hash substitute while screens said "EmbeddingGemma 2".
- `qlib/pipeline.py` attaches one vector (first 16 numbers of one embedding of the paper summaries) to every training and live row, so
  those columns carry no stock-specific information. The shipped `quant_slm_*.json` weights record no embedding backend.
- The hardware card said embeddings serve "AAOIFI Shariah standards", which contradicts the product's promise that halal results never
  come from an AI model, and showed a green "In-Process" tick for every model whatever its status.

## Files changed

- `src/quant_system/research/embedding_gemma.py`: rewritten. Default `google/embeddinggemma-2`; real backend through sentence-transformers,
  text-only config, card task prefixes (query vs document), loaded once; Matryoshka truncate + re-normalise; width check instead of zero
  padding; `auto` picks the real model only when its weights are already cached (no surprise 3 GB download); Ollama model name is
  configurable and never reported as EmbeddingGemma 2; a failing real backend flips the reported backend to the substitute, clears the
  cache, bumps `generation` and records `fallback_reason`; new `label`, `uses_real_model`, `served_model`, `real_model_status()`.
- `src/quant_system/research/rag_engine.py`: question embedded as a query; rebuilds the paper vectors if the backend changes (never mixes
  two vector spaces); metadata now carries `embedding_label`, `embedding_is_real_model` and the model that really served.
- `src/quant_system/server/v2/hardware.py`: the card is `embeddinggemma-2`, "EmbeddingGemma 2 (text, about 270M)", "~3 GB download", with a
  status of READY / NOT DOWNLOADED / NOT INSTALLED and a description that matches; no Shariah claim.
- `frontend/src/components/HardwareAcceleratorCard.tsx`: "In-Process" tick only for ACTIVE or READY models, otherwise "Not running on this computer".
- `src/quant_system/server/v2/router.py`, `src/quant_system/server/static/index.html`, `src/quant_system/research/qlib/quant_slm.py`,
  `src/quant_system/research/qlib/pipeline.py`, `scripts/train_literature_alpha_model.py`, `scripts/run_slm_walk_forward_backtest.py`,
  `docs/CANDIDATE_FOUNDATION_MODELS.md`: wording now describes a fixed research-context vector and print the provider's own label.
- Tests: new `tests/test_embedding_gemma_honesty.py` (19 tests, fake sentence-transformers, no download) and
  `frontend/src/components/HardwareAcceleratorCard.test.tsx` (2 tests); `tests/test_hardware_accelerator.py` id updated.

## Commands and outcomes

| Command | Result | Evidence/notes |
|---|---|---|
| `pytest tests/test_embedding_gemma_honesty.py tests/test_embedding_gemma.py tests/test_hardware_accelerator.py tests/test_quant_rag.py` | PASS | 34 passed |
| mutation check: restore dead model id; skip cache clear on fallback; skip rebuild in search | PASS | each mutation made its matching test fail; files restored (unmutated run 19 passed) |
| `ruff check` / `ruff format --check` on `src tests scripts launcher.py quantos_studio.py` | PASS | clean, 737 files formatted |
| `mypy src scripts launcher.py` | PASS | no issues in 466 source files |
| `detect-secrets scan` on the changed files | PASS | 0 candidates |
| `pytest tests` (full, once, nothing else running) | PASS | 5842 passed, 6 skipped, 0 failed |
| `vitest run` (full) and `npm run typecheck` | PASS | 1540 passed; typecheck clean |

## Not done, said plainly

- **The real model has not been run.** There is no torch here and the download is about 3 GB. The real path is tested only against a fake
  `sentence_transformers`, so what is proven is how the provider calls it (id, text-only config, prefixes, width, fallback, labels), not the
  model's own numbers or that `config_kwargs` loads cleanly in the installed library version. A real smoke test needs the founder's permission
  for the install and the download.
- The Quant SLM is not retrained (a new trial needs its own dated declaration). Its 16 context columns are still constant across stocks.
  The training script and any live path each build that vector with whatever backend is active at the time, so a model trained with one
  backend and served with another sees shifted inputs (train/serve skew). Open; needs a decision, not a patch.
- Old release notes (3.1.0 in `updates.py` and `Settings.tsx`, `CHANGELOG.md` line 62) still say "embedding-gemma-2 / XRIV features". They are
  history and were not rewritten.
- Not pushed and not released. Release status after this commit: 1 of 3 user-visible changes.

## Blockers and conflicts

None. No other active record claimed these paths.

## Stop point

All edits committed on `main`. Tracked tree clean except the cleared side-effect files.

## Next safe action

With the founder's permission, a real smoke test in an isolated scratch environment (not the project venv): install torch and
sentence-transformers there, download `google/embeddinggemma-2`, embed a few finance sentences, and confirm width 768, unit norm after
truncation, query/document prefix behaviour, and that `uses_real_model` becomes true.

## Update: the real model was run (founder approved the install and the 3 GB download, 2026-10-10)

Done in an isolated scratch environment (venv and Hugging Face cache under the session scratchpad; the project venv was not changed):
`pip install --only-binary=:all: torch sentence-transformers httpx` (torch 2.14.1+cpu has an ARM64 wheel), then `pillow` and `torchvision`.

What the real run found that the fake-module tests could not:

1. The model's processor imports PIL and then torchvision even for text-only use. Without them the real backend failed to load and the provider
   fell back and said "could not run here" (the fallback and the label worked as designed). `real_model_status()` had said READY in that state;
   it now requires `sentence_transformers`, `torch`, `torchvision` and `PIL` (`REQUIRED_PACKAGES`), with a test per library.
2. The checkpoint's bfloat16 is 9 to 10 times slower than float32 on this CPU (5 short texts 3.1 s against 0.35 s; one 1,300-token text 30 s
   against 3.9 s) for the same vectors (cosine 0.9997 or better). The provider now loads with `model_kwargs={"dtype": "float32"}`.
3. The library reports no maximum sequence length (an absurdly large number), so long inputs could run away. The provider now sets
   `max_seq_length = 8192`, the card's limit.

Final run of the finished provider (`mode="transformers"`): `uses_real_model` true, no fallback, 271,002,624 parameters (so the text-only config
drops the image and audio towers), float32, 768 wide, unit norm, Matryoshka 128/256/512 unit norm, the right sentence ranked first (0.82
against 0.47 to 0.64; the keyword substitute scored 0.99 for the match and about 0 for everything else), paper search served by the real model
(top paper: the Deflated Sharpe Ratio paper, 0.747, `embedding_is_real_model` true). Tests after the fixes: 39 passed in the four related files.

Still open: the real model is not in the installed app (torch, torchvision, pillow and a 3 GB download are not bundled), and nothing in the app
builds `QuantPaperRAG`, so no screen can use paper search yet (only scripts and the optional `rag_engine` hook of the AI advisers do).
Each provider object loads its own copy of the model (about 1.1 GB of weights), so a screen should share one provider.

## Correction: the download is 1.5 GB, not 3 GB

Earlier lines in this record, the hardware card, the docs and a test said "about 3 GB". That came from the Hugging Face page's `usedStorage`
(3,014,689,355 bytes), which counts more than the file you download. Measured on 2026-10-10 after the real download: the model cache is 1.5 GB
(`model.safetensors` is 744M parameters at 2 bytes each), and the libraries it needs (torch, torchvision, transformers, sentence-transformers,
pillow) are 1.1 GB, of which torch alone is 539 MB. The installed app is 115 MB, so bundling would roughly add 2.6 GB. The card now says
"~1.5 GB download".
