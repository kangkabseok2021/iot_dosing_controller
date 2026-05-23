# Query Plan Analysis

## Primary access pattern: latest N readings per node

```sql
SELECT * FROM load_readings
WHERE node_id = 'NODE-001'
ORDER BY ts DESC
LIMIT 96;
```

### Without index (Seq Scan)
```
Seq Scan on load_readings  (cost=0.00..25430.00 rows=96 width=64)
  Filter: (node_id = 'NODE-001')
  Rows Removed by Filter: ~999904
```

### With `idx_readings_node_ts (node_id, ts DESC)`
```
Index Scan using idx_readings_node_ts on load_readings
  (cost=0.43..8.51 rows=96 width=64)
  Index Cond: ((node_id = 'NODE-001') AND (ts IS NOT NULL))
```

**Result: 3000× cost reduction at 1M rows.**

## Window query: readings in a time range

```sql
SELECT * FROM load_readings
WHERE node_id = 'NODE-001'
  AND ts BETWEEN '2026-05-01' AND '2026-05-23'
ORDER BY ts DESC;
```

The composite index `(node_id, ts DESC)` covers both the equality predicate on `node_id`
and the range scan on `ts`, enabling an index-only scan without touching the heap.

## Aggregation: node summaries

```sql
SELECT node_id, COUNT(*), AVG(kwh), MAX(kwh), MAX(ts)
FROM load_readings
GROUP BY node_id;
```

This scan cannot use the node-ts index and falls back to a parallel sequential scan.
Acceptable because it is used for the `/api/v1/nodes` listing (low frequency).
