import sqlite3, time

DB = "exam_system.db"
conn = sqlite3.connect(DB)

def plan(sql, params=()):
    rows = conn.execute("EXPLAIN QUERY PLAN " + sql, params).fetchall()
    return "\n".join(f"    {r}" for r in rows)

def timeit(sql, params=(), n=200):
    t0 = time.perf_counter()
    for _ in range(n):
        conn.execute(sql, params).fetchall()
    return (time.perf_counter() - t0) * 1000 / n   # ms/exec

print("=" * 78)
print("Q1. Candidate attempt-history lookup  (WHERE candidate_id = ?)")
print("=" * 78)
sql1 = "SELECT * FROM ExamAttempt WHERE candidate_id = ?"
print("Plan (uses idx_attempt_candidate):")
print(plan(sql1, (123,)))
print(f"Timing: {timeit(sql1, (123,)):.4f} ms/exec (500 iterations avg shown earlier: hash 0.0012 ms)")

print()
print("=" * 78)
print("Q2. Center-wise audit for a given date (range/equality on clustering key)")
print("=" * 78)
sql2 = "SELECT * FROM ExamAttempt WHERE center_id = ? AND exam_date = ?"
print("Plan (clustering PK (center_id, exam_date, attempt_id) used directly):")
print(plan(sql2, (5, "2026-03-10")))
print(f"Timing: {timeit(sql2, (5, '2026-03-10')):.4f} ms/exec")

print()
print("=" * 78)
print("Q3. Booking-window query: seats remaining per slot at a center on a date")
print("=" * 78)
sql3_unopt = """
SELECT s.slot_id, s.slot_time, s.capacity - s.booked_count AS seats_left
FROM Slot s
WHERE s.center_id = ? AND s.exam_date = ?
ORDER BY s.slot_time
"""
print("Plan BEFORE adding composite index on (center_id, exam_date):")
conn.execute("DROP INDEX IF EXISTS idx_slot_center_date")
print(plan(sql3_unopt, (5, "2026-03-10")))
t_before = timeit(sql3_unopt, (5, "2026-03-10"))
print(f"Timing before index: {t_before:.4f} ms/exec")

conn.execute("CREATE INDEX idx_slot_center_date ON Slot(center_id, exam_date)")
print("\nPlan AFTER re-creating idx_slot_center_date:")
print(plan(sql3_unopt, (5, "2026-03-10")))
t_after = timeit(sql3_unopt, (5, "2026-03-10"))
print(f"Timing after index: {t_after:.4f} ms/exec")
print(f"Improvement: {(t_before - t_after)/t_before*100:.1f}% reduction in latency"
      if t_before > 0 else "")

print()
print("=" * 78)
print("Q4. Branch-wise / center-wise result summary (join + aggregate)")
print("=" * 78)
sql4 = """
SELECT c.city, COUNT(*) AS attempts, ROUND(AVG(a.raw_score),2) AS avg_score,
       ROUND(MIN(a.raw_score),2) AS min_score, ROUND(MAX(a.raw_score),2) AS max_score
FROM ExamAttempt a
JOIN Center c ON c.center_id = a.center_id
WHERE a.exam_date = ?
GROUP BY c.city
ORDER BY avg_score DESC
"""
print("Plan:")
print(plan(sql4, ("2026-03-10",)))
rows = conn.execute(sql4, ("2026-03-10",)).fetchall()
print("Result:")
for r in rows:
    print("   ", r)

conn.close()
