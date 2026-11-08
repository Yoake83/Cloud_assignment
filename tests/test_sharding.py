import json

import pytest
import worker


def lines(n):
    return [json.dumps({"id": f"C{i:04d}", "text": f"t{i}"}) for i in range(n)]


def test_shards_partition_the_pool_exactly():
    pool = lines(3000)
    shards = [worker.shard_items(pool, i, 3) for i in range(3)]
    ids = [x["id"] for s in shards for x in s]
    assert len(ids) == 3000 and len(set(ids)) == 3000
    assert shards[1][0]["id"] == "C0001" and shards[2][1]["id"] == "C0005"


def test_bad_shard_settings_raise():
    with pytest.raises(ValueError):
        worker.shard_items(lines(5), 2, 2)
