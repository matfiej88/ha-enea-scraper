#!/usr/bin/env python3
"""
Script to convert Enea historical data from JSONL to TSV format for Home Assistant statistics import.
Creates two TSV files:
- enea_consumed_import.tsv for sensor.enea_energy_consumed
- enea_returned_import.tsv for sensor.enea_energy_returned
"""

import json
from datetime import datetime
from typing import List, Tuple
from collections import defaultdict

INPUT_FILE = "enea_historical_data.jsonl"
OUTPUT_FILE_CONSUMED = "enea_consumed_import.tsv"
OUTPUT_FILE_RETURNED = "enea_returned_import.tsv"


def parse_jsonl_file(filename: str) -> Tuple[List[Tuple[str, float]], List[Tuple[str, float]]]:
    """
    Parse JSONL file and extract consumed and returned energy data.

    Returns:
        Tuple of (consumed_records, returned_records)
        Each record is (datetime_str, energy_kwh)
    """
    consumed_records = []
    returned_records = []

    # Use defaultdict to aggregate hourly data by date
    consumed_daily = defaultdict(float)
    returned_daily = defaultdict(float)

    with open(filename, 'r', encoding='utf-8') as f:
        for line_num, line in enumerate(f, 1):
            try:
                record = json.loads(line.strip())

                # Skip failed requests
                if record.get('status') != 'success':
                    continue

                data = record.get('data', [])
                if not data:
                    continue

                # Process each hourly record
                for hourly in data:
                    date_from = hourly.get('dateFrom')
                    if not date_from:
                        continue

                    # Parse datetime and get date for aggregation
                    try:
                        dt = datetime.fromisoformat(date_from)
                        date_key = dt.strftime('%Y-%m-%d')

                        # Get energy values
                        consumed = float(hourly.get('aecasb', 0))
                        returned = float(hourly.get('eaecasb', 0))

                        # Aggregate by day
                        consumed_daily[date_key] += consumed
                        returned_daily[date_key] += returned

                    except (ValueError, TypeError) as e:
                        print(f"Warning: Could not parse datetime '{date_from}' on line {line_num}: {e}")
                        continue

            except json.JSONDecodeError as e:
                print(f"Error: Invalid JSON on line {line_num}: {e}")
                continue

    # Convert aggregated data to sorted lists
    for date_key in sorted(consumed_daily.keys()):
        # Format as "DD.MM.YYYY 12:00" for HA statistics
        dt = datetime.strptime(date_key, '%Y-%m-%d')
        formatted_date = dt.strftime('%d.%m.%Y 12:00')

        consumed_records.append((formatted_date, consumed_daily[date_key]))
        returned_records.append((formatted_date, returned_daily[date_key]))

    return consumed_records, returned_records


def write_tsv_file(filename: str, statistic_id: str, records: List[Tuple[str, float]]):
    """Write records to TSV file in Home Assistant statistics format."""
    with open(filename, 'w', encoding='utf-8') as f:
        # Write header
        f.write("statistic_id\tstart\tdelta\n")

        # Write data rows
        for date_str, energy in records:
            f.write(f"{statistic_id}\t{date_str}\t{energy}\n")


def main():
    """Main function to convert JSONL to TSV files."""
    print("Starting Enea data conversion from JSONL to TSV...")
    print(f"Input file: {INPUT_FILE}")
    print(f"Output files:")
    print(f"  - {OUTPUT_FILE_CONSUMED} (consumed energy)")
    print(f"  - {OUTPUT_FILE_RETURNED} (returned energy)")
    print("-" * 70)

    # Parse JSONL file
    print("Parsing JSONL file...")
    consumed_records, returned_records = parse_jsonl_file(INPUT_FILE)

    print(f"✓ Parsed data:")
    print(f"  - Consumed energy: {len(consumed_records)} daily records")
    print(f"  - Returned energy: {len(returned_records)} daily records")

    # Write consumed energy TSV
    print(f"\nWriting {OUTPUT_FILE_CONSUMED}...")
    write_tsv_file(
        OUTPUT_FILE_CONSUMED,
        "sensor.enea_energy_consumed",
        consumed_records
    )
    print(f"✓ Done! {len(consumed_records)} records written")

    # Write returned energy TSV
    print(f"\nWriting {OUTPUT_FILE_RETURNED}...")
    write_tsv_file(
        OUTPUT_FILE_RETURNED,
        "sensor.enea_energy_returned",
        returned_records
    )
    print(f"✓ Done! {len(returned_records)} records written")

    # Show summary
    print("-" * 70)
    print("Conversion complete!")

    if consumed_records:
        print(f"\nConsumed energy summary:")
        print(f"  First record: {consumed_records[0][0]} - {consumed_records[0][1]:.2f} kWh")
        print(f"  Last record:  {consumed_records[-1][0]} - {consumed_records[-1][1]:.2f} kWh")
        total_consumed = sum(r[1] for r in consumed_records)
        print(f"  Total consumed: {total_consumed:.2f} kWh")

    if returned_records:
        print(f"\nReturned energy summary:")
        print(f"  First record: {returned_records[0][0]} - {returned_records[0][1]:.2f} kWh")
        print(f"  Last record:  {returned_records[-1][0]} - {returned_records[-1][1]:.2f} kWh")
        total_returned = sum(r[1] for r in returned_records)
        print(f"  Total returned: {total_returned:.2f} kWh")


if __name__ == "__main__":
    main()
