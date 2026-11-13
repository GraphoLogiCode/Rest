"""Save the Rest database password locally without putting it in shell history."""

from getpass import getpass
from pathlib import Path
from urllib.parse import quote
import os


def main():
    env_path = Path(__file__).resolve().parents[1] / ".env"
    existing = env_path.read_text() if env_path.exists() else ""
    if "SUPABASE_URL=https://byrndjhgzusfjdgjfbev.supabase.co" not in existing:
        raise SystemExit("Expected Rest project configuration in backend/.env; no changes made.")
    password = getpass("Rest Supabase database password (hidden): ")
    if not password:
        raise SystemExit("Password was empty; no changes made.")
    url = (
        "postgresql://postgres.byrndjhgzusfjdgjfbev:"
        + quote(password, safe="")
        + "@aws-0-us-east-2.pooler.supabase.com:5432/postgres?sslmode=require"
    )
    lines = existing.splitlines()
    matches = [i for i, line in enumerate(lines) if line.startswith("DATABASE_URL=")]
    if len(matches) != 1:
        raise SystemExit("Expected exactly one DATABASE_URL entry; no changes made.")
    lines[matches[0]] = "DATABASE_URL=" + url
    # Restrict permissions before writing the credential; never print its value.
    os.chmod(env_path, 0o600)
    env_path.write_text("\n".join(lines) + "\n")
    print("Saved database connection in backend/.env (owner-only permissions).")
    print("Connection has not been tested yet. Return to the chat for verification.")


if __name__ == "__main__":
    main()
