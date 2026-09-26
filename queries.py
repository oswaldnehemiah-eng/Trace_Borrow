"""Database queries for the simple TraceBorrow application."""

from database import get_connection


def create_user(username, password_hash):
    conn = get_connection()
    cursor = conn.execute(
        "INSERT INTO users (username, password_hash) VALUES (?, ?)",
        (username.strip(), password_hash),
    )
    conn.commit()
    user_id = cursor.lastrowid
    conn.close()
    return user_id


def get_user_by_username(username):
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM users WHERE username = ?",
        (username.strip(),),
    ).fetchone()
    conn.close()
    return row


def get_user_by_id(user_id):
    conn = get_connection()
    row = conn.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    conn.close()
    return row


def get_other_users(user_id):
    conn = get_connection()
    rows = conn.execute(
        "SELECT id, username FROM users WHERE id != ? ORDER BY username",
        (user_id,),
    ).fetchall()
    conn.close()
    return rows


def _all_transfers(conn):
    return conn.execute(
        """
        SELECT
            transfers.id,
            transfers.transferred_at,
            transfers.item_description,
            transfers.from_user_id,
            transfers.to_user_id,
            sender.username AS from_username,
            receiver.username AS to_username
        FROM transfers
        JOIN users AS sender ON transfers.from_user_id = sender.id
        JOIN users AS receiver ON transfers.to_user_id = receiver.id
        ORDER BY transfers.id ASC
        """
    ).fetchall()


def _build_item_chains(rows):
    """Return the current custody chain for every item description."""
    by_item = {}
    for row in rows:
        by_item.setdefault(row["item_description"], []).append(row)

    chains = {}
    for description, transfers in by_item.items():
        chain = []
        for transfer in transfers:
            from_id = transfer["from_user_id"]
            to_id = transfer["to_user_id"]

            if not chain:
                chain = [from_id, to_id]
                continue

            # Only the current holder may record the next handover.
            if chain[-1] != from_id:
                # Keep the most recent valid-looking handover from breaking
                # the dashboard when old data is inconsistent.
                chain = [from_id, to_id]
                continue

            # Returning to somebody already in the chain removes everyone
            # after that person from the active custody chain.
            if to_id in chain:
                chain = chain[: chain.index(to_id) + 1]
            else:
                chain.append(to_id)

        chains[description] = chain
    return by_item, chains


