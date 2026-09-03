"""
Baseline (BAD) implementation: un-coordinated read-then-write, exactly
as described in the problem statement. Demonstrates the double-booking
anomaly that the transaction-managed version (concurrency_test.py) fixes.
"""
import sqlite3, threading, time

DB = "exam_system.db"
SLOT_ID = 77777
N_THREADS = 20
results = []
lock = threading.Lock()

def naive_book(candidate_id):
    conn = sqlite3.connect(DB, timeout=10)
    row = conn.execute("SELECT capacity, booked_count FROM Slot WHERE slot_id=?",
                        (SLOT_ID,)).fetchone()
    capacity, booked = row
    # <-- window here: another thread can read the same 'booked' value
    time.sleep(0.001)
    if booked >= capacity:
        conn.close()
        return False
    conn.execute("INSERT INTO Booking (candidate_id, slot_id, status) VALUES (?,?,'CONFIRMED')",
                 (candidate_id, SLOT_ID))
    conn.execute("UPDATE Slot SET booked_count = ? WHERE slot_id=?", (booked + 1, SLOT_ID))
    conn.commit()
    conn.close()
    return True

def worker(cid):
    ok = naive_book(cid)
    with lock:
        results.append((cid, ok))

def run():
    conn = sqlite3.connect(DB)
    conn.execute("INSERT OR REPLACE INTO Slot VALUES (?,?,?,?,?,?)",
                 (SLOT_ID, 1, "2026-09-16", "09:00", 1, 0))
    conn.execute("DELETE FROM Booking WHERE slot_id=?", (SLOT_ID,))
    conn.commit()
    conn.close()

    threads = [threading.Thread(target=worker, args=(2000 + i,)) for i in range(N_THREADS)]
    for t in threads: t.start()
    for t in threads: t.join()

    conn = sqlite3.connect(DB)
    final = conn.execute("SELECT capacity, booked_count FROM Slot WHERE slot_id=?",
                          (SLOT_ID,)).fetchone()
    n_bookings = conn.execute("SELECT COUNT(*) FROM Booking WHERE slot_id=?",
                               (SLOT_ID,)).fetchone()[0]
    conn.close()

    n_success = sum(1 for _, ok in results if ok)
    print(f"{N_THREADS} concurrent NAIVE booking attempts for 1 seat:")
    print(f"  App-level successes reported : {n_success}")
    print(f"  Slot.capacity={final[0]}  Slot.booked_count={final[1]}  "
          f"Booking rows actually inserted={n_bookings}")
    if n_bookings > final[0]:
        print(f"  -> ANOMALY CONFIRMED: {n_bookings} candidates booked into "
              f"{final[0]} seat(s) (lost update / double booking).")
    else:
        print("  -> No anomaly this run (race window too narrow to trigger); "
              "increase thread count or sleep to reproduce reliably.")

if __name__ == "__main__":
    run()
