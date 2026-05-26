#!/usr/bin/env python3
"""
BiteRec – one-command launcher
Usage:
  python run.py                                  # uses CSV in same folder
  python run.py /path/to/openfoodfacts.csv       # custom path
  python run.py /path/to/openfoodfacts.csv 8000  # custom port
"""
import sys, os, subprocess

DEFAULT_CSV_NAMES = [
    "openfoodfacts_short_30MB.csv",
    "en.openfoodfacts.org.products.csv",
    "openfoodfacts.csv",
]

def main():
    csv_path = None
    port = "8000"

    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    for arg in args:
        if arg.isdigit():
            port = arg
        elif os.path.isfile(arg):
            csv_path = arg
        else:
            print(f"❌  File not found: {arg}")
            sys.exit(1)

    # Auto-detect CSV in same directory
    if not csv_path:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        for name in DEFAULT_CSV_NAMES:
            candidate = os.path.join(script_dir, name)
            if os.path.isfile(candidate):
                csv_path = candidate
                break
        if os.path.isfile("../../Context files/openfoodfacts_short_30MB.csv"):
            csv_path = "../../Context files/openfoodfacts_short_30MB.csv"

    if not csv_path:
        print("❌  CSV not found.")
        print("   Supported filenames (place next to run.py):")
        for n in DEFAULT_CSV_NAMES:
            print(f"   - {n}")
        print("\n   Or pass the path explicitly:")
        print("   python run.py C:\\path\\to\\en.openfoodfacts.org.products.csv")
        sys.exit(1)

    os.environ["BITREC_CSV"] = os.path.abspath(csv_path)
    file_mb = os.path.getsize(csv_path) / 1024 / 1024
    print(f"✅  Using CSV: {csv_path}  ({file_mb:.0f} MB)")

    if file_mb > 500:
        print(f"ℹ️   Large file detected — loading up to 50 000 products.")
        print(f"    First start may take 1–3 minutes.")

    print(f"🚀  Starting BiteRec at http://localhost:{port}")
    print(f"    Press Ctrl+C to stop.\n")

    app_dir = os.path.dirname(os.path.abspath(__file__))
    subprocess.run(
        [sys.executable, "-m", "uvicorn", "app:app",
         "--host", "0.0.0.0", "--port", port],
        cwd=app_dir,
    )

if __name__ == "__main__":
    main()
