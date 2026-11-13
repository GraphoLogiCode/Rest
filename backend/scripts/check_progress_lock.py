"""Exercise shared database locks without reading or writing customer rows."""
import asyncio
import os
from pathlib import Path
from uuid import uuid4
from dotenv import load_dotenv
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.storage.postgres import PostgresStore
load_dotenv(Path(__file__).resolve().parents[1] / '.env')

async def main():
    store = PostgresStore(os.environ['DATABASE_URL'])
    owner = uuid4()
    first_entered, release, second_entered = asyncio.Event(), asyncio.Event(), asyncio.Event()
    async def first():
        async with store.progress_owner_lock(owner):
            first_entered.set()
            await release.wait()
    async def second():
        async with store.progress_owner_lock(owner):
            second_entered.set()
    one = asyncio.create_task(first())
    try:
        await asyncio.wait_for(first_entered.wait(), 12)
        two = asyncio.create_task(second())
        await asyncio.sleep(0.3)
        assert not second_entered.is_set()
        release.set()
        await asyncio.wait_for(asyncio.gather(one, two), 12)
        assert second_entered.is_set()
        assert store.list_progress(owner, 'photo') == []
        print('Separate database sessions serialized progress operations; private read for a random non-user returned no records. No customer rows changed.')
    finally:
        release.set()
        store.close()
try:
    asyncio.run(main())
except Exception:
    raise SystemExit('Lock check failed. Private connection details were not printed.')
