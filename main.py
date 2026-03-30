import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent

def run_scraper(path, name):
    print(f"\n{'='*50}")
    print(f"Running {name} scraper...")
    print(f"{'='*50}")
    result = subprocess.run([sys.executable, str(path)], cwd=str(path.parent))
    return result.returncode

def main():
    mtg_result = run_scraper(SCRIPT_DIR / "magic.app" / "scraper.py", "Magic")
    poke_result = run_scraper(SCRIPT_DIR / "poke.app" / "scraper.py", "Pokemon")
    
    print(f"\n{'='*50}")
    print("Done!")
    print(f"{'='*50}")
    
    if mtg_result != 0:
        print("Magic scraper failed")
    if poke_result != 0:
        print("Pokemon scraper failed")
    
    sys.exit(max(mtg_result, poke_result))

if __name__ == "__main__":
    main()
