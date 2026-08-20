#!/usr/bin/env python3
"""Create a deterministic first-pass map of a product codebase.

The output is intentionally a set of discovery leads. It does not claim that
static inspection found every runtime surface.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


SKIP_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".idea",
    ".vscode",
    ".venv",
    "venv",
    "node_modules",
    "vendor",
    "Pods",
    "DerivedData",
    "build",
    "dist",
    "out",
    "target",
    ".next",
    ".nuxt",
    ".svelte-kit",
    ".gradle",
    ".dart_tool",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    "coverage",
    ".deep-product-qa",
}

SURFACE_DIR_NAMES = {
    "app",
    "apps",
    "api",
    "apis",
    "backend",
    "client",
    "clients",
    "components",
    "controllers",
    "desktop",
    "features",
    "frontend",
    "handlers",
    "integrations",
    "jobs",
    "mobile",
    "pages",
    "routes",
    "screens",
    "server",
    "services",
    "views",
    "web",
    "workers",
}

ROUTE_FILE_NAMES = {
    "routes.ts",
    "routes.tsx",
    "routes.js",
    "routes.jsx",
    "router.ts",
    "router.tsx",
    "router.js",
    "router.jsx",
    "urls.py",
    "routes.py",
}

API_SCHEMA_NAMES = {
    "openapi.json",
    "openapi.yaml",
    "openapi.yml",
    "swagger.json",
    "swagger.yaml",
    "swagger.yml",
    "schema.graphql",
    "schema.gql",
    "schema.prisma",
}

TEST_MARKERS = (
    ".test.",
    ".spec.",
    "_test.",
    "test_",
    "tests.",
)

CRITICAL_MANIFESTS = {
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "Pipfile",
    "poetry.lock",
    "manage.py",
    "Cargo.toml",
    "go.mod",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
    "settings.gradle",
    "settings.gradle.kts",
    "pubspec.yaml",
    "Package.swift",
    "composer.json",
    "Gemfile",
    "mix.exs",
    "Dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
    "AndroidManifest.xml",
    "Info.plist",
    "tauri.conf.json",
    "capacitor.config.ts",
    "capacitor.config.json",
}


@dataclass
class SampleBucket:
    limit: int
    count: int = 0
    samples: list[str] = field(default_factory=list)

    def add(self, value: str) -> None:
        self.count += 1
        if len(self.samples) < self.limit:
            self.samples.append(value)

    def as_dict(self) -> dict[str, Any]:
        return {
            "count": self.count,
            "samples": sorted(self.samples),
            "truncated": self.count > len(self.samples),
        }


def relative(path: Path, root: Path) -> str:
    try:
        value = path.relative_to(root).as_posix()
        return value or "."
    except ValueError:
        return path.as_posix()


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def dependency_names(package: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for key in ("dependencies", "devDependencies", "peerDependencies", "optionalDependencies"):
        value = package.get(key, {})
        if isinstance(value, dict):
            names.update(str(name) for name in value)
    return names


def package_hints(path: Path, root: Path) -> dict[str, Any]:
    package = read_json(path)
    entry: dict[str, Any] = {
        "path": relative(path, root),
        "kind": "javascript-package",
        "platform_hints": [],
        "framework_hints": [],
    }
    if package is None:
        entry["parse_warning"] = "package.json could not be parsed"
        return entry

    deps = dependency_names(package)
    scripts = package.get("scripts", {})
    entry["name"] = package.get("name")
    entry["private"] = package.get("private")
    entry["scripts"] = sorted(scripts) if isinstance(scripts, dict) else []

    rules = {
        "next": ("web", "Next.js"),
        "react": ("web", "React"),
        "vue": ("web", "Vue"),
        "nuxt": ("web", "Nuxt"),
        "@angular/core": ("web", "Angular"),
        "svelte": ("web", "Svelte"),
        "astro": ("web", "Astro"),
        "express": ("backend", "Express"),
        "fastify": ("backend", "Fastify"),
        "koa": ("backend", "Koa"),
        "@nestjs/core": ("backend", "NestJS"),
        "react-native": ("mobile", "React Native"),
        "expo": ("mobile", "Expo"),
        "@capacitor/core": ("mobile", "Capacitor"),
        "cordova": ("mobile", "Cordova"),
        "electron": ("desktop", "Electron"),
        "@tauri-apps/api": ("desktop", "Tauri"),
    }
    platforms: set[str] = set()
    frameworks: set[str] = set()
    for dependency, (platform, framework) in rules.items():
        if dependency in deps:
            platforms.add(platform)
            frameworks.add(framework)
    entry["platform_hints"] = sorted(platforms)
    entry["framework_hints"] = sorted(frameworks)
    return entry


def generic_manifest_hints(path: Path, root: Path) -> dict[str, Any] | None:
    name = path.name
    suffix = path.suffix.lower()
    entry: dict[str, Any] = {
        "path": relative(path, root),
        "kind": "manifest",
        "platform_hints": [],
        "framework_hints": [],
    }

    if name == "package.json":
        return package_hints(path, root)
    if name in {"pyproject.toml", "requirements.txt", "Pipfile", "poetry.lock", "manage.py"}:
        entry.update(kind="python-project", platform_hints=["backend"], framework_hints=["Python"])
    elif name == "Cargo.toml":
        entry.update(kind="rust-project", framework_hints=["Rust"])
    elif name == "go.mod":
        entry.update(kind="go-project", platform_hints=["backend"], framework_hints=["Go"])
    elif name in {"pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"}:
        entry.update(kind="jvm-project", framework_hints=["JVM"])
    elif name == "AndroidManifest.xml":
        entry.update(kind="android-application", platform_hints=["android", "mobile"], framework_hints=["Android"])
    elif name in {"Info.plist", "Package.swift"}:
        entry.update(kind="apple-project", platform_hints=["apple"], framework_hints=["Apple native"])
    elif name == "pubspec.yaml":
        entry.update(kind="flutter-project", platform_hints=["mobile"], framework_hints=["Flutter"])
    elif name == "tauri.conf.json":
        entry.update(kind="tauri-application", platform_hints=["desktop"], framework_hints=["Tauri"])
    elif name.startswith("capacitor.config"):
        entry.update(kind="capacitor-application", platform_hints=["mobile"], framework_hints=["Capacitor"])
    elif name in {"composer.json", "Gemfile", "mix.exs"}:
        entry.update(kind="server-project", platform_hints=["backend"])
    elif name.startswith("Dockerfile") or name in {"docker-compose.yml", "docker-compose.yaml", "compose.yml", "compose.yaml"}:
        entry.update(kind="container-config", platform_hints=["service"])
    elif suffix in {".sln", ".csproj", ".fsproj"}:
        entry.update(kind="dotnet-project", framework_hints=[".NET"])
    else:
        return None
    return entry


def is_manifest(path: Path) -> bool:
    return (
        path.name in CRITICAL_MANIFESTS
        or path.name.startswith("Dockerfile")
        or path.suffix.lower() in {".sln", ".csproj", ".fsproj"}
    )


def is_test_file(name: str, parts: Iterable[str]) -> bool:
    lowered = name.lower()
    lowered_parts = {part.lower() for part in parts}
    return "test" in lowered_parts or "tests" in lowered_parts or any(marker in lowered for marker in TEST_MARKERS)


def discover(root: Path, sample_limit: int) -> dict[str, Any]:
    manifests: list[dict[str, Any]] = []
    surface_dirs = SampleBucket(sample_limit)
    route_files = SampleBucket(sample_limit)
    api_schemas = SampleBucket(sample_limit)
    tests = SampleBucket(sample_limit)
    docs = SampleBucket(sample_limit)
    env_examples = SampleBucket(sample_limit)
    ci_files = SampleBucket(sample_limit)
    migration_paths = SampleBucket(sample_limit)
    locale_paths = SampleBucket(sample_limit)
    feature_flag_paths = SampleBucket(sample_limit)
    application_roots: set[str] = set()
    platform_hints: set[str] = set()
    framework_hints: set[str] = set()
    files_scanned = 0
    symlink_dirs_skipped: list[str] = []

    for current, dirs, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        retained_dirs: list[str] = []
        for dirname in dirs:
            child = current_path / dirname
            if dirname in SKIP_DIRS:
                continue
            if child.is_symlink():
                if len(symlink_dirs_skipped) < sample_limit:
                    symlink_dirs_skipped.append(relative(child, root))
                continue
            if dirname.endswith((".xcodeproj", ".xcworkspace")):
                manifest = {
                    "path": relative(child, root),
                    "kind": "apple-project",
                    "platform_hints": ["apple"],
                    "framework_hints": ["Xcode"],
                }
                manifests.append(manifest)
                platform_hints.add("apple")
                framework_hints.add("Xcode")
                application_roots.add(relative(current_path, root))
            retained_dirs.append(dirname)
            if dirname.lower() in SURFACE_DIR_NAMES:
                surface_dirs.add(relative(child, root))
        dirs[:] = retained_dirs

        rel_current_parts = Path(relative(current_path, root)).parts
        lowered_parts = {part.lower() for part in rel_current_parts}
        if "migrations" in lowered_parts or "migration" in lowered_parts:
            migration_paths.add(relative(current_path, root))
        if "locales" in lowered_parts or "i18n" in lowered_parts or "translations" in lowered_parts:
            locale_paths.add(relative(current_path, root))
        if "feature-flags" in lowered_parts or "feature_flags" in lowered_parts or "flags" in lowered_parts:
            feature_flag_paths.add(relative(current_path, root))

        for filename in files:
            files_scanned += 1
            path = current_path / filename
            rel = relative(path, root)
            lowered = filename.lower()

            if is_manifest(path):
                manifest = generic_manifest_hints(path, root)
                if manifest is not None:
                    manifests.append(manifest)
                    application_roots.add(relative(current_path, root))
                    platform_hints.update(manifest.get("platform_hints", []))
                    framework_hints.update(manifest.get("framework_hints", []))

            relative_parts = (*rel_current_parts, filename)
            if filename in ROUTE_FILE_NAMES or "route" in lowered or any(part.lower() in {"pages", "routes", "screens"} for part in relative_parts):
                route_files.add(rel)
            if filename in API_SCHEMA_NAMES or lowered.startswith(("openapi.", "swagger.")):
                api_schemas.add(rel)
            if is_test_file(filename, relative_parts):
                tests.add(rel)
            if lowered.startswith(("readme", "contributing")) or filename == "AGENTS.md":
                docs.add(rel)
            if lowered in {".env.example", ".env.sample", "env.example", "env.sample"} or lowered.endswith((".env.example", ".env.sample")):
                env_examples.add(rel)
            if ".github" in path.parts and "workflows" in path.parts:
                ci_files.add(rel)
            elif lowered in {".gitlab-ci.yml", "azure-pipelines.yml", "jenkinsfile", "circle.yml"}:
                ci_files.add(rel)

    warnings: list[str] = []
    if not manifests:
        warnings.append("No recognized project manifest was found; inspect the repository manually.")
    if tests.count == 0:
        warnings.append("No test files were recognized; this does not prove that tests are absent.")
    if docs.count == 0:
        warnings.append("No README, CONTRIBUTING, or AGENTS instruction file was recognized.")
    if not platform_hints:
        warnings.append("No platform could be inferred safely from recognized manifests.")
    if symlink_dirs_skipped:
        warnings.append("Symlinked directories were not traversed; inspect them when they are part of the product.")

    manifests.sort(key=lambda item: str(item.get("path", "")))
    return {
        "schema_version": 1,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": root.as_posix(),
        "statement": "Static discovery leads only; runtime and behavioral discovery remain mandatory.",
        "summary": {
            "files_scanned": files_scanned,
            "recognized_manifests": len(manifests),
            "application_roots": len(application_roots),
            "platform_hints": sorted(platform_hints),
            "framework_hints": sorted(framework_hints),
        },
        "application_roots": sorted(application_roots),
        "manifests": manifests,
        "surface_directories": surface_dirs.as_dict(),
        "route_and_screen_files": route_files.as_dict(),
        "api_and_data_schemas": api_schemas.as_dict(),
        "test_files": tests.as_dict(),
        "documentation": docs.as_dict(),
        "environment_examples": env_examples.as_dict(),
        "ci_files": ci_files.as_dict(),
        "migration_paths": migration_paths.as_dict(),
        "locale_paths": locale_paths.as_dict(),
        "feature_flag_paths": feature_flag_paths.as_dict(),
        "symlink_directories_skipped": sorted(symlink_dirs_skipped),
        "warnings": warnings,
        "mandatory_next_steps": [
            "Verify every application root and nested workspace manually.",
            "Derive roles, permissions, routes, states, flags, integrations, and supported platforms from source.",
            "Launch each product and perform runtime navigation discovery.",
            "Inspect logs, network calls, persistence, workers, and external effects for hidden behavior.",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, help="Root of the codebase to inspect")
    parser.add_argument("--output", help="JSON output path; omit to print to stdout")
    parser.add_argument("--max-samples", type=int, default=200, help="Maximum paths retained per sampled category")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        raise SystemExit(f"Codebase root is not a directory: {root}")
    if args.max_samples < 1:
        raise SystemExit("--max-samples must be at least 1")

    result = discover(root, args.max_samples)
    rendered = json.dumps(result, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        output = Path(args.output).expanduser().resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(f"Discovery written to {output}")
        print(f"Files scanned: {result['summary']['files_scanned']}")
        print("Reminder: runtime and behavioral discovery are still mandatory.")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
