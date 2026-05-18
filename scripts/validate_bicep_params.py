"""
Bicep Parameter Mapping Validator
=================================
Validates that parameter names in *.parameters.json files exactly match
the param declarations in their corresponding Bicep templates.

Checks performed:
  1. Whitespace  – parameter names must have no leading/trailing spaces.
  2. Existence   – every JSON parameter must map to a `param` in the Bicep file.
  3. Casing      – names must match exactly (case-sensitive).
  4. Orphaned    – required Bicep params (no default) missing from the JSON file.
  5. Env vars    – parameter values bound to environment variables must use the
                  AZURE_ENV_* naming convention, except for explicitly allowed
                  names (for example, AZURE_LOCATION).

Usage:
  # Validate a specific pair
  python validate_bicep_params.py --bicep main.bicep --params main.parameters.json

  # Auto-discover all *.parameters.json files under infra/
  python validate_bicep_params.py --dir infra

  # CI mode – exit code 1 on any error
  python validate_bicep_params.py --dir infra --strict

Returns exit-code 0 when no errors are found, 1 when errors are found (in --strict mode).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Environment variables exempt from the AZURE_ENV_ naming convention.
_ENV_VAR_EXCEPTIONS = {"AZURE_LOCATION"}

# ---------------------------------------------------------------------------
# Bicep param parser
# ---------------------------------------------------------------------------

# Matches lines like:  param environmentName string
#                       param tags resourceInput<...>
#                       param gptDeploymentCapacity int = 150
# Ignores commented-out lines (// param ...).
# Captures the type token and the rest of the line so we can detect defaults.
_PARAM_RE = re.compile(
    r"^(?!//)[ \t]*param\s+(?P<name>[A-Za-z_]\w*)\s+(?P<type>\S+)(?P<rest>.*)",
    re.MULTILINE,
)


@dataclass
class BicepParam:
    name: str
    has_default: bool


def parse_bicep_params(bicep_path: Path) -> list[BicepParam]:
    """Extract all `param` declarations from a Bicep file."""
    text = bicep_path.read_text(encoding="utf-8-sig")
    params: list[BicepParam] = []
    for match in _PARAM_RE.finditer(text):
        name = match.group("name")
        param_type = match.group("type")
        rest = match.group("rest")
        # A param is optional if it has a default value (= ...) or is nullable (type ends with ?)
        has_default = "=" in rest or param_type.endswith("?")
        params.append(BicepParam(name=name, has_default=has_default))
    return params


# ---------------------------------------------------------------------------
# Parameters JSON parser
# ---------------------------------------------------------------------------


def parse_parameters_json(json_path: Path) -> list[str]:
    """Return the raw parameter key names (preserving whitespace) from a
    parameters JSON file.
    """
    text = json_path.read_text(encoding="utf-8-sig")
    # azd parameter files may include ${VAR} or ${VAR=default} placeholders inside
    # string values. These are valid JSON strings, but we sanitize them so that
    # json.loads remains resilient to azd-specific placeholders and any unusual
    # default formats.
    sanitized = re.sub(r'"\$\{[^}]+\}"', '"__placeholder__"', text)
    try:
        data = json.loads(sanitized)
    except json.JSONDecodeError:
        # Fallback: extract keys with regex for resilience.
        return _extract_keys_regex(text)
    return list(data.get("parameters", {}).keys())


def parse_parameters_env_vars(json_path: Path) -> dict[str, list[str]]:
    """Return a mapping of parameter name → list of azd env var names
    referenced in its value (e.g. ``${AZURE_ENV_NAME}``).
    """
    text = json_path.read_text(encoding="utf-8-sig")
    result: dict[str, list[str]] = {}
    params = {}

    # Parse the JSON to get the proper parameter structure.
    sanitized = re.sub(r'"\$\{([^}]+)\}"', r'"__azd_\1__"', text)
    try:
        data = json.loads(sanitized)
        params = data.get("parameters", {})
    except json.JSONDecodeError:
        pass

    # Walk each top-level parameter and scan its entire serialized value
    # for ${VAR} references from the original text.
    for param_name, param_obj in params.items():
        # Find the raw text block for this parameter in the original file
        # by scanning for all ${VAR} patterns in the original value section.
        raw_value = json.dumps(param_obj)
        # Restore original var references from the sanitized placeholders
        for m in re.finditer(r'__azd_([^_].*?)__', raw_value):
            var_ref = m.group(1)
            # var_ref may contain "=default", extract just the var name
            var_name = var_ref.split("=")[0].strip()
            if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', var_name):
                result.setdefault(param_name, []).append(var_name)

    return result


def _extract_keys_regex(text: str) -> list[str]:
    """Fallback key extraction via regex when JSON is non-standard."""
    # Matches the key inside "parameters": { "key": ... }
    keys: list[str] = []
    in_params = False
    for line in text.splitlines():
        if '"parameters"' in line:
            in_params = True
            continue
        if in_params:
            m = re.match(r'\s*"([^"]+)"\s*:', line)
            if m:
                keys.append(m.group(1))
    return keys


# ---------------------------------------------------------------------------
# Validation logic
# ---------------------------------------------------------------------------

@dataclass
class ValidationIssue:
    severity: str          # "ERROR" or "WARNING"
    param_file: str
    bicep_file: str
    param_name: str
    message: str


@dataclass
class ValidationResult:
    pair: str
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(i.severity == "ERROR" for i in self.issues)


def validate_pair(
    bicep_path: Path,
    params_path: Path,
) -> ValidationResult:
    """Validate a single (bicep, parameters.json) pair."""
    result = ValidationResult(
        pair=f"{params_path.name} -> {bicep_path.name}"
    )

    bicep_params = parse_bicep_params(bicep_path)
    bicep_names = {p.name for p in bicep_params}
    bicep_names_lower = {p.name.lower(): p.name for p in bicep_params}
    required_bicep = {p.name for p in bicep_params if not p.has_default}

    json_keys = parse_parameters_json(params_path)

    seen_json_keys: set[str] = set()

    for raw_key in json_keys:
        stripped = raw_key.strip()

        # 1. Whitespace check
        if raw_key != stripped:
            result.issues.append(ValidationIssue(
                severity="ERROR",
                param_file=str(params_path),
                bicep_file=str(bicep_path),
                param_name=repr(raw_key),
                message=(
                    f"Parameter name has leading/trailing whitespace. "
                    f"Raw key: {repr(raw_key)}, expected: {repr(stripped)}"
                ),
            ))

        # 2. Exact match check
        if stripped not in bicep_names:
            # 3. Case-insensitive near-match
            suggestion = bicep_names_lower.get(stripped.lower())
            if suggestion:
                result.issues.append(ValidationIssue(
                    severity="ERROR",
                    param_file=str(params_path),
                    bicep_file=str(bicep_path),
                    param_name=stripped,
                    message=(
                        f"Case mismatch: JSON has '{stripped}', "
                        f"Bicep declares '{suggestion}'."
                    ),
                ))
            else:
                result.issues.append(ValidationIssue(
                    severity="ERROR",
                    param_file=str(params_path),
                    bicep_file=str(bicep_path),
                    param_name=stripped,
                    message=(
                        f"Parameter '{stripped}' exists in JSON but has no "
                        f"matching param in the Bicep template."
                    ),
                ))
        seen_json_keys.add(stripped)

    # 4. Required Bicep params missing from JSON
    for req in sorted(required_bicep - seen_json_keys):
        result.issues.append(ValidationIssue(
            severity="WARNING",
            param_file=str(params_path),
            bicep_file=str(bicep_path),
            param_name=req,
            message=(
                f"Required Bicep param '{req}' (no default value) is not "
                f"supplied in the parameters file."
            ),
        ))

    # 5. Env var naming convention – all azd vars should start with AZURE_ENV_
    env_vars = parse_parameters_env_vars(params_path)
    for param_name, var_names in sorted(env_vars.items()):
        for var in var_names:
            if not var.startswith("AZURE_ENV_") and var not in _ENV_VAR_EXCEPTIONS:
                result.issues.append(ValidationIssue(
                    severity="WARNING",
                    param_file=str(params_path),
                    bicep_file=str(bicep_path),
                    param_name=param_name,
                    message=(
                        f"Env var '${{{var}}}' does not follow the "
                        f"AZURE_ENV_ naming convention."
                    ),
                ))

    return result


# ---------------------------------------------------------------------------
# Discovery – find (bicep, params) pairs automatically
# ---------------------------------------------------------------------------

def discover_pairs(infra_dir: Path) -> list[tuple[Path, Path]]:
    """For each *.parameters.json, find the matching Bicep file.

    Naming convention: a file like ``main.waf.parameters.json`` is a
    variant of ``main.parameters.json`` — the user copies its contents
    into ``main.parameters.json`` before running ``azd up``.  Both
    files should therefore be validated against ``main.bicep``.

    Resolution order:
      1. Exact stem match  (e.g. ``foo.parameters.json`` → ``foo.bicep``).
      2. Base-stem match   (e.g. ``main.waf.parameters.json`` → ``main.bicep``).
    """
    pairs: list[tuple[Path, Path]] = []
    for pf in sorted(infra_dir.rglob("*.parameters.json")):
        stem = pf.name.replace(".parameters.json", "")
        bicep_candidate = pf.parent / f"{stem}.bicep"
        if bicep_candidate.exists():
            pairs.append((bicep_candidate, pf))
        else:
            # Try the base stem (first segment before the first dot).
            base_stem = stem.split(".")[0]
            base_candidate = pf.parent / f"{base_stem}.bicep"
            if base_candidate.exists():
                pairs.append((base_candidate, pf))
            else:
                print(f"  [SKIP] No matching Bicep file for {pf.name}")
    return pairs


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# HTML email report
# ---------------------------------------------------------------------------

def _html_escape(text: str) -> str:
    """Escape HTML special characters."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def generate_html_report(
    results: list[ValidationResult],
    *,
    accelerator_name: str = "",
    run_url: str = "",
    scan_dir: str = "",
) -> str:
    """Build a structured HTML email body from validation results."""
    total_errors = sum(
        1 for r in results for i in r.issues if i.severity == "ERROR"
    )
    total_warnings = sum(
        1 for r in results for i in r.issues if i.severity == "WARNING"
    )
    has_errors = total_errors > 0
    overall_status = "Issues Detected" if has_errors else "Passed"
    status_color = "#D32F2F" if has_errors else "#2E7D32"
    status_bg = "#FFEBEE" if has_errors else "#E8F5E9"
    status_icon = "&#10060;" if has_errors else "&#9989;"

    parts: list[str] = []

    # --- Document wrapper (Outlook-compatible, no gradient/border-radius/box-shadow) ---
    parts.append(
        '<!DOCTYPE html><html><head><meta charset="utf-8"></head>'
        '<body style="margin:0;padding:0;font-family:Segoe UI,Helvetica,Arial,sans-serif;'
        'background-color:#ffffff;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"'
        ' style="background-color:#ffffff;">'
        '<tr><td align="center" style="padding:0;">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"'
        ' style="max-width:680px;background-color:#ffffff;">'
    )

    # --- Header banner (solid color, Outlook-safe) ---
    parts.append(
        f'<tr><td style="background-color:#0078D4;padding:20px 24px;color:#ffffff;">'
        f'<h1 style="margin:0 0 4px 0;font-size:20px;font-weight:600;color:#ffffff;">'
        f'Bicep Parameter Validation Report</h1>'
        f'<p style="margin:0;font-size:13px;color:#ffffff;">'
        f'{_html_escape(accelerator_name) if accelerator_name else "Accelerator"}'
        f' &mdash; Automated Check</p>'
        f'</td></tr>'
    )

    # --- Summary card ---
    parts.append(
        f'<tr><td style="padding:16px 24px 12px 24px;">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"'
        f' style="background-color:{status_bg};border-left:4px solid {status_color};">'
        f'<tr><td style="padding:12px 16px;">'
        f'<span style="font-size:16px;font-weight:600;color:{status_color};">'
        f'{status_icon} Overall Status: {overall_status}</span>'
        f'</td></tr>'
        f'<tr><td style="padding:4px 16px 12px 16px;">'
        f'<table role="presentation" cellpadding="0" cellspacing="0"><tr>'
    )
    # Accelerator name pill
    if accelerator_name:
        parts.append(
            f'<td style="padding-right:20px;vertical-align:top;">'
            f'<span style="font-size:11px;color:#666;">Accelerator</span><br>'
            f'<strong style="font-size:13px;">{_html_escape(accelerator_name)}'
            f'</strong></td>'
        )
    # Scan directory pill
    if scan_dir:
        parts.append(
            f'<td style="padding-right:20px;vertical-align:top;">'
            f'<span style="font-size:11px;color:#666;">Scan Directory</span><br>'
            f'<strong style="font-size:13px;">{_html_escape(scan_dir)}/</strong>'
            f'</td>'
        )
    # Error count pill
    err_pill_color = "#D32F2F" if total_errors > 0 else "#2E7D32"
    parts.append(
        f'<td style="padding-right:20px;vertical-align:top;">'
        f'<span style="font-size:11px;color:#666;">Errors</span><br>'
        f'<strong style="font-size:13px;color:{err_pill_color};">'
        f'{total_errors}</strong></td>'
    )
    # Warning count pill
    warn_pill_color = "#F57C00" if total_warnings > 0 else "#2E7D32"
    parts.append(
        f'<td style="vertical-align:top;">'
        f'<span style="font-size:11px;color:#666;">Warnings</span><br>'
        f'<strong style="font-size:13px;color:{warn_pill_color};">'
        f'{total_warnings}</strong></td>'
    )
    parts.append("</tr></table></td></tr></table></td></tr>")

    # --- Per-pair detail sections ---
    parts.append('<tr><td style="padding:8px 24px 0 24px;">')
    for r in results:
        errors = [i for i in r.issues if i.severity == "ERROR"]
        warnings = [i for i in r.issues if i.severity == "WARNING"]

        if not r.issues:
            badge = (
                '<span style="display:inline-block;padding:2px 8px;'
                'font-size:11px;font-weight:700;'
                'color:#2E7D32;background-color:#E8F5E9;">PASS</span>'
            )
        elif errors:
            badge = (
                '<span style="display:inline-block;padding:2px 8px;'
                'font-size:11px;font-weight:700;'
                'color:#D32F2F;background-color:#FFEBEE;">FAIL</span>'
            )
        else:
            badge = (
                '<span style="display:inline-block;padding:2px 8px;'
                'font-size:11px;font-weight:700;'
                'color:#F57C00;background-color:#FFF3E0;">WARN</span>'
            )

        parts.append(
            f'<table role="presentation" width="100%" cellpadding="0"'
            f' cellspacing="0" style="margin-bottom:12px;border:1px solid #e0e0e0;">'
            f'<tr><td style="background-color:#fafafa;padding:10px 12px;'
            f'border-bottom:1px solid #e0e0e0;">'
            f'{badge} '
            f'<strong style="font-size:13px;">'
            f'{_html_escape(r.pair)}</strong>'
            f'<span style="float:right;font-size:11px;color:#888;">'
            f'{len(errors)} error(s), {len(warnings)} warning(s)</span>'
            f'</td></tr>'
        )

        if r.issues:
            # --- Errors section ---
            if errors:
                parts.append(
                    '<tr><td style="padding:8px 12px 4px 12px;">'
                    '<strong style="font-size:12px;color:#D32F2F;">'
                    '&#9679; Errors</strong></td></tr>'
                    '<tr><td style="padding:0 12px;">'
                    '<table role="presentation" width="100%" cellpadding="0"'
                    ' cellspacing="0" style="font-size:12px;border:1px solid #f5c6cb;">'
                    '<tr style="background-color:#FFEBEE;">'
                    '<th style="text-align:left;padding:6px 10px;'
                    'border-bottom:1px solid #f5c6cb;width:180px;">Parameter</th>'
                    '<th style="text-align:left;padding:6px 10px;'
                    'border-bottom:1px solid #f5c6cb;">Details</th></tr>'
                )
                for idx, issue in enumerate(errors):
                    bg = "#ffffff" if idx % 2 == 0 else "#fff5f5"
                    parts.append(
                        f'<tr style="background-color:{bg};">'
                        f'<td style="padding:5px 10px;border-bottom:1px solid #f5c6cb;'
                        f'vertical-align:top;font-family:Consolas,monospace;'
                        f'font-size:11px;word-break:break-all;">'
                        f'{_html_escape(issue.param_name)}</td>'
                        f'<td style="padding:5px 10px;border-bottom:1px solid #f5c6cb;'
                        f'vertical-align:top;">{_html_escape(issue.message)}</td>'
                        f'</tr>'
                    )
                parts.append("</table></td></tr>")

            # --- Warnings section ---
            if warnings:
                parts.append(
                    '<tr><td style="padding:8px 12px 4px 12px;">'
                    '<strong style="font-size:12px;color:#F57C00;">'
                    '&#9679; Warnings</strong></td></tr>'
                    '<tr><td style="padding:0 12px 8px 12px;">'
                    '<table role="presentation" width="100%" cellpadding="0"'
                    ' cellspacing="0" style="font-size:12px;border:1px solid #ffe0b2;">'
                    '<tr style="background-color:#FFF3E0;">'
                    '<th style="text-align:left;padding:6px 10px;'
                    'border-bottom:1px solid #ffe0b2;width:180px;">Parameter</th>'
                    '<th style="text-align:left;padding:6px 10px;'
                    'border-bottom:1px solid #ffe0b2;">Details</th></tr>'
                )
                for idx, issue in enumerate(warnings):
                    bg = "#ffffff" if idx % 2 == 0 else "#fffaf0"
                    parts.append(
                        f'<tr style="background-color:{bg};">'
                        f'<td style="padding:5px 10px;border-bottom:1px solid #ffe0b2;'
                        f'vertical-align:top;font-family:Consolas,monospace;'
                        f'font-size:11px;word-break:break-all;">'
                        f'{_html_escape(issue.param_name)}</td>'
                        f'<td style="padding:5px 10px;border-bottom:1px solid #ffe0b2;'
                        f'vertical-align:top;">{_html_escape(issue.message)}</td>'
                        f'</tr>'
                    )
                parts.append("</table></td></tr>")
        else:
            parts.append(
                '<tr><td style="padding:10px 12px;color:#2E7D32;'
                'font-size:12px;">All parameters validated successfully.'
                '</td></tr>'
            )

        parts.append("</table>")

    parts.append("</td></tr>")

    # --- Footer with run URL ---
    footer_parts: list[str] = []
    if run_url:
        footer_parts.append(
            f'<a href="{_html_escape(run_url)}" style="display:inline-block;'
            f'padding:8px 16px;background-color:#0078D4;color:#ffffff;'
            f'text-decoration:none;font-size:12px;'
            f'font-weight:600;">View Workflow Run</a>'
        )
    if has_errors:
        footer_parts.append(
            '<p style="margin:10px 0 0 0;font-size:12px;color:#555;">'
            'Please fix the parameter mapping issues at your earliest convenience.</p>'
        )
    footer_parts.append(
        '<p style="margin:10px 0 0 0;font-size:12px;color:#999;">'
        'Best regards,<br>Your Automation Team</p>'
    )
    parts.append(
        f'<tr><td style="padding:14px 24px 20px 24px;border-top:1px solid #e0e0e0;">'
        f'{"".join(footer_parts)}</td></tr>'
    )

    # --- Close wrapper ---
    parts.append("</table></td></tr></table></body></html>")
    return "".join(parts)


