"""Runner for short-horizon trial 11 (Kronos-base, five sampled paths), on any machine.

Declaration: `reports/kronos_trial11/TRIAL-LEDGER.md`, frozen before any forecast of this trial exists.

Trial 10 ran Kronos-small with one path on a four-core CPU, because the declared compute rule fitted a
laptop night. This runs the largest released model, with the paths averaged, which needs a GPU: base
with five paths measured 694.5 s per decision date on four CPU cores, about 102 hours in all.

It needs no repository, no market-data credential and no broker. The model's inputs are one file, the
exact adjusted bars the declared generator would build from the repository, and the declared generator is
run **unmodified**: this script checks its SHA-256, then replaces only the three things the declaration says
may change (where the bars come from, which device the model runs on, and the laptop-only pause rules).

    python scripts/kronos_trial11.py export-inputs        # in the repository, once
    python scripts/kronos_trial11.py package              # in the repository: the zip to upload
    python kronos_trial11.py prepare   --workspace ws     # downloads and hash-checks code and weights
    python kronos_trial11.py selfcheck --workspace ws     # proves the inputs reproduce the declared plan
    python kronos_trial11.py forecast  --workspace ws --out kronos-forecasts.json

A forecast run resumes from its checkpoint (`<out>.partial.jsonl`), so a session that is cut off loses
nothing. Scoring is a separate step in the repository: `scripts/score_kronos_trial11.py`.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import os
import sys
import urllib.request
import zipfile
from collections.abc import Callable, Mapping
from datetime import date
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
GENERATOR_NAME = "generate_kronos_forecasts.py"
INPUTS_NAME = "kronos-inputs.json.gz"
INPUTS_SCHEMA = "kronos-trial11-inputs-v1"

#: SHA-256 of the declared generator, `scripts/generate_kronos_forecasts.py`. Any other file is refused.
GENERATOR_SHA256 = "ef17b128de13f93b50a6874c5e637c8c8d2840b55966a07c6e470aef94d49e8a"

KRONOS_CODE_COMMIT = "67b630e67f6a18c9e9be918d9b4337c960db1e9a"
KRONOS_CODE_SHA256 = {
    "__init__.py": "f8f856ca3fedadcaac97e196be23d1aeda1c3c9ffe8903d66d43ea3bcac6240c",
    "kronos.py": "0a5f90282e2039c2de0771473419715c845def154896dbd0f5747837e6241032",
    "module.py": "a07edbadc0e96804c8158c021bbc6063bb7cc43b34d7fc470d5c8ff2005a409f",
}

#: Hub repository -> (revision, SHA-256 of model.safetensors). Verified after download, every time.
WEIGHTS = {
    "NeoQuasar/Kronos-Tokenizer-base": (
        "0e0117387f39004a9016484a186a908917e22426",
        "59d85f6af76a2c3b8240ea06cb21db4213b4eeca053f246b23e29cf832fc6bee",
    ),
    "NeoQuasar/Kronos-base": (
        "2b554741eca47781b64468546e77fef3e85130e6",
        "abff193acab6db1a0368e9773e75799d11403b6d054ee6d5f0a11aeabc5f4b83",
    ),
}

MODEL_KEY = "base"
SAMPLES = 5
TRIAL = 11
DECLARATION = "reports/kronos_trial11/TRIAL-LEDGER.md"

EXPECTED_NAMES = 45
EXPECTED_DATES = 529
EXPECTED_FORECASTS = 23_805


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def find_file(explicit: Path | None, name: str, *fallbacks: Path) -> Path:
    """The first existing candidate. A named file that is missing is an error, never a silent fallback."""
    if explicit is not None:
        if not explicit.is_file():
            raise SystemExit(f"{explicit} does not exist")
        return explicit
    for candidate in (HERE / name, *fallbacks):
        if candidate.is_file():
            return candidate
    raise SystemExit(f"cannot find {name}; pass it explicitly")


def load_generator(path: Path) -> Any:
    """The declared generator, refused unless it is byte-for-byte the declared file."""
    actual = sha256_file(path)
    if actual != GENERATOR_SHA256:
        raise SystemExit(
            f"{path} has SHA-256 {actual}, not the declared {GENERATOR_SHA256}. "
            "The trial runs the declared generator unmodified."
        )
    spec = importlib.util.spec_from_file_location("generate_kronos_forecasts", path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def write_inputs(bars_by_symbol: Mapping[str, list[Any]], path: Path) -> None:
    """The model's inputs as one file. Floats are written with Python's shortest exact representation."""
    document = {
        "schema": INPUTS_SCHEMA,
        "trial": TRIAL,
        "symbols": {
            symbol: [[b.on.isoformat(), b.open, b.high, b.low, b.close, b.volume] for b in bars]
            for symbol, bars in sorted(bars_by_symbol.items())
        },
    }
    payload = json.dumps(document, separators=(",", ":")).encode("utf-8")
    with path.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as gz:
        gz.write(payload)


def read_inputs(path: Path, generator: Any) -> dict[str, list[Any]]:
    document = json.loads(gzip.decompress(path.read_bytes()).decode("utf-8"))
    if document.get("schema") != INPUTS_SCHEMA:
        raise SystemExit(f"{path} is not a {INPUTS_SCHEMA} file")
    bar = generator.Bar
    return {
        symbol: [
            bar(date.fromisoformat(row[0]), row[1], row[2], row[3], row[4], row[5]) for row in rows
        ]
        for symbol, rows in document["symbols"].items()
    }


def plan_summary(generator: Any, bars_by_symbol: Mapping[str, list[Any]]) -> tuple[int, int, int]:
    planned = generator.plan_dates(bars_by_symbol)
    return len(bars_by_symbol), len(planned), sum(len(item.symbols) for item in planned)


def resolve_device(requested: str, cuda_available: bool) -> str:
    """`auto` takes a GPU when there is one. Asking for `cuda` without one is an error, not a downgrade."""
    if requested == "auto":
        return "cuda" if cuda_available else "cpu"
    if requested == "cuda" and not cuda_available:
        raise SystemExit("--device cuda was requested but no CUDA device is available")
    return requested


def verify_code(kronos_src: Path) -> None:
    for name, expected in KRONOS_CODE_SHA256.items():
        path = kronos_src / "model" / name
        if not path.is_file() or sha256_file(path) != expected:
            raise SystemExit(f"{path} is missing or differs from the declared Kronos code")


def fetch_file(url: str, target: Path) -> None:
    with urllib.request.urlopen(url, timeout=60) as response:  # noqa: S310 - pinned https URL
        target.write_bytes(response.read())


def download_code(workspace: Path) -> None:
    source = workspace / "kronos-src" / "model"
    source.mkdir(parents=True, exist_ok=True)
    base = f"https://raw.githubusercontent.com/shiyu-coder/Kronos/{KRONOS_CODE_COMMIT}/model"
    for name in KRONOS_CODE_SHA256:
        if not (source / name).is_file():
            fetch_file(f"{base}/{name}", source / name)
    verify_code(workspace / "kronos-src")
    print("Kronos code: three files match the declared SHA-256 values")


def fetch_weights(workspace: Path, repo: str, revision: str, expected: str) -> dict[str, str]:
    from huggingface_hub import snapshot_download  # type: ignore[import-not-found,unused-ignore]

    folder = workspace / "weights" / repo.split("/")[1]
    snapshot_download(repo, revision=revision, local_dir=str(folder))
    actual = sha256_file(folder / "model.safetensors")
    if actual != expected:
        raise SystemExit(f"{repo}: weights SHA-256 {actual} differs from the declared {expected}")
    print(f"{repo}: revision {revision[:12]}, weights match the declared SHA-256")
    return {"revision": revision, "model_safetensors_sha256": actual}


def download_weights(workspace: Path) -> dict[str, dict[str, str]]:
    return {
        repo: fetch_weights(workspace, repo, revision, expected)
        for repo, (revision, expected) in WEIGHTS.items()
    }


def prepare(workspace: Path) -> int:
    """Download the pinned Kronos code and weights into `workspace`, verifying every hash."""
    download_code(workspace)
    pinned = download_weights(workspace)
    record = workspace / "weights" / "pinned-revisions.json"
    record.write_text(json.dumps(pinned, indent=2), encoding="utf-8")
    return 0


def selfcheck(generator: Any, inputs: Path) -> int:
    names, dates, forecasts = plan_summary(generator, read_inputs(inputs, generator))
    print(f"inputs: {names} names, {dates} decision dates, {forecasts:,} forecasts")
    expected = (EXPECTED_NAMES, EXPECTED_DATES, EXPECTED_FORECASTS)
    if (names, dates, forecasts) != expected:
        print(
            f"MISMATCH: the declared plan is {expected[0]} names, {expected[1]} dates, {expected[2]:,} forecasts"
        )
        return 1
    print("OK: the inputs reproduce the declared plan")
    return 0


def predictor_builder(generator: Any, device: str) -> Callable[..., Any]:
    """The generator's `build_predictor`, identical except that the device is not fixed to the CPU."""

    def build(model_key: str, *, weights_dir: Path, kronos_src: Path) -> Any:
        sys.path.insert(0, str(kronos_src))
        from model import (  # type: ignore[import-not-found,unused-ignore]
            Kronos,
            KronosPredictor,
            KronosTokenizer,
        )

        tokenizer_folder = generator.verified_weights(weights_dir, generator.TOKENIZER_REPO)
        model_folder = generator.verified_weights(weights_dir, generator.MODEL_REPOS[model_key])
        tokenizer = KronosTokenizer.from_pretrained(str(tokenizer_folder))
        model = Kronos.from_pretrained(str(model_folder))
        tokenizer.eval()
        model.eval()
        return KronosPredictor(model, tokenizer, device=device, max_context=generator.CONTEXT)

    return build


