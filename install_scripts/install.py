import re
import subprocess

subprocess.run("echo $(whoami)", shell=True)

subprocess.run("brew install gfortran openblas pkg-config", shell=True)
brew_info_result = subprocess.run("brew info openblas", capture_output=True, text=True, shell=True)

pkg_config_environment = re.search("export PKG_CONFIG_PATH=\"(.*)\"", brew_info_result.stdout)
print(pkg_config_environment.group(1))

env = {"PKG_CONFIG_PATH": pkg_config_environment.group(1)}

subprocess.run("brew install python@3.13", shell=True)

commands = [
    "python3.13 -m venv venv",
    "source venv/bin/activate",
    "pip install -r requirements.txt",
]

for c in commands:
    result = subprocess.run("; which python".join(commands), shell=True)
    if result.returncode != 0:
        print(f"failed command: {c}")
        break

print(pkg_config_environment.group(0))
