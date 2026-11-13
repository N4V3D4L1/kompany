#!/usr/bin/env bash
# One-time setup on a production host. Review before running. Installs only Python packages from PyPI
# and the Kokoro model files from the official kokoro-onnx GitHub release (checksums verified).
set -euo pipefail
cd "$(dirname "$0")/.."
python3 -m pip install --user pillow numpy jinja2 kokoro-onnx==0.6.1
M=../.models/kokoro; mkdir -p "$M"
for f in kokoro-v1.0.int8.onnx voices-v1.0.bin; do
  [ -f "$M/$f" ] || curl -fsSL -o "$M/$f" "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/$f"
done
cd "$M" && sha256sum -c - <<'SUMS'
6e742170d309016e5891a994e1ce1559c702a2ccd0075e67ef7157974f6406cb  kokoro-v1.0.int8.onnx
bca610b8308e8d99f32e6fe4197e7ec01679264efed0cac9140fe9c29f1fbf7d  voices-v1.0.bin
SUMS
echo "Now set a dashboard password: python3 -m n4v3d_media.dashboard.app --set-password"