def device_description(device: str) -> str:
    if device != "cuda":
        return "cpu"
    import torch  # type: ignore[import-not-found,unused-ignore]

    return f"cuda: {torch.cuda.get_device_name(0)}"


def configure_generator(generator: Any, bars: dict[str, list[Any]], device: str) -> None:
    """The only three things the declaration lets this trial change in the declared generator."""
    generator.load_bars = lambda _args: bars
    generator.in_market_hours = lambda _now: False
    generator.on_ac_power = lambda: None
    generator.build_predictor = predictor_builder(generator, device)


def stamp_output(out: Path, device: str, inputs: Path) -> None:
    """Add what a scorer needs to trust the file: which trial, which code, which device."""
    document = json.loads(out.read_text(encoding="utf-8"))
    document["trial"] = TRIAL
    document["declaration"] = DECLARATION
    document["device"] = device_description(device)
    document["runner_sha256"] = sha256_file(Path(__file__))
    document["generator_sha256"] = GENERATOR_SHA256
    document["inputs_sha256"] = sha256_file(inputs)
    out.write_text(json.dumps(document), encoding="utf-8")


def forecast(args: argparse.Namespace, generator: Any, inputs: Path) -> int:
    import torch  # type: ignore[import-not-found,unused-ignore]

    device = resolve_device(args.device, bool(torch.cuda.is_available()))
    workspace: Path = args.workspace
    verify_code(workspace / "kronos-src")
    bars = read_inputs(inputs, generator)
    declared = (EXPECTED_NAMES, EXPECTED_DATES, EXPECTED_FORECASTS)
    if plan_summary(generator, bars) != declared:
        raise SystemExit("the inputs do not reproduce the declared plan; run selfcheck")

    os.environ.setdefault("HF_HOME", str(workspace / "hf-home"))
    configure_generator(generator, bars, device)
    print(f"device: {device_description(device)}; model {MODEL_KEY}, {SAMPLES} paths per name")
    out: Path = args.out
    command = ["--kronos-src", str(workspace / "kronos-src")]
    command += ["--weights-dir", str(workspace / "weights"), "forecast"]
    command += ["--model", MODEL_KEY, "--samples", str(SAMPLES), "--out", str(out)]
    code = int(generator.main(command))
    if code == 0:
        stamp_output(out, device, inputs)
        print(f"written {out}; send this one file back, it is the trial's whole output")
    return code


