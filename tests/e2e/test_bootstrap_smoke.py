import subprocess
from pathlib import Path


def test_bootstrap_is_valid_bash():
    script = Path("scripts/install-remote.sh")
    assert script.exists()
    # bash syntax check (-n: no-exec)
    subprocess.run(["bash", "-n", str(script)], check=True)
