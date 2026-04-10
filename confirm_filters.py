
from pathlib import Path
from config_loader import load_config
from channel_builder import ChannelBuilder

def confirm():
    cfg_path = Path("config.yml")
    if not cfg_path.exists():
        print(f"Error: {cfg_path} not found.")
        return

    print(f"Loading config from {cfg_path}...")
    cfg = load_config(cfg_path)
    
    # We want to check what's active in the summary files
    builder = ChannelBuilder(cfg)
    active_triplets = builder._load_active_hhz_stations()
    
    locations_found = sorted({loc for net, sta, loc in active_triplets})
    print(f"\nLocation codes found in active HHZ channels (after blacklisting S0):")
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
        print(f"SUCCESS: Both '00' and '01' are being used.")
    elif found_expected:
        print(f"PARTIAL: Found {found_expected}, but missing {expected - found_expected}")
    else:
        print(f"FAILURE: Neither '00' nor '01' were found in the active list.")

    # Show a few examples
    print("\nExamples of selected channels:")
    for net, sta, loc in active_triplets[:10]:
        print(f"  {net}.{sta}.{loc}")

if __name__ == "__main__":
    confirm()
