import sys
from pathlib import Path

# Add src to sys.path
sys.path.append(str(Path(__file__).parent.parent / "src"))

from psd_analysis.common.config import load_config
from psd_analysis.common.builders import ChannelBuilder

def confirm():
    # Try new config path first, fallback to old
    cfg_path = Path(__file__).parent.parent / "configs" / "default_config.yml"
    if not cfg_path.exists():
        cfg_path = Path(__file__).parent.parent / "config.yml"
        
    if not cfg_path.exists():
        print(f"Error: Config not found.")
        return

    print(f"Loading config from {cfg_path}...")
    cfg = load_config(cfg_path)
    
    builder = ChannelBuilder(cfg)
    active_triplets = builder._load_active_stations()
    
    locations_found = sorted({loc for net, sta, loc in active_triplets})
    print(f"\nLocation codes found in active channels (after blacklisting S0 and 20):")
    for loc in locations_found:
        count = sum(1 for net, sta, l in active_triplets if l == loc)
        print(f"  '{loc}': {count} stations")

    if 'S0' in locations_found:
        print("\nFAILURE: 'S0' was found in the active list!")
    else:
        print("\nSUCCESS: 'S0' was successfully blacklisted.")

    expected = {'00', '01'}
    found_expected = expected.intersection(set(locations_found))
    if found_expected == expected:
        print(f"SUCCESS: Both '00' and '01' are active and being discovered.")
    elif found_expected:
        print(f"PARTIAL: Found {found_expected}, but missing {expected - found_expected}")
    else:
        print(f"NOTIFICATION: Neither '00' nor '01' were found. Check if they are currently active.")

    print("\nExamples of selected channels:")
    for net, sta, loc in active_triplets[:10]:
        print(f"  {net}.{sta}.{loc}")

if __name__ == "__main__":
    confirm()
