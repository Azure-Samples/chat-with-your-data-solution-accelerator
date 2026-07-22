#!/usr/bin/env bash
#
# In-house automated release script.
#
# Replaces third-party release tooling (previously the codfish
# semantic-release-action, then semantic-release). Uses only git, bash, and curl
# against the GitHub REST API, so there are NO external libraries, npm packages,
# or third-party GitHub Actions involved in the release logic.
#
# Behaviour (feature parity with the previous codfish/semantic-release setup):
#   * Analyses Conventional Commit subjects since the last vX.Y.Z tag.
#   * Bump rules: breaking (! or "BREAKING CHANGE") -> major, feat -> minor,
#     fix/perf/revert -> patch. Any other type alone does NOT trigger a release.
#   * First ever release is 1.0.0.
#   * Release notes group every commit type into sections (Features, Bug Fixes,
#     Performance Improvements, Reverts, Other Updates) and include a compare
#     link header, autolinked PR/issue references, and autolinked commit SHAs.
#   * Tags are formatted as v${version}. The GitHub Release creates the tag.
#   * Each released PR/issue gets a "released" label and an inclusion comment.
#   * Emits step outputs (new-release-published, release-version) for the job.
#
# Required environment:
#   GITHUB_TOKEN       - token with contents:write, issues:write, pull-requests:write.
#   GITHUB_REPOSITORY  - "owner/repo" (provided automatically by Actions).
#
set -euo pipefail

REPO="${GITHUB_REPOSITORY:?GITHUB_REPOSITORY not set}"
TOKEN="${GITHUB_TOKEN:?GITHUB_TOKEN not set}"
API_URL="${GITHUB_API_URL:-https://api.github.com}"
SERVER_URL="${GITHUB_SERVER_URL:-https://github.com}"
REPO_URL="${SERVER_URL}/${REPO}"
SHA="$(git rev-parse HEAD)"

# Escape a string so it is safe to embed inside a JSON string literal.
json_escape() {
  local s="$1"
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  s="${s//$'\r'/}"
  s="${s//$'\t'/\\t}"
  s="${s//$'\n'/\\n}"
  printf '%s' "$s"
}

# Write a key/value pair to the GitHub Actions step output, when available.
set_output() {
  if [[ -n "${GITHUB_OUTPUT:-}" ]]; then
    printf '%s=%s\n' "$1" "$2" >> "$GITHUB_OUTPUT"
  fi
}

# --- Determine the last released version tag (vMAJOR.MINOR.PATCH) ---
last_tag="$(git tag -l 'v[0-9]*.[0-9]*.[0-9]*' --sort=-v:refname | head -n1 || true)"

if [[ -n "$last_tag" ]]; then
  echo "Last release tag: $last_tag"
  range="${last_tag}..HEAD"
  base_version="${last_tag#v}"
else
  echo "No previous release tag found; this would be the first release."
  range=""
  base_version=""
fi

# --- Collect commits in range ---
if [[ -n "$range" ]]; then
  raw="$(git log "$range" --no-merges --format='%h%x1f%H%x1f%s%x1f%b%x1e')"
else
  raw="$(git log --no-merges --format='%h%x1f%H%x1f%s%x1f%b%x1e')"
fi

# bump: 0 none, 1 patch, 2 minor, 3 major
bump=0
feat_lines=()
fix_lines=()
perf_lines=()
revert_lines=()
other_lines=()
breaking_lines=()
declare -A referenced_prs=()

type_regex='^([a-zA-Z]+)(\(([^)]+)\))?(!)?:[[:space:]]*(.*)$'

while IFS= read -r -d $'\x1e' record; do
  # Skip empty records.
  if [[ -z "${record//[$'\n\t ']/}" ]]; then
    continue
  fi

  short_sha="${record%%$'\x1f'*}"
  short_sha="${short_sha//[$'\n\r\t ']/}"
  rest="${record#*$'\x1f'}"
  full_sha="${rest%%$'\x1f'*}"
  full_sha="${full_sha//[$'\n\r\t ']/}"
  rest="${rest#*$'\x1f'}"
  subject="${rest%%$'\x1f'*}"
  body="${rest#*$'\x1f'}"

  if [[ ! "$subject" =~ $type_regex ]]; then
    continue
  fi

  type="$(printf '%s' "${BASH_REMATCH[1]}" | tr '[:upper:]' '[:lower:]')"
  scope="${BASH_REMATCH[3]}"
  bang="${BASH_REMATCH[4]}"
  desc="${BASH_REMATCH[5]}"

  breaking=0
  if [[ -n "$bang" ]] || printf '%s' "$body" | grep -qE 'BREAKING[ -]CHANGE'; then
    breaking=1
  fi

  # Autolink "(#123)" pull request / issue references in the description.
  linked_desc="$(printf '%s' "$desc" | sed -E "s@\(#([0-9]+)\)@([#\1](${REPO_URL}/issues/\1))@g")"
  commit_link="([${short_sha}](${REPO_URL}/commit/${full_sha}))"

  if [[ -n "$scope" ]]; then
    entry="* **${scope}:** ${linked_desc} ${commit_link}"
  else
    entry="* ${linked_desc} ${commit_link}"
  fi

  # Record PR/issue numbers referenced by this commit for later commenting.
  while read -r prnum; do
    [[ -n "$prnum" ]] && referenced_prs["$prnum"]=1
  done < <(printf '%s' "$subject" | grep -oE '#[0-9]+' | tr -d '#')

  if [[ $breaking -eq 1 ]]; then
    breaking_lines+=("$entry")
    if (( bump < 3 )); then bump=3; fi
  fi

  case "$type" in
    feat)   feat_lines+=("$entry");   if (( bump < 2 )); then bump=2; fi ;;
    fix)    fix_lines+=("$entry");    if (( bump < 1 )); then bump=1; fi ;;
    perf)   perf_lines+=("$entry");   if (( bump < 1 )); then bump=1; fi ;;
    revert) revert_lines+=("$entry"); if (( bump < 1 )); then bump=1; fi ;;
    docs|style|chore|refactor|test|build|ci) other_lines+=("$entry") ;;
    *) : ;;
  esac
