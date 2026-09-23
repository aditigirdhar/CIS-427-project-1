import socket
import sqlite3
# Connect to the SQLite database
connection = sqlite3.connect("pokemon.db")
cursor = connection.cursor()


# Create the Users table if it does not already exist
cursor.execute("""
CREATE TABLE IF NOT EXISTS Users (
    ID INTEGER PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    user_name TEXT NOT NULL,
    password TEXT,
    usd_balance DOUBLE NOT NULL,
    is_root INTEGER NOT NULL DEFAULT 0
)
""")
connection.commit()


# Create the Pokemon_cards table if it does not already exist
cursor.execute("""
CREATE TABLE IF NOT EXISTS Pokemon_cards (
    ID INTEGER PRIMARY KEY,
    card_name TEXT NOT NULL,
    card_type TEXT NOT NULL,
    rarity TEXT NOT NULL,
    count INTEGER,
    owner_id INTEGER,
    FOREIGN KEY (owner_id) REFERENCES Users(ID)
)
""")
connection.commit()
# Create an initial root user if the database has no users
cursor.execute("SELECT COUNT(*) FROM Users")
user_count = cursor.fetchone()[0]

if user_count == 0:
    cursor.execute("""
    INSERT INTO Users
    (first_name, last_name, user_name, password, usd_balance, is_root)
    VALUES (?, ?, ?, ?, ?, ?)
    """, ("John", "Doe", "j_doe", "Passwrd4", 100.00, 1))
    connection.commit()
    print("Initial user created.")

# Configure the server socket and listening port
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 42701

server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server_socket.bind((SERVER_HOST, SERVER_PORT))
server_socket.listen(1)

print("Server is waiting for a connection...")

# Keep accepting clients until the server receives a valid SHUTDOWN command
shutdown = False

while not shutdown:

    client_socket, client_address = server_socket.accept()

    print("Client connected:", client_address)

    message = client_socket.recv(1024).decode().strip()

    print("Received from client:", message)

    parts = message.split()

    # BALANCE
    if len(parts) == 2 and parts[0].upper() == "BALANCE":
        try:
            user_id = int(parts[1])

            cursor.execute(
                "SELECT first_name, last_name, usd_balance FROM Users WHERE ID = ?",
                (user_id,)
            )

            user = cursor.fetchone()

            if user is None:
                response = f"400 User {user_id} doesn't exist"
            else:
                first_name, last_name, balance = user
                response = (
                    f"200 OK\n"
                    f"Balance for user {first_name} {last_name}: ${balance:.2f}"
                )

        except ValueError:
            response = "403 message format error"

    # LIST
    elif len(parts) == 2 and parts[0].upper() == "LIST":
        try:
            user_id = int(parts[1])

            cursor.execute(
                "SELECT ID, card_name, card_type, rarity, count, owner_id "
                "FROM Pokemon_cards WHERE owner_id = ?",
                (user_id,)
            )

            cards = cursor.fetchall()

            if not cards:
                response = f"200 OK\nNo Pokemon cards found for user {user_id}"
            else:
                response = "200 OK\n"
                response += "ID Card Name Type Rarity Count OwnerID\n"

                for card in cards:
                    card_id, card_name, card_type, rarity, count, owner_id = card

                    response += (
                        f"{card_id} {card_name} {card_type} "
                        f"{rarity} {count} {owner_id}\n"
                    )

        except ValueError:
            response = "403 message format error"

    # BUY
    elif len(parts) == 7 and parts[0].upper() == "BUY":
        try:
            card_name = parts[1]
            card_type = parts[2]
            rarity = parts[3]
            price = float(parts[4])
            count = int(parts[5])
            user_id = int(parts[6])

            if price < 0 or count <= 0:
                response = "403 message format error"
            else:
                cursor.execute(
                    "SELECT usd_balance FROM Users WHERE ID = ?",
                    (user_id,)
                )

                user = cursor.fetchone()

                if user is None:
                    response = f"400 User {user_id} doesn't exist"
                else:
                    balance = user[0]
                    total_cost = price * count

                    if balance < total_cost:
                        response = "400 Not enough USD balance"
                    else:
                        new_balance = balance - total_cost

                        cursor.execute(
                            """
                            INSERT INTO Pokemon_cards
                            (card_name, card_type, rarity, count, owner_id)
                            VALUES (?, ?, ?, ?, ?)
                            """,
                            (card_name, card_type, rarity, count, user_id)
                        )

                        cursor.execute(
                            "UPDATE Users SET usd_balance = ? WHERE ID = ?",
                            (new_balance, user_id)
                        )

                        connection.commit()

                        response = (
                            f"200 OK\n"
                            f"BOUGHT: New balance: {count} {card_name}. "
                            f"User USD balance ${new_balance:.2f}"
                        )

        except (ValueError, IndexError):
            response = "403 message format error"

    # SELL
    elif len(parts) == 5 and parts[0].upper() == "SELL":
        try:
            card_name = parts[1]
            sell_count = int(parts[2])
            price = float(parts[3])
            user_id = int(parts[4])

            if sell_count <= 0 or price < 0:
                response = "403 message format error"
            else:
                cursor.execute(
                    """
                    SELECT ID, count
                    FROM Pokemon_cards
                    WHERE card_name = ? AND owner_id = ?
                    """,
                    (card_name, user_id)
                )

                card = cursor.fetchone()

                if card is None:
                    response = f"400 User {user_id} doesn't own {card_name}"
                else:
                    card_id = card[0]
                    current_count = card[1]

                    if current_count < sell_count:
                        response = "400 Not enough Pokemon balance"
                    else:
                        total_sale = price * sell_count
                        new_count = current_count - sell_count

                        cursor.execute(
                            "UPDATE Users SET usd_balance = usd_balance + ? WHERE ID = ?",
                            (total_sale, user_id)
                        )

                        if new_count == 0:
                            cursor.execute(
                                "DELETE FROM Pokemon_cards WHERE ID = ?",
                                (card_id,)
                            )
                        else:
                            cursor.execute(
                                "UPDATE Pokemon_cards SET count = ? WHERE ID = ?",
                                (new_count, card_id)
                            )

                        connection.commit()

                        cursor.execute(
                            "SELECT usd_balance FROM Users WHERE ID = ?",
                            (user_id,)
                        )

                        new_balance = cursor.fetchone()[0]

                        response = (
                            f"200 OK\n"
                            f"SOLD: New balance: {new_count} {card_name}. "
                            f"User's balance USD ${new_balance:.2f}"
                        )

        except (ValueError, IndexError):
            response = "403 message format error"

    # QUIT
    elif len(parts) == 1 and parts[0].upper() == "QUIT":
        response = "200 OK\nGoodbye!"

    # SHUTDOWN
    elif len(parts) == 2 and parts[0].upper() == "SHUTDOWN":
        try:
            user_id = int(parts[1])

            cursor.execute(
                "SELECT is_root FROM Users WHERE ID = ?",
                (user_id,)
            )

            user = cursor.fetchone()

            if user is None:
                response = f"400 User {user_id} doesn't exist"

            elif user[0] != 1:
                response = "401 Unauthorized"

            else:
                response = "200 OK\nServer shutting down..."

                client_socket.sendall((response + "\n").encode())

                client_socket.close()

                shutdown = True
                continue

        except ValueError:
            response = "403 message format error"

    else:
        response = "400 invalid command"

    client_socket.sendall((response + "\n").encode())

    client_socket.close()

# Close the server socket and database connection
server_socket.close()
connection.close()

print("Server stopped.")
