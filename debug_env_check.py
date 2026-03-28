from pathlib import Path

ROOT = Path(r"D:\CuoiKyTin")

print(f"Project root: {ROOT.resolve()}")
print("\nFiles/folders in project root:")
for item in sorted(ROOT.iterdir(), key=lambda p: p.name.lower()):
    suffix = "/" if item.is_dir() else ""
    print(f"- {item.name}{suffix}")

env_file = ROOT / ".env"
print("\n.env check:")
print(f"Exists: {env_file.exists()}")
print(f"Absolute path: {env_file.resolve()}")

if not env_file.exists():
    env_txt = ROOT / ".env.txt"
    if env_txt.exists():
        print("Found .env.txt instead of .env")
        print(f".env.txt path: {env_txt.resolve()}")
