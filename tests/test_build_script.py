"""Verify native-command failure handling without running a destructive build."""
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.skipif(sys.platform != "win32", reason="PowerShell Windows build")
def test_failed_native_build_step_never_prints_success():
    script = (Path(__file__).parents[1] / "scripts" / "build-windows.ps1").read_text(encoding="utf-8")
    start = script.index("function Invoke-Checked")
    end = script.index("# Python 3.12")
    command = "$ErrorActionPreference = 'Stop'\n" + script[start:end]
    command += "\nInvoke-Checked 'Expected build failure' { & $env:COMSPEC /c exit 23 }\nWrite-Host 'SUCCESS'\n"
    result = subprocess.run(["powershell", "-NoProfile", "-Command", command],
                            capture_output=True, text=True, timeout=20)
    assert result.returncode != 0
    assert "SUCCESS" not in result.stdout
    assert "exit code 23" in result.stderr
