# TraceBorrow

TraceBorrow is a simple web app for recording where a physically lent item goes. The physical handover happens outside the software; TraceBorrow only records it.

## Data model

Only three concepts exist in the database:

- `users` — registered users.
- `transfers` — every physical handover, with sender, receiver, item description, and timestamp.
- `return_requests` — simple requests asking the current holder to return an item.

There are no models, asset IDs, serial numbers, ownership fields, QR codes, approval workflows, or pending transfers.

## Dashboard

Each user sees two counters:

- **Currently With Me** — items that originated with another user and are currently held by the logged-in user. Your own item being returned to you is not counted here.
- **With Other People** — items that originated with the logged-in user and are currently held by someone else. Passing along someone else's borrowed item does not count here.

The dashboard also shows:

- **My Lending History** — the complete custody chain for items that originally started with the user.
- **My Borrowing History** — handovers where another user directly gave the item to the user.

Every history row shows both **date and time** in `AM/PM` format.

## Return requests

A user who previously had an item can choose **Request an item back**, enter the same item description, and send a request to the item's current holder. The current holder sees the request on their dashboard with the requester, item description, and request date/time. The return itself is still recorded through **+ Add New Transfer**.

When the item reaches the requester, any matching pending request is automatically marked fulfilled.

## Data persistence

The database is stored in `database/traceborrow.db` inside the TraceBorrow project folder. It is **not deleted when the server stops**. Registered accounts, transfers, and return requests therefore remain after restarting the server or shutting down the laptop.

The application also keeps a successful login session for up to 30 days. Use **Logout** when you want to end that session.

**Important:** Do not delete the `database` folder or `database/traceborrow.db` if you want to keep the saved data. Also keep the same project folder when restarting TraceBorrow.

## Run

On Windows, double-click `START_TraceBorrow.bat`, then open http://127.0.0.1:5000

## Tests

Run:

```bash
python -m unittest discover -s tests -v
```
