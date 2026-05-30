import subprocess
from pathlib import Path


def test_bootstrap_is_valid_bash():
    script = Path("scripts/install-remote.sh")
    assert script.exists()
    # bash 구문 검사 (-n: no-exec)
    subprocess.run(["bash", "-n", str(script)], check=True)
