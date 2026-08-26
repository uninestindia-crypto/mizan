"""Command-line interface for Mīzān models: export, download, upload, inspect, and verify."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from quant_system.modeling.mizan_hub import MizanHub, MizanHubError
from quant_system.modeling.mizan_model import MizanModel


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="quantos-mizan",
        description="Mizan Model CLI - Export, share, download, upload, and inspect QuantOS ML models.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True, help="Subcommand to execute")

    # Command: info / inspect
    info_parser = subparsers.add_parser(
        "info", help="Inspect a Mizan model package or default model"
    )
    info_parser.add_argument(
        "model_path",
        nargs="?",
        default=None,
        help="Path to model directory or .zip archive (defaults to built-in default Mizan model)",
    )

    # Command: export
    export_parser = subparsers.add_parser(
        "export", help="Export a Mizan model to a portable package"
    )
    export_parser.add_argument(
        "--output",
        "-o",
        type=Path,
        required=True,
        help="Destination path for the exported .zip archive or directory",
    )
    export_parser.add_argument(
        "--evidence-manifest",
        type=Path,
        default=None,
        help="Optional path to a QuantOS evidence manifest.json to export",
    )
    export_parser.add_argument(
        "--format",
        choices=["zip", "dir"],
        default="zip",
        help="Export format (zip archive or directory)",
    )

    # Command: download
    download_parser = subparsers.add_parser(
        "download", help="Download a Mizan model from URL or Hugging Face"
    )
    download_parser.add_argument(
        "source",
        help="Remote URL or Hugging Face repository ID (e.g. 'username/mizan-nse-alpha')",
    )
    download_parser.add_argument(
        "--output-dir",
        "-o",
        type=Path,
        default=None,
        help="Destination directory for the downloaded package",
    )
    download_parser.add_argument(
        "--filename",
        default="mizan_model.zip",
        help="Filename in the Hugging Face repository",
    )
    download_parser.add_argument(
        "--token",
        default=None,
        help="Hugging Face API token",
    )

    # Command: upload
    upload_parser = subparsers.add_parser(
        "upload", help="Upload a Mizan model package to Hugging Face Hub"
    )
    upload_parser.add_argument(
        "model_path",
        type=Path,
        help="Path to local Mizan model directory or .zip archive",
    )
    upload_parser.add_argument(
        "--repo-id",
        required=True,
        help="Target Hugging Face repository ID (e.g. 'org/mizan-v1')",
    )
    upload_parser.add_argument(
        "--token",
        default=None,
        help="Hugging Face API token (defaults to HF_TOKEN env variable)",
    )
    upload_parser.add_argument(
        "--private",
        action="store_true",
        help="Create repository as private",
    )

    # Command: verify
    verify_parser = subparsers.add_parser(
        "verify", help="Verify package checksums and cryptographic integrity"
    )
    verify_parser.add_argument(
        "model_path",
        type=Path,
        help="Path to model directory or .zip archive to verify",
    )

    # Command: predict
    predict_parser = subparsers.add_parser("predict", help="Run model scoring on feature input")
    predict_parser.add_argument(
        "--model",
        type=Path,
        default=None,
        help="Path to model directory or .zip archive",
    )
    predict_parser.add_argument(
        "--features",
        type=str,
        required=True,
        help="JSON string or path to JSON file containing feature mapping",
    )

    return parser


def handle_info(args: argparse.Namespace) -> int:
    if args.model_path:
        model = MizanHub.load_package(args.model_path)
    else:
        model = MizanModel.default_model()

    print("=================================================================")
    print(f"  Mizan Model: {model.config.model_name} ({model.config.model_id})")
    print("=================================================================")
    print(f"Candidate ID       : {model.config.candidate_id}")
    print(f"Version            : {model.config.version}")
    print(f"Architecture       : {model.config.model_type}")
    print(
        f"Feature Schema     : {model.config.feature_schema_id} (v{model.config.feature_schema_version})"
    )
    print(f"Feature Count      : {len(model.config.feature_names)}")
    print(f"Score Threshold    : {model.config.score_threshold}")
    print(f"L2 Penalty         : {model.config.l2_penalty}")
    print(f"Horizon Sessions   : {model.config.label_horizon_sessions}")
    print(f"Weights Hash       : {model.weights.weights_hash[:16]}...")
    print(f"Preprocessor Hash  : {model.preprocessor.preprocessor_hash[:16]}...")
    print(f"Model Card Hash    : {model.model_card.model_card_hash[:16]}...")
    print(f"Verdict            : {model.model_card.verdict}")
    print("-----------------------------------------------------------------")
    print("Key Evaluation Metrics:")
    for k, v in model.model_card.metrics.items():
        print(f"  {k:22s}: {v}")
    print("-----------------------------------------------------------------")
    print(f"Feature Names ({len(model.config.feature_names)}):")
    for i, name in enumerate(model.config.feature_names):
        mean = model.preprocessor.means[i]
        scale = model.preprocessor.scales[i]
        coeff = model.weights.coefficients[i]
        print(
            f"  {i + 1:02d}. {name:25s} | coeff={coeff:12s} | mean={mean:10s} | scale={scale:10s}"
        )
    print("=================================================================")
    return 0


def handle_export(args: argparse.Namespace) -> int:
    if args.evidence_manifest and Path(args.evidence_manifest).exists():
        manifest_data = json.loads(Path(args.evidence_manifest).read_text(encoding="utf-8"))
        model = MizanHub.from_evidence_manifest(manifest_data)
    else:
        model = MizanModel.default_model()

    package_zip = args.format == "zip" or args.output.suffix == ".zip"
    out = MizanHub.export_package(model, args.output, package_zip=package_zip)
    print(f"Successfully exported Mizan model package to: {out}")
    return 0


def handle_download(args: argparse.Namespace) -> int:
    source = args.source
    if source.startswith("http://") or source.startswith("https://"):
        model = MizanHub.download_from_url(source, output_dir=args.output_dir)
    else:
        model = MizanHub.download_from_hf(
            repo_id=source,
            filename=args.filename,
            token=args.token,
            local_dir=args.output_dir,
        )
    print(
        f"Successfully downloaded and verified Mizan model '{model.model_id}' (v{model.config.version})"
    )
    return 0


def handle_upload(args: argparse.Namespace) -> int:
    model = MizanHub.load_package(args.model_path)
    res = MizanHub.upload_to_hf(
        model=model,
        repo_id=args.repo_id,
        token=args.token,
        private=args.private,
    )
    print(f"Successfully uploaded Mizan model to: {res.get('repo_id')}")
    return 0


def handle_verify(args: argparse.Namespace) -> int:
    try:
        MizanHub.verify_package_integrity(args.model_path)
        print(f"Package '{args.model_path}' passed all cryptographic integrity checks.")
        return 0
    except MizanHubError as err:
        print(f"Integrity check FAILED for '{args.model_path}': {err}", file=sys.stderr)
        return 1


def handle_predict(args: argparse.Namespace) -> int:
    model = MizanHub.load_package(args.model) if args.model else MizanModel.default_model()

    feat_path = Path(args.features)
    if feat_path.exists():
        raw_input = json.loads(feat_path.read_text(encoding="utf-8"))
    else:
        raw_input = json.loads(args.features)

    if isinstance(raw_input, dict) and any(isinstance(v, dict) for v in raw_input.values()):
        # Universe dictionary
        scores = model.predict_scores(raw_input)
        ranked = model.rank_universe(raw_input)
        print(json.dumps({"scores": scores, "ranked": ranked}, indent=2))
    elif isinstance(raw_input, dict):
        score = model.predict_score(raw_input)
        print(json.dumps({"score": score}, indent=2))
    else:
        print("Invalid feature payload format. Expected JSON object.", file=sys.stderr)
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        if args.command in ("info", "inspect"):
            return handle_info(args)
        if args.command == "export":
            return handle_export(args)
        if args.command == "download":
            return handle_download(args)
        if args.command == "upload":
            return handle_upload(args)
        if args.command == "verify":
            return handle_verify(args)
        if args.command == "predict":
            return handle_predict(args)
    except Exception as err:
        print(f"Error: {err}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