def export_inputs(args: argparse.Namespace, generator: Any) -> int:
    """Repository only: the exact bars the declared generator builds, written once for every machine."""
    root = HERE.parent
    sys.path.insert(0, str(root / "scripts"))
    sys.path.insert(0, str(root / "src"))
    namespace = argparse.Namespace(
        market_cache=root / "data/evidence/market-cache/nifty50-current-20160822-20260821/store",
        universe=root / "data/authorities/nse-research-universe-liquid-10y.csv",
        corporate_actions_dir=root
        / "data/evidence/market-cache/all-market-20160822-20260821/corporate-actions",
        validated_factors=root / "data/authorities/nse-validated-demerger-factors.json",
        subset_size=50,
    )
    bars = generator.load_bars(namespace)
    out: Path = args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    write_inputs(bars, out)
    again = read_inputs(out, generator)
    if again != bars:
        raise SystemExit("the written inputs do not read back identically")
    print(
        f"wrote {out}: {plan_summary(generator, again)} names/dates/forecasts; sha256 {sha256_file(out)}"
    )
    return 0


PACKAGE_NAME = "kronos-trial11-package.zip"


def package_members(root: Path) -> list[tuple[str, Path]]:
    """What a machine without the repository needs, as (name inside the zip, source file)."""
    report = root / "reports" / "kronos_trial11"
    return [
        (GENERATOR_NAME, root / "scripts" / GENERATOR_NAME),
        ("kronos_trial11.py", root / "scripts" / "kronos_trial11.py"),
        (INPUTS_NAME, report / INPUTS_NAME),
        ("README.md", report / "README.md"),
        ("TRIAL-LEDGER.md", report / "TRIAL-LEDGER.md"),
    ]


