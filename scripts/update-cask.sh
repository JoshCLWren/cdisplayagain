#!/usr/bin/env bash
# Generate the Homebrew cask for a published release.
#
# Usage: scripts/update-cask.sh <tag> [output-path]
#
# Reads the checksums the release workflow published, so the cask can never
# disagree with the assets people actually download.
set -euo pipefail

if [[ $# -lt 1 || $# -gt 2 ]]; then
    echo "Usage: $0 <tag> [output-path]" >&2
    exit 2
fi

tag=$1
version=${tag#v}
output=${2:-Casks/cdisplayagain.rb}
repo=${CDISPLAYAGAIN_REPO:-JoshCLWren/cdisplayagain}

if ! command -v gh >/dev/null 2>&1; then
    echo "ERROR: the gh CLI is required." >&2
    exit 1
fi

checksums=$(gh release view "$tag" --repo "$repo" --json assets \
    --jq '.assets[] | select(.name == "SHA256SUMS") | .url')
if [[ -z "$checksums" ]]; then
    echo "ERROR: release $tag has no SHA256SUMS asset." >&2
    exit 1
fi

sums=$(gh release download "$tag" --repo "$repo" --pattern SHA256SUMS --output - 2>/dev/null)

lookup() {
    local suffix=$1 line
    line=$(grep -E "cdisplayagain-${version}-macos-${suffix}\.zip\$" <<<"$sums" || true)
    if [[ -z "$line" ]]; then
        echo "ERROR: no macOS ${suffix} asset in $tag checksums." >&2
        exit 1
    fi
    awk '{print $1}' <<<"$line"
}

arm_sha=$(lookup arm64)

mkdir -p -- "$(dirname -- "$output")"
cat > "$output" <<EOF
cask "cdisplayagain" do
  version "${version}"
  sha256 "${arm_sha}"

  url "https://github.com/${repo}/releases/download/v#{version}/cdisplayagain-#{version}-macos-arm64.zip",
      verified: "github.com/${repo}/"
  name "cdisplayagain"
  desc "Minimalist remake of the CDisplay sequential comic viewer"
  homepage "https://github.com/${repo}"

  # Only Apple silicon builds are published; Intel users build from source.
  depends_on arch: :arm64
  depends_on macos: ">= :big_sur"

  # package-macos.sh zips a versioned parent directory holding the bundle
  # alongside install.sh and the license, so the app is one level down.
  app "cdisplayagain-#{version}-macos-arm64/cdisplayagain.app"

  # The app is ad-hoc signed rather than notarized, so Gatekeeper blocks the
  # quarantined copy Homebrew downloads until the flag is cleared.
  postflight do
    system_command "/usr/bin/xattr",
                   args: ["-dr", "com.apple.quarantine", "#{appdir}/cdisplayagain.app"],
                   sudo: false
  end

  zap trash: [
    "~/Library/Logs/cdisplayagain",
    "~/Library/Saved Application State/io.github.joshclwren.cdisplayagain.savedState",
  ]
end
EOF

echo "Wrote $output for $tag"
