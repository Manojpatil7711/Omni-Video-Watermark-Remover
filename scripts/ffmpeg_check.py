import shutil
import subprocess

for name in ("ffmpeg", "ffprobe"):
    path = shutil.which(name)
    print(f"{name}: {path or 'NOT FOUND'}")
    if path:
        result = subprocess.run([name, "-version"], capture_output=True, text=True)
        print(result.stdout.splitlines()[0] if result.stdout else "unknown version")