def build_package(root: Path, out: Path) -> int:
    """A zip anyone can upload to a GPU host. Deterministic: the same files give the same bytes."""
    members = package_members(root)
    if sha256_file(members[0][1]) != GENERATOR_SHA256:
        raise SystemExit("the generator is not the declared one; refusing to package it")
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, source in members:
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 6, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, source.read_bytes())
    print(f"wrote {out} ({out.stat().st_size / 1e6:.1f} MB); sha256 {sha256_file(out)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--generator", type=Path, default=None, help="the declared generator file")
    parser.add_argument("--inputs", type=Path, default=None, help="the inputs file")
    commands = parser.add_subparsers(dest="command", required=True)

    commands.add_parser(
        "export-inputs", help="repository only: write the inputs file"
    ).add_argument("--out", type=Path, default=HERE.parent / "reports/kronos_trial11" / INPUTS_NAME)
    commands.add_parser(
        "package", help="repository only: build the zip to upload to a GPU host"
    ).add_argument(
        "--out", type=Path, default=HERE.parent / "reports/kronos_trial11" / PACKAGE_NAME
    )
    for name, helptext in (
        ("prepare", "download and hash-check the pinned code and weights"),
        ("selfcheck", "prove the inputs reproduce the declared plan"),
        ("forecast", "run the trial's forecasts"),
    ):
        sub = commands.add_parser(name, help=helptext)
        sub.add_argument("--workspace", type=Path, default=Path("kronos-trial11-workspace"))
        if name == "forecast":
            sub.add_argument("--out", type=Path, default=Path("kronos-forecasts.json"))
            sub.add_argument("--device", choices=("auto", "cpu", "cuda"), default="auto")
    args = parser.parse_args(argv)

    repo_scripts = HERE.parent / "scripts" / GENERATOR_NAME
    if args.command == "package":
        return build_package(HERE.parent, args.out)
    if args.command == "prepare":
        return prepare(args.workspace)
    generator = load_generator(find_file(args.generator, GENERATOR_NAME, repo_scripts))
    if args.command == "export-inputs":
        return export_inputs(args, generator)
    inputs = find_file(
        args.inputs, INPUTS_NAME, HERE.parent / "reports/kronos_trial11" / INPUTS_NAME
    )
    if args.command == "selfcheck":
        return selfcheck(generator, inputs)
    return forecast(args, generator, inputs)


if __name__ == "__main__":
    raise SystemExit(main())
