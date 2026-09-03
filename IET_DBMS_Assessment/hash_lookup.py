"""
Static hashing (division method) with separate chaining for
candidate-wise point lookup on the ExamAttempt archive, benchmarked
against (a) a full sequential scan and (b) the B-tree secondary
index idx_attempt_candidate created in schema.sql.
"""
import sqlite3, time, random

DB = "exam_system.db"
BUCKETS = 10007   # prime, ~2x candidate count, keeps chain length low

def h(candidate_id: int) -> int:
    return candidate_id % BUCKETS

def build_hash_index(conn):
    """Build an in-memory static hash table: bucket -> [ (candidate_id, rowid_list) ]"""
    table = [[] for _ in range(BUCKETS)]
    cur = conn.execute("SELECT candidate_id, center_id, exam_date, attempt_id FROM ExamAttempt")
    n_rows, n_collisions = 0, 0
    for candidate_id, center_id, exam_date, attempt_id in cur:
        b = h(candidate_id)
        bucket = table[b]
        if bucket and bucket[-1][0] != candidate_id and len(bucket) > 0:
            pass
        bucket.append((candidate_id, center_id, exam_date, attempt_id))
        n_rows += 1
    # collision stats: buckets holding >1 distinct candidate_id
    for bucket in table:
        distinct = len(set(x[0] for x in bucket))
        if distinct > 1:
            n_collisions += 1
    return table, n_rows, n_collisions

def hash_lookup(table, candidate_id):
    bucket = table[h(candidate_id)]
    return [row for row in bucket if row[0] == candidate_id]

def linear_scan(conn, candidate_id):
    cur = conn.execute(
        "SELECT candidate_id, center_id, exam_date, attempt_id FROM ExamAttempt "
        "WHERE candidate_id = ?", (candidate_id,))
    return cur.fetchall()

def main():
    conn = sqlite3.connect(DB)

    print("Building static hash table (division method, N=%d buckets, chaining)..." % BUCKETS)
    table, n_rows, n_collisions = build_hash_index(conn)
    avg_chain = n_rows / BUCKETS
    print(f"  rows hashed        : {n_rows}")
    print(f"  buckets w/ collision: {n_collisions} / {BUCKETS}")
    print(f"  average chain length: {avg_chain:.3f}")

    random.seed(7)
    test_ids = [random.randint(1, 5000) for _ in range(500)]

    # 1) Full sequential scan (no index) -- disable index use with NOT INDEXED
    t0 = time.perf_counter()
    for cid in test_ids:
        conn.execute("SELECT candidate_id, attempt_id FROM ExamAttempt "
                      "NOT INDEXED WHERE candidate_id = ?", (cid,)).fetchall()
    t_scan = time.perf_counter() - t0

    # 2) B-tree secondary index (idx_attempt_candidate)
    t0 = time.perf_counter()
    for cid in test_ids:
        conn.execute("SELECT candidate_id, attempt_id FROM ExamAttempt "
                      "WHERE candidate_id = ?", (cid,)).fetchall()
    t_index = time.perf_counter() - t0

    # 3) Static hash table (in-memory simulation of a direct/hashed file)
    t0 = time.perf_counter()
    for cid in test_ids:
        hash_lookup(table, cid)
    t_hash = time.perf_counter() - t0

    print("\nAverage lookup latency over 500 random candidate_id point queries:")
    print(f"  Full sequential scan (NOT INDEXED) : {1000*t_scan/500:.4f} ms/lookup   total {t_scan*1000:.2f} ms")
    print(f"  B+-tree secondary index            : {1000*t_index/500:.4f} ms/lookup   total {t_index*1000:.2f} ms")
    print(f"  Static hash table (chaining)       : {1000*t_hash/500:.4f} ms/lookup   total {t_hash*1000:.2f} ms")
    print(f"\n  Speedup, hash vs scan  : {t_scan/t_hash:.1f}x")
    print(f"  Speedup, index vs scan : {t_scan/t_index:.1f}x")

    conn.close()

if __name__ == "__main__":
    main()
