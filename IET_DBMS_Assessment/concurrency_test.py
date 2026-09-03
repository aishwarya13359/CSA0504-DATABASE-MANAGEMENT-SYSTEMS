"""
Concurrency-anomaly test: N threads simultaneously attempt to book the
LAST available seat of a single slot. Without transaction isolation
(read-then-write without locking) this classically double-books the
seat. With BEGIN IMMEDIATE (write-intent lock acquired at transaction
start, SQLite's stand-in for SELECT ... FOR UPDATE / SERIALIZABLE
locking in MySQL/PostgreSQL) only one thread may succeed.
"""
import sqlite3, threading, time
from transactions_demo import book_slot

DB = "exam_system.db"
LAST_SEAT_SLOT = 88888
N_THREADS = 20

def setup_last_seat_slot():
    conn = sqlite3.connect(DB)
    conn.execute("INSERT OR REPLACE INTO Slot VALUES (?,?,?,?,?,?)",
                 (LAST_SEAT_SLOT, 1, "2026-09-15", "09:00", 1, 0))  # capacity = 1
    conn.execute("DELETE FROM Booking WHERE slot_id = ?", (LAST_SEAT_SLOT,))
    conn.commit()
    conn.close()

results = []
lock = threading.Lock()

def worker(candidate_id):
    conn = sqlite3.connect(DB, timeout=10)
    conn.isolation_level = None
    ok, msg = book_slot(conn, candidate_id, LAST_SEAT_SLOT)
    with lock:
        results.append((candidate_id, ok, msg))
    conn.close()

def run_concurrent_test():
    setup_last_seat_slot()
    threads = [threading.Thread(target=worker, args=(1000 + i,)) for i in range(N_THREADS)]
    t0 = time.perf_counter()
    for t in threads: t.start()
    for t in threads: t.join()
    elapsed = time.perf_counter() - t0

    conn = sqlite3.connect(DB)
    final = conn.execute("SELECT capacity, booked_count FROM Slot WHERE slot_id=?",
                          (LAST_SEAT_SLOT,)).fetchone()
    n_bookings = conn.execute("SELECT COUNT(*) FROM Booking WHERE slot_id=? AND status='CONFIRMED'",
                               (LAST_SEAT_SLOT,)).fetchone()[0]
    conn.close()

    n_success = sum(1 for _, ok, _ in results if ok)
    n_rejected = sum(1 for _, ok, _ in results if not ok)

    print(f"{N_THREADS} concurrent booking attempts for 1 remaining seat "
          f"(elapsed {elapsed*1000:.1f} ms)")
    print(f"  Successful bookings : {n_success}")
    print(f"  Rejected (SLOT_FULL): {n_rejected}")
    print(f"  Slot.capacity={final[0]}  Slot.booked_count={final[1]}  "
          f"CONFIRMED Booking rows={n_bookings}")
    assert final[1] <= final[0], "OVER-BOOKING ANOMALY DETECTED"
    assert n_success == 1, "MORE THAN ONE CANDIDATE WAS BOOKED INTO 1 SEAT"
    print("  -> PASS: capacity constraint held under concurrent write load.")

if __name__ == "__main__":
    run_concurrent_test()
