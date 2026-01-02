"""Normalize sampling documents in MongoDB.

Rules applied per document:
- Prefer canonical snake_case fields in DB (pond_id, sampling_date, sample_size, average_weight, average_length,
  survival_rate, feed_conversion_ratio, recorded_by, total_cost, cost_unit, total_count, type, cost).
- For known camelCase aliases (pondId, samplingDate, sampleSize, averageWeight, ...), if the canonical field
  is missing or null/empty, copy value to canonical field. Then remove the camelCase alias and other duplicate
  keys (like totalAmount, total_amount, totalCount, total_count, costUnit).
- Preserve data when possible; coerce numeric fields where reasonable.

Run: python3 scripts/normalize_sampling_docs.py
"""

from fin_server.utils.normalize_sampling import normalize_sampling_docs


if __name__ == '__main__':
    n = normalize_sampling_docs()
    print(f"Normalized {n} sampling documents")