def get_item_state(item_description):
    """Return owner/origin, current holder, and custody chain for an item."""
    item_description = " ".join(item_description.strip().split())
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT
            transfers.id, transfers.from_user_id, transfers.to_user_id,
            transfers.item_description, transfers.transferred_at,
            sender.username AS from_username, receiver.username AS to_username
        FROM transfers
        JOIN users AS sender ON transfers.from_user_id = sender.id
        JOIN users AS receiver ON transfers.to_user_id = receiver.id
        WHERE transfers.item_description = ?
        ORDER BY transfers.id ASC
        """,
        (item_description,),
    ).fetchall()
    by_item, chains = _build_item_chains(rows)
    chain = chains.get(item_description, [])
    origin_id = rows[0]["from_user_id"] if rows else None
    current_holder_id = chain[-1] if chain else None
    conn.close()
    return {
        "exists": bool(rows),
        "origin_id": origin_id,
        "current_holder_id": current_holder_id,
        "chain": chain,
        "rows": by_item.get(item_description, []),
    }


def create_transfer(from_user_id, to_user_id, item_description):
    """Record a physical handover and fulfill matching return requests."""
    item_description = " ".join(item_description.strip().split())
    if not item_description:
        return False, "Please enter an item description."
    if from_user_id == to_user_id:
        return False, "The borrower must be another TraceBorrow user."

    conn = get_connection()
    rows = _all_transfers(conn)
    _, chains = _build_item_chains(rows)
    chain = chains.get(item_description)

    if chain and chain[-1] != from_user_id:
        holder = conn.execute(
            "SELECT username FROM users WHERE id = ?", (chain[-1],)
        ).fetchone()
        holder_name = holder["username"] if holder else "another user"
        conn.close()
        return False, f"This item is currently with {holder_name}."

    conn.execute(
        """
        INSERT INTO transfers (from_user_id, to_user_id, item_description)
        VALUES (?, ?, ?)
        """,
        (from_user_id, to_user_id, item_description),
    )

    # A pending request is fulfilled once the requested item reaches the
    # person who asked for it.
    conn.execute(
        """
        UPDATE return_requests
        SET status = 'FULFILLED'
        WHERE item_description = ?
          AND requester_id = ?
          AND status = 'PENDING'
        """,
        (item_description, to_user_id),
    )

    conn.commit()
    conn.close()
    return True, "Transfer recorded successfully."


def _dashboard_chains(conn):
    rows = _all_transfers(conn)
    return _build_item_chains(rows)[1]


def get_dashboard_counts(user_id):
    """Count only items borrowed from others and items owned by the user that are away.

    The first person in a custody chain is treated as the item's owner/origin.
    Having your own item returned to you therefore does not count as
    "Currently With Me". That counter is for items you are holding that
    originated with another user. Likewise, "With Other People" counts only
    the user's own items that are currently held by someone else.
    """
    conn = get_connection()
    chains = _dashboard_chains(conn)
    with_me = 0
    with_others = 0

    for chain in chains.values():
        if not chain:
            continue

        origin_id = chain[0]
        current_holder_id = chain[-1]

        # Borrowed item: it belongs to someone else and is currently with me.
        if current_holder_id == user_id and origin_id != user_id:
            with_me += 1

        # Lent item: it originated with me and is currently with someone else.
        elif origin_id == user_id and current_holder_id != user_id:
            with_others += 1

    conn.close()
    return {"with_me": with_me, "with_others": with_others}


def get_user_lending_history(user_id):
    """Show the full custody trail for items that originated with this user."""
    conn = get_connection()
    rows = _all_transfers(conn)
    origin_by_item = {}
    for row in rows:
        origin_by_item.setdefault(row["item_description"], row["from_user_id"])

    result = [
        row for row in rows
        if origin_by_item.get(row["item_description"]) == user_id
    ]
    result.reverse()
    conn.close()
    return result


def get_user_borrowing_history(user_id):
    """Show every handover that another user made directly to this user."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT
            transfers.id, transfers.transferred_at, transfers.item_description,
            lender.username AS lender_username
        FROM transfers
        JOIN users AS lender ON transfers.from_user_id = lender.id
        WHERE transfers.to_user_id = ?
        ORDER BY transfers.id DESC
        """,
        (user_id,),
    ).fetchall()
    conn.close()
    return rows


def create_return_request(requester_id, item_description):
    """Ask the current holder to return an item to the requester."""
    item_description = " ".join(item_description.strip().split())
    if not item_description:
        return False, "Please enter the item description."

    state = get_item_state(item_description)
    if not state["exists"]:
        return False, "That item is not in TraceBorrow yet."

    if requester_id not in state["chain"]:
        return False, "You are not part of this item's custody history."

    current_holder_id = state["current_holder_id"]
    if current_holder_id == requester_id:
        return False, "This item is already with you."

    conn = get_connection()
    existing = conn.execute(
        """
        SELECT id FROM return_requests
        WHERE item_description = ? AND requester_id = ? AND status = 'PENDING'
        """,
        (item_description, requester_id),
    ).fetchone()
    if existing:
        conn.close()
        return False, "A return request for this item is already pending."

    conn.execute(
        """
        INSERT INTO return_requests (item_description, requester_id, target_user_id)
        VALUES (?, ?, ?)
        """,
        (item_description, requester_id, current_holder_id),
    )
    conn.commit()
    conn.close()
    return True, "Return request sent to the current holder."


def get_pending_return_requests(user_id):
    """Return pending requests that should notify this user."""
    conn = get_connection()
    rows = conn.execute(
        """
        SELECT
            return_requests.id, return_requests.item_description,
            return_requests.requested_at,
            requester.username AS requester_username
        FROM return_requests
        JOIN users AS requester ON return_requests.requester_id = requester.id
        WHERE return_requests.target_user_id = ?
          AND return_requests.status = 'PENDING'
        ORDER BY return_requests.id DESC
        """,
        (user_id,),
    ).fetchall()
    conn.close()
    return rows
