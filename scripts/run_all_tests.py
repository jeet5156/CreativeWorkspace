import os
import sys
import subprocess
from pathlib import Path

repo_root = Path(__file__).resolve().parent.parent

def main():
    tests_dir = repo_root / "tests"
    test_files = sorted([f for f in tests_dir.glob("test_*.py")])

    print(f"Discovered {len(test_files)} test modules in {tests_dir}")
    print("==================================================================")

    passed_count = 0
    failed_files = []

    for idx, tf in enumerate(test_files, 1):
        rel_path = tf.relative_to(repo_root)
        print(f"[{idx}/{len(test_files)}] Running {tf.name}...", end=" ", flush=True)

        cmd = [sys.executable, "-m", "unittest", str(rel_path)]
        res = subprocess.run(cmd, cwd=str(repo_root), capture_output=True, text=True)

        if res.returncode == 0:
            print("OK")
            passed_count += 1
        else:
            print("FAILED")
            failed_files.append((tf.name, res.stdout + "\n" + res.stderr))

    print("==================================================================")
    print(f"SUMMARY: {passed_count}/{len(test_files)} test modules passed.")

    if failed_files:
        print("\n--- FAILURE DETAILS ---")
        for fname, err in failed_files:
            print(f"\n[FAIL] {fname}:")
            print(err)
        sys.exit(1)
    else:
        print("\nALL TEST MODULES PASSED SUCCESSFULLY!")
        sys.exit(0)

if __name__ == "__main__":
    main()
