"""
CMPT 371 A3: Multiplayer Crossword Server
Architecture: TCP Sockets with Multithreaded Session Management
References: 
Socket boilerplate adapted from "TCP Echo Server" tutorial.
"""

import json
import socket
import threading

# Server configuration
HOST = '127.0.0.1'
PORT = 5050
SIZE = 5
NUM_PLAYERS = 2
EMPTY ='_'
# Matchmaking Queue: Temporarily holds connected client sockets until 
# two players are available to form a GameSession.
matchmaking_queue = []

crossword_sol = [
    ['S','H','A','N','T'],
    ['C','E','D','A','R'],
    ['O','L','I','V','E'],
    ['F','L','E','E','S'],
    ['F','O','U','L','S']
]

crossword_clues_across = [
    "Not to",
    "Aromatic wood",
    "Oil",
    "Itchy dog",
    "Basketball offenses"
]

crossword_clues_down = [
    "Disdain",
    "Hi",
    "Bye",
    "Belly button",
    "Long locks"
]

def send(conn, data):
    """
    Sends JSON message to a client socket.
    """
    try:
        conn.sendall((json.dumps(data) + "\n").encode())
        return True
    except (BrokenPipeError, ConnectionResetError, OSError):
        return False

def disconnect_player(current_turn, sockets):
    """
    Handle player disconnection.
    """
    # Find which player left and disconnect
    if current_turn == 1:
        other_turn = 2
    else:
        other_turn = 1
    other_socket = sockets[other_turn]

    # Protocol: Disconnected
    try:
        send(other_socket, {
            "type": "DISCONNECTED",
            "message": "Opponent disconnected!"
        })
    except Exception as e:
        print(f"[ERROR] Failed to notify player {other_turn}, {e}")
    
    # Close both sockets
    for s in sockets.values():
        s.close()

def game_session(conn_p1, conn_p2):
    """
    Runs an isolated game session between two matched players on a background thread.
    Guarantees concurrent sessions do not block each other.
    """
    # Protocol: Assign roles using the "WELCOME" message.
    # Note: \n is appended to act as a TCP message boundary.
    send(conn_p1, {"type":"WELCOME","player":1})
    send(conn_p2, {"type":"WELCOME","player":2})
    
    # Initialize the game state
    grid = []
    for row in range(SIZE):
        current_row = []
        for col in range(SIZE):
            current_row.append(EMPTY)
        grid.append(current_row)
    
    scores = {}
    scores[1] = 0
    scores[2] = 0

    current_turn = 1 # Player 1 starts
    
    for conn in [conn_p1, conn_p2]:
        # Protocol: Show clues to both players
        if not send(conn, {
            "type": "CLUES",
            "across": crossword_clues_across,
            "down": crossword_clues_down
        }):
            return
        # Protocol: Game start
        if not send(conn, {"type": "START"}):
            return
    
    # Protocol: Tell both players it's Player 1's turn
    send(conn_p1, {"type" : "TURN", "player":1})
    send(conn_p2, {"type" : "TURN", "player":1})

    # Map roles to their respective socket objects
    sockets = {1: conn_p1, 2: conn_p2}
    
    try:
        while True:
            active_socket = sockets[current_turn]
            # Block and wait for the active player to send their move
            try:
                data = active_socket.recv(1024).decode('utf-8')
                if not data: 
                    print(f"[DISCONNECTED] Player {current_turn} disconnected!")
                    disconnect_player(current_turn, sockets)
                    return
            except ConnectionResetError:
                # If client crashes
                print("Client disconnected unexpectedly")
                disconnect_player(current_turn, sockets)
                return
            
            # Multiple messages may arrive buffered together in the TCP stream, 
            # process each message using the \n boundary.
            messages = data.split("\n")
            for msg_str in messages:
                msg_str = msg_str.strip()
                if not msg_str:
                    continue
                try:
                    msg = json.loads(msg_str)
                except json.JSONDecodeError:
                    # Incorrectly formatted JSON message
                    print(f"[WARNING] Incorrect formatted JSON: {msg_str}")
                    continue
            
                # Protocol: Process the "GUESS" action
                if msg["type"] == "GUESS":
                    row, col, letter = msg["row"], msg["col"], msg["letter"]
                    # Update authoritative state
                    if grid[row][col] != EMPTY:
                        send(active_socket, {
                            "type": "ERROR",
                            "message": "Cell already filled!"
                        })
                        continue
                    
                    # If user guesses correctly
                    if crossword_sol[row][col] == letter:
                        grid[row][col] = letter
                        scores[current_turn] += 1
    
                        send(active_socket, {
                            "type": "MESSAGE",
                            "text": "Correct Guess!"
                        })

                        # Update both players
                        for conn in [conn_p1, conn_p2] :
                            send(conn, {"type" : "UPDATE", "row" : row, "col": col, "letter" : letter})
                    else:
                        # Protocol: Handle incorrect guess
                        send(active_socket, {
                            "type": "ERROR",
                            "message": "Invalid letter!"
                        })

                # Check for game status, are there empty cells 
                # or is grid complete (aka game end)
                all_filled = True
                for row in range(SIZE):
                    for col in range(SIZE):
                        if grid[row][col] == EMPTY:
                            all_filled = False
                            break
                    if not all_filled:
                        break

                if all_filled:
                    for conn in [conn_p1, conn_p2]:
                        if scores[1] > scores[2]:
                            result = "Player 1 won!"
                        elif scores[2] > scores[1]:
                            result = "Player 2 won!"
                        else:
                            result = "Draw!"
                        send(conn, {
                            "type": "GAME_END",
                            "result": result,
                            "scores": {"1": scores[1], "2": scores[2]}
                            }
                        )
                    return

                # Switch player's turns
                if current_turn == 1: #p1 -> p2
                    current_turn = 2
                else: # p2->p1
                    current_turn = 1
                for conn in [conn_p1, conn_p2] :
                    send(conn, {"type" : "TURN", "player": current_turn})
    finally:
        # Safely close the sockets when the session ends
        conn_p1.close()
        conn_p2.close()

def start_server():
    """
    Main server loop. 
    Binds the socket and populates the matchmaking queue.
    """
    # Initialize an IPv4 (AF_INET) TCP (SOCK_STREAM) socket
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((HOST, PORT))
    server.listen()
    print(f"[START] Server is listening on {HOST}:{PORT}")
    
    try:
        while True:
            # Block until a new client connects
            conn, addr = server.accept()
            print(f"[CONNECTED] {addr}")
            data = conn.recv(1024).decode('utf-8')
            messages = data.split("\n")
            for msg_str in messages:
                msg_str = msg_str.strip()
                if not msg_str:
                    continue
                msg = json.loads(msg_str)
            
            # Protocol: Check for the initial "CONNECT" handshake
            if msg["type"] == "CONNECT":
                matchmaking_queue.append(conn)
                print(f"[QUEUE] Player added. Waiting # of players : {NUM_PLAYERS - len(matchmaking_queue)}")
                
                # Session Management: When 2 players are queued, match them up
                if len(matchmaking_queue) >= 2:
                    player_1 = matchmaking_queue.pop(0)
                    player_2 = matchmaking_queue.pop(0)
                    # Spawn an isolated GameSession thread for the matched pair
                    print("[MATCH] 2 Players found. Starting new game session.")
                    threading.Thread(target=game_session, args=(player_1, player_2)).start()
    except KeyboardInterrupt:
        # Graceful shutdown on Ctrl+C
        print("\n[SHUTDOWN] Server closing...")
        server.close()

if __name__ == "__main__":
    start_server()