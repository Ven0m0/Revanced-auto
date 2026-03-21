import subprocess
import sys

class Builder:
    def __init__(self, config):
        self.config = config
    
    def build_all(self) -> bool:
        result = subprocess.run(
            ["./build.sh", self.config.config_file],
            capture_output=True,
            text=True
        )
        return result.returncode == 0
