import subprocess

import modal

app = modal.App("nailvision-hello")


@app.function(gpu="T4")
def hello():
    print(subprocess.run(["nvidia-smi"], capture_output=True, text=True).stdout)


@app.local_entrypoint()
def main():
    hello.remote()