# ---------------------------------------------------------------------------
# Console reporting
# ---------------------------------------------------------------------------

_COLORS = {
    "ERROR": "\033[91m",    # red
    "WARNING": "\033[93m",  # yellow
    "OK": "\033[92m",       # green
    "RESET": "\033[0m",
}


def print_report(results: list[ValidationResult], *, use_color: bool = True) -> None:
    c = _COLORS if use_color else {k: "" for k in _COLORS}
    total_errors = 0
    total_warnings = 0

    for r in results:
        errors = [i for i in r.issues if i.severity == "ERROR"]
        warnings = [i for i in r.issues if i.severity == "WARNING"]
        total_errors += len(errors)
        total_warnings += len(warnings)

        if not r.issues:
            print(f"\n{c['OK']}[PASS]{c['RESET']} {r.pair}")
        elif errors:
            print(f"\n{c['ERROR']}[FAIL]{c['RESET']} {r.pair}")
        else:
            print(f"\n{c['WARNING']}[WARN]{c['RESET']} {r.pair}")

        for issue in r.issues:
            tag = (
                f"{c['ERROR']}ERROR{c['RESET']}"
                if issue.severity == "ERROR"
                else f"{c['WARNING']}WARN {c['RESET']}"
            )
            print(f"  {tag}  {issue.param_name}: {issue.message}")

    print(f"\n{'=' * 60}")
    print(f"Total: {total_errors} error(s), {total_warnings} warning(s)")
    if total_errors == 0:
        print(f"{c['OK']}All parameter mappings are valid.{c['RESET']}")
    else:
        print(f"{c['ERROR']}Parameter mapping issues detected!{c['RESET']}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate Bicep ↔ parameters.json parameter mappings.",
    )
    parser.add_argument(
        "--bicep",
        type=Path,
        help="Path to a specific Bicep template.",
    )
    parser.add_argument(
        "--params",
        type=Path,
        help="Path to a specific parameters JSON file.",
    )
    parser.add_argument(
        "--dir",
        type=Path,
        help="Directory to scan for *.parameters.json files (auto-discovers pairs).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Exit with code 1 if any errors are found.",
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output (useful for CI logs).",
    )
    parser.add_argument(
        "--json-output",
        type=Path,
        help="Write results as JSON to the given file path.",
    )
    parser.add_argument(
        "--html-output",
        type=Path,
        help="Write a structured HTML email report to the given file path.",
    )
    parser.add_argument(
        "--accelerator-name",
        type=str,
        default="",
        help="Accelerator display name for the HTML report header.",
    )
    parser.add_argument(
        "--run-url",
        type=str,
        default="",
        help="Workflow run URL to include in the HTML report footer.",
    )
    args = parser.parse_args()

    results: list[ValidationResult] = []

    if args.bicep and args.params:
        results.append(validate_pair(args.bicep, args.params))
    elif args.dir:
        pairs = discover_pairs(args.dir)
        if not pairs:
            print(f"No (bicep, parameters.json) pairs found under {args.dir}")
            return 0
        for bicep_path, params_path in pairs:
            results.append(validate_pair(bicep_path, params_path))
    else:
        parser.error("Provide either --bicep/--params or --dir.")

    print_report(results, use_color=not args.no_color)

    # Optional JSON output for CI artifact consumption
    if args.json_output:
        json_data = []
        for r in results:
            for issue in r.issues:
                json_data.append({
                    "severity": issue.severity,
                    "paramFile": issue.param_file,
                    "bicepFile": issue.bicep_file,
                    "paramName": issue.param_name,
                    "message": issue.message,
                })
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(
            json.dumps(json_data, indent=2), encoding="utf-8"
        )
        print(f"\nJSON report written to {args.json_output}")

    # Optional HTML email report
    if args.html_output:
        scan_dir = str(args.dir) if args.dir else ""
        html = generate_html_report(
            results,
            accelerator_name=args.accelerator_name,
            run_url=args.run_url,
            scan_dir=scan_dir,
        )
        args.html_output.parent.mkdir(parents=True, exist_ok=True)
        args.html_output.write_text(html, encoding="utf-8")
        print(f"HTML report written to {args.html_output}")

    has_errors = any(r.has_errors for r in results)
    return 1 if args.strict and has_errors else 0


if __name__ == "__main__":
    sys.exit(main())