done <<< "$raw"

# --- Decide whether a release is warranted ---
if (( bump == 0 )); then
  echo "No releasable changes (feat/fix/perf/revert/breaking) found. No release created."
  set_output "new-release-published" "false"
  exit 0
fi

# --- Compute the next version ---
if [[ -z "$base_version" ]]; then
  next="1.0.0"
else
  IFS='.' read -r MAJOR MINOR PATCH <<< "$base_version"
  case $bump in
    3) MAJOR=$((MAJOR + 1)); MINOR=0; PATCH=0 ;;
    2) MINOR=$((MINOR + 1)); PATCH=0 ;;
    1) PATCH=$((PATCH + 1)) ;;
  esac
  next="${MAJOR}.${MINOR}.${PATCH}"
fi
tag="v${next}"
echo "Next version: $tag"

# --- Build release notes ---
append_section() {
  local title="$1"
  local -n arr="$2"
  if (( ${#arr[@]} > 0 )); then
    notes+="### ${title}"$'\n\n'
    local line
    for line in "${arr[@]}"; do
      notes+="${line}"$'\n'
    done
    notes+=$'\n'
  fi
}

release_date="$(date -u +%Y-%m-%d)"
if [[ -n "$last_tag" ]]; then
  notes="## [${next}](${REPO_URL}/compare/${last_tag}...${tag}) (${release_date})"$'\n\n'
else
  notes="## ${next} (${release_date})"$'\n\n'
fi
append_section "⚠ BREAKING CHANGES" breaking_lines
append_section "Features" feat_lines
append_section "Bug Fixes" fix_lines
append_section "Performance Improvements" perf_lines
append_section "Reverts" revert_lines
append_section "Other Updates" other_lines

echo "----- Release notes -----"
printf '%s\n' "$notes"
echo "-------------------------"

# --- Dry-run: report what would happen without publishing anything ---
if [[ "${DRY_RUN:-false}" == "true" ]]; then
  echo "DRY RUN: would create release ${tag} at ${SHA}."
  if (( ${#referenced_prs[@]} > 0 )); then
    echo "DRY RUN: would add the 'released' label and an inclusion comment to: ${!referenced_prs[*]}"
  fi
  set_output "new-release-published" "true"
  set_output "release-version" "${next}"
  exit 0
fi

# --- Create the GitHub Release (also creates the tag at SHA) ---
payload=$(printf '{"tag_name":"%s","target_commitish":"%s","name":"%s","body":"%s","draft":false,"prerelease":false}' \
  "$tag" "$SHA" "$tag" "$(json_escape "$notes")")

resp_file="$(mktemp)"
http_code=$(curl -sS -o "$resp_file" -w '%{http_code}' -X POST \
  -H "Authorization: Bearer ${TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "${API_URL}/repos/${REPO}/releases" \
  -d "$payload")

if [[ "$http_code" != "201" ]]; then
  echo "Failed to create release (HTTP ${http_code}):"
  cat "$resp_file"
  rm -f "$resp_file"
  exit 1
fi

# The release page URL is the first "html_url" in the response body.
release_url="$(grep -oE '"html_url"[[:space:]]*:[[:space:]]*"[^"]*"' "$resp_file" | head -n1 | sed -E 's/.*"html_url"[[:space:]]*:[[:space:]]*"([^"]*)".*/\1/')"
rm -f "$resp_file"
echo "Successfully created release ${tag} (${release_url})."

set_output "new-release-published" "true"
set_output "release-version" "${next}"

# --- Comment on and label every released PR/issue (matches @semantic-release/github) ---
comment_body=":tada: This PR is included in version ${next} :tada:"$'\n\n'"The release is available on [GitHub release](${release_url})"
comment_json="$(json_escape "$comment_body")"

for pr in "${!referenced_prs[@]}"; do
  echo "Annotating #${pr}..."

  # Inclusion comment.
  c_code=$(curl -sS -o /dev/null -w '%{http_code}' -X POST \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "${API_URL}/repos/${REPO}/issues/${pr}/comments" \
    -d "{\"body\":\"${comment_json}\"}") || c_code="000"
  if [[ "$c_code" != "201" ]]; then
    echo "  war: could not comment on #${pr} (HTTP ${c_code})"
  fi

  # "released" label.
  l_code=$(curl -sS -o /dev/null -w '%{http_code}' -X POST \
    -H "Authorization: Bearer ${TOKEN}" \
    -H "Accept: application/vnd.github+json" \
    -H "X-GitHub-Api-Version: 2022-11-28" \
    "${API_URL}/repos/${REPO}/issues/${pr}/labels" \
    -d '{"labels":["released"]}') || l_code="000"
  if [[ "$l_code" != "200" ]]; then
    echo "  war: could not label #${pr} (HTTP ${l_code})"
  fi
done

echo "Release ${tag} complete."
