import sqlite3

DB = "exam_system.db"

def book_slot(conn, candidate_id, slot_id, simulate_failure=False):
    """
    Bounded ACID transaction for slot booking.
    BEGIN IMMEDIATE takes a write lock up-front (SQLite's analogue of
    SELECT ... FOR UPDATE row locking used in MySQL/PostgreSQL) so a
    concurrent booking on the same slot must wait rather than read a
    stale booked_count (prevents the lost-update / over-booking anomaly).
    """
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute("SAVEPOINT before_capacity_check")

        row = conn.execute(
            "SELECT capacity, booked_count FROM Slot WHERE slot_id = ?",
            (slot_id,)).fetchone()
        capacity, booked = row

        if booked >= capacity:
            conn.execute("ROLLBACK TO before_capacity_check")
            conn.execute("ROLLBACK")
            return False, "SLOT_FULL"

        conn.execute(
            "INSERT INTO Booking (candidate_id, slot_id, status) VALUES (?,?,'CONFIRMED')",
            (candidate_id, slot_id))

        conn.execute(
            "UPDATE Slot SET booked_count = booked_count + 1 WHERE slot_id = ?",
            (slot_id,))

        if simulate_failure:
            raise RuntimeError("Simulated failure mid-transaction")

        conn.execute("RELEASE before_capacity_check")
        conn.commit()
        return True, "CONFIRMED"

    except sqlite3.IntegrityError as e:
        conn.execute("ROLLBACK TO before_capacity_check")
        conn.rollback()
        return False, f"INTEGRITY_ERROR: {e}"
    except RuntimeError as e:
        conn.rollback()
        return False, f"ROLLED_BACK: {e}"


def publish_result(conn, attempt_id, candidate_id, center_id, exam_date,
                    score, examiner, expected_version=None):
    """
    Optimistic-concurrency result publish/update. If expected_version is
    given, the UPDATE only succeeds when the row's version still matches
    -- this is the 'lost update' guard for concurrent examiners editing
    the same result.
    """
    conn.execute("BEGIN IMMEDIATE")
    existing = conn.execute(
        "SELECT result_id, version FROM Result WHERE attempt_id = ?",
        (attempt_id,)).fetchone()

    if existing is None:
        conn.execute("""INSERT INTO Result
            (attempt_id, candidate_id, center_id, exam_date, final_score,
             grade, published_by) VALUES (?,?,?,?,?,?,?)""",
            (attempt_id, candidate_id, center_id, exam_date, score,
             "PASS" if score >= 40 else "FAIL", examiner))
        conn.commit()
        return True, "INSERTED"

    result_id, current_version = existing
    if expected_version is not None and expected_version != current_version:
        conn.rollback()
        return False, f"VERSION_CONFLICT (have {current_version}, expected {expected_version})"

    cur = conn.execute(
        """UPDATE Result SET final_score = ?, grade = ?, published_by = ?,
           version = version + 1
           WHERE result_id = ? AND version = ?""",
        (score, "PASS" if score >= 40 else "FAIL", examiner,
         result_id, current_version))
    if cur.rowcount == 0:
        conn.rollback()
        return False, "VERSION_CONFLICT_AT_UPDATE"
    conn.commit()
    return True, "UPDATED"


if __name__ == "__main__":
    conn = sqlite3.connect(DB, timeout=5)
    conn.isolation_level = None  # manual transaction control

    print("=" * 78)
    print("Demo 1: Normal successful booking transaction")
    print("=" * 78)
    slot = conn.execute("SELECT slot_id, capacity, booked_count FROM Slot LIMIT 1").fetchone()
    print(f"Target slot before booking: slot_id={slot[0]} capacity={slot[1]} booked={slot[2]}")
    ok, msg = book_slot(conn, candidate_id=1, slot_id=slot[0])
    print(f"Result: ok={ok} status={msg}")
    slot2 = conn.execute("SELECT booked_count FROM Slot WHERE slot_id=?", (slot[0],)).fetchone()
    print(f"booked_count after COMMIT: {slot2[0]}")

    print()
    print("=" * 78)
    print("Demo 2: Transaction rolled back mid-way (simulated failure)")
    print("=" * 78)
    before = conn.execute("SELECT booked_count FROM Slot WHERE slot_id=?", (slot[0],)).fetchone()[0]
    booking_count_before = conn.execute("SELECT COUNT(*) FROM Booking").fetchone()[0]
    ok, msg = book_slot(conn, candidate_id=2, slot_id=slot[0], simulate_failure=True)
    print(f"Result: ok={ok} status={msg}")
    after = conn.execute("SELECT booked_count FROM Slot WHERE slot_id=?", (slot[0],)).fetchone()[0]
    booking_count_after = conn.execute("SELECT COUNT(*) FROM Booking").fetchone()[0]
    print(f"booked_count unchanged: {before} -> {after}")
    print(f"Booking rows unchanged: {booking_count_before} -> {booking_count_after}")
    print("(No partial data committed -- atomicity preserved.)")

    print()
    print("=" * 78)
    print("Demo 3: Fill a slot to capacity, then reject an over-limit booking")
    print("=" * 78)
    tiny_slot_id = 99999
    conn.execute("INSERT OR REPLACE INTO Slot VALUES (?,?,?,?,?,?)",
                 (tiny_slot_id, 1, "2026-09-01", "11:00", 2, 0))
    conn.commit()
    results = []
    for cand in [101, 102, 103]:
        ok, msg = book_slot(conn, cand, tiny_slot_id)
        results.append((cand, ok, msg))
    for cand, ok, msg in results:
        print(f"  candidate {cand}: ok={ok} status={msg}")
    final = conn.execute("SELECT capacity, booked_count FROM Slot WHERE slot_id=?", (tiny_slot_id,)).fetchone()
    print(f"Final slot state: capacity={final[0]} booked_count={final[1]} "
          f"(never exceeds capacity)")

    print()
    print("=" * 78)
    print("Demo 4: Optimistic-concurrency result publish + conflict rejection")
    print("=" * 78)
    ok, msg = publish_result(conn, attempt_id=1, candidate_id=1, center_id=1,
                              exam_date="2026-01-10", score=72.5, examiner="Examiner_A")
    print(f"Examiner_A first publish: ok={ok} status={msg}")
    row = conn.execute("SELECT version FROM Result WHERE attempt_id=1").fetchone()
    stale_version = row[0]
    ok, msg = publish_result(conn, attempt_id=1, candidate_id=1, center_id=1,
                              exam_date="2026-01-10", score=75.0, examiner="Examiner_B",
                              expected_version=stale_version)
    print(f"Examiner_B update using version {stale_version}: ok={ok} status={msg}")
    ok, msg = publish_result(conn, attempt_id=1, candidate_id=1, center_id=1,
                              exam_date="2026-01-10", score=68.0, examiner="Examiner_C",
                              expected_version=stale_version)  # stale now
    print(f"Examiner_C update using STALE version {stale_version}: ok={ok} status={msg}")
    final_row = conn.execute("SELECT final_score, version, published_by FROM Result WHERE attempt_id=1").fetchone()
    print(f"Final row: score={final_row[0]} version={final_row[1]} published_by={final_row[2]}")

    conn.close()
