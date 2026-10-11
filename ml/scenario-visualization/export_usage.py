"""Export tracking-only events for a future billing adapter. Never sends or charges."""
import argparse
import json
import os
from pathlib import Path
import sqlite3
from uuid import UUID


def export_events(database, destination, after=0):
    # Read-only URI prevents a typo from creating an empty billing database.
    with sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True) as db:
        db.row_factory = sqlite3.Row
        rows = db.execute('SELECT * FROM usage_events WHERE sequence>? ORDER BY sequence', (after,))
        last = after
        count = 0
        # Exclusive creation avoids overwriting prior export checkpoints or other files.
        descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'w') as output:
            for row in rows:
                event = {'schemaVersion': 1, 'eventId': str(UUID(row['event_id'])),
                         'customerId': str(UUID(row['owner'])), 'metric': 'illustration.completed',
                         'quantity': row['quantity'], 'occurredAt': row['occurred_at'],
                         'runtimeMs': row['runtime_ms'], 'model': row['model'], 'region': row['region']}
                output.write(json.dumps(event) + '\n')
                last, count = row['sequence'], count + 1
        return {'events': count, 'lastSequence': last, 'delivered': False, 'paymentsEnabled': False}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--after', type=int, default=0)
    args = parser.parse_args()
    if args.after < 0:
        parser.error('--after must be nonnegative')
    print(json.dumps(export_events(args.database, args.output, args.after)))
