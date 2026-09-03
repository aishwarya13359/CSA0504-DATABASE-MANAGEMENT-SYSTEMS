# National Vocational Certification and Exam Slot-Booking System — Reference Implementation

Run in this order (Python 3, stdlib sqlite3 only, no installs needed):

1. python3 seed_data.py                       # builds exam_system.db (20 centers, 5000 candidates, 50000 attempts)
2. python3 hash_lookup.py                     # static hash table vs B+-tree index vs full scan benchmark
3. python3 query_optimization.py              # EXPLAIN QUERY PLAN + timing for the 4 report queries
4. python3 transactions_demo.py               # ACID booking transaction + optimistic-lock result publishing
5. python3 concurrency_anomaly_baseline.py    # reproduces the double-booking anomaly (no transaction guard)
6. python3 concurrency_test.py                # shows the anomaly eliminated (BEGIN IMMEDIATE + capacity check)

For a MySQL/PostgreSQL submission: port schema.sql (drop WITHOUT ROWID, keep the
composite PRIMARY KEY), replace BEGIN IMMEDIATE with SELECT ... FOR UPDATE or
SET TRANSACTION ISOLATION LEVEL SERIALIZABLE, and re-capture EXPLAIN / EXPLAIN
ANALYZE screenshots from MySQL Workbench / pgAdmin for the rubric's "tool usage
evidence" requirement.
