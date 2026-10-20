#!/usr/bin/env bash
# Offline/static recovery helper. It never executes the EXE or setup installer.
set -uo pipefail
if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
  echo "Usage: $0 /path/asistan.exe /path/Asistan-setup.exe [uninstall.exe]"
  exit 2
fi
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_EXE="$(realpath "$1")" || exit 2
SETUP_EXE="$(realpath "$2")" || exit 2
UNINSTALL_EXE=""
if [ "$#" -eq 3 ]; then UNINSTALL_EXE="$(realpath "$3")" || exit 2; fi
OUT="$(pwd)/asistan_linux_kurtarma"
mkdir -p "$OUT"
for f in "$APP_EXE" "$SETUP_EXE"; do
  [ -r "$f" ] || { echo "Cannot read: $f" >&2; exit 2; }
done
if [ -n "$UNINSTALL_EXE" ] && [ ! -r "$UNINSTALL_EXE" ]; then echo "Cannot read uninstaller: $UNINSTALL_EXE" >&2; exit 2; fi
{
  echo "Asistan static recovery"
  date -Is 2>/dev/null || date
  echo
  for f in "$APP_EXE" "$SETUP_EXE" "$UNINSTALL_EXE"; do
    [ -n "$f" ] || continue
    sha256sum "$f" 2>/dev/null || shasum -a 256 "$f"
    file "$f" 2>/dev/null || true
    echo
  done
} > "$OUT/file_fingerprints.txt"

if python3 -c 'import brotli' >/dev/null 2>&1; then
  python3 "$ROOT/tools/recover_asistan_frontend_v4.py" "$APP_EXE" --output "$OUT/recovered_frontend" > "$OUT/frontend_extract.log" 2>&1
  printf 'frontend_exit_code=%s\n' "$?" >> "$OUT/exit_codes.txt"
  cat "$OUT/frontend_extract.log"
else
  echo "Missing Python brotli module. Debian/Ubuntu: sudo apt install python3-brotli" | tee "$OUT/frontend_extract.log"
fi

python3 "$ROOT/tools/extract_asistan_pe_resources.py" "$APP_EXE" --output "$OUT/recovered_pe_resources" > "$OUT/pe_extract.log" 2>&1
printf 'pe_exit_code=%s\n' "$?" >> "$OUT/exit_codes.txt"
cat "$OUT/pe_extract.log"

extract_nsis() {
  label="$1"; exe="$2"; dest="$3"
  mkdir -p "$dest"
  if command -v 7z >/dev/null 2>&1; then
    echo "Static NSIS analysis: $label"
    7z l -slt "$exe" > "$dest/7z_listing.txt" 2> "$dest/7z_listing.err"
    printf '%s\n' "$?" > "$dest/7z_listing_exit_code.txt"
    7z t "$exe" > "$dest/7z_test.log" 2>&1
    printf '%s\n' "$?" > "$dest/7z_test_exit_code.txt"
    mkdir -p "$dest/files"
    7z x -y "$exe" "-o$dest/files" > "$dest/7z_extract.log" 2>&1
    printf '%s\n' "$?" > "$dest/7z_extract_exit_code.txt"
    cat "$dest/7z_extract.log"
    find "$dest/files" -type f -printf '%P\t%s bytes\n' 2>/dev/null | sort > "$dest/extracted_file_list.tsv" || find "$dest/files" -type f -print | sort > "$dest/extracted_file_list.tsv"
    (cd "$dest/files" && find . -type f -print0 | sort -z | xargs -0 -r sha256sum) > "$dest/extracted_sha256.txt"
  else
    cat > "$dest/7z_missing.txt" <<'MSG'
7z is not installed, so NSIS extraction was skipped.
Try: sudo apt update && sudo apt install 7zip
On older Ubuntu releases the package may be p7zip-full.
Re-run this script after installing it.
MSG
    cat "$dest/7z_missing.txt"
  fi
  if command -v strings >/dev/null 2>&1; then
    strings -a -n 5 "$exe" > "$dest/strings_ascii.txt" 2>&1 || true
    strings -el -n 5 "$exe" > "$dest/strings_utf16le.txt" 2>&1 || true
  fi
}
extract_nsis "setup" "$SETUP_EXE" "$OUT/setup_nsis"
if [ -n "$UNINSTALL_EXE" ]; then extract_nsis "uninstaller" "$UNINSTALL_EXE" "$OUT/uninstaller_nsis"; fi

if [ -d "$OUT/recovered_frontend" ] && command -v node >/dev/null 2>&1; then
  : > "$OUT/recovered_frontend/node_check.txt"
  js_ok=0; js_bad=0
  while IFS= read -r -d '' js; do
    if node --check "$js" >> "$OUT/recovered_frontend/node_check.txt" 2>&1; then js_ok=$((js_ok+1)); else js_bad=$((js_bad+1)); fi
  done < <(find "$OUT/recovered_frontend" -type f -name '*.js' -print0)
  printf 'js_ok=%s\njs_bad=%s\n' "$js_ok" "$js_bad" | tee -a "$OUT/recovered_frontend/node_check.txt"
fi
echo "Done. Results: $OUT"
echo "The EXE and setup installer were not run."
