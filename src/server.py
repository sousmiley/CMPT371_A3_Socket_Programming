"""
CMPT 371 A3: Multiplayer Crossword Server
Architecture: *CHANGE*TCP Sockets with Multithreaded Session Management
References: 
Socket boilerplate adapted from "TCP Echo Server" tutorial.
"""

import json
import socket
import threading
import json

# Server configuration
HOST = '127.0.0.1'
PORT = 5050
# If 5050 doesn't work, try 5555
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

# TODO: Clues need to show up serperately for down 
crossword_clues = [
    "ACROSS: Not to. DOWN: Disdain",
    "ACROSS: Aromatic wood. DOWN: Hi",
    "ACROSS: Oil. DOWN: Bye",
    "ACROSS: Itchy dog. DOWN: Belly button",
    "ACROSS: Basketball offenses. DOWN: Long locks"
]

def send(conn, data):
    conn.sendall((json.dumps(data) + "\n").encode())

# def check_winner(board):
#     """
#     Basic win and draw validation.
#     Enforces the "Single Source of Truth" rule: the server calculates wins 
#     so clients cannot cheat by modifying their local memory.
#     """

def game_session(conn_p1, conn_p2):
    """
    Isolated game loop for two matched players running on a background thread.
    This guarantees concurrent sessions do not block each other.
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
            current_row.append(EMPTY)  # '_' represents an empty cell
        grid.append(current_row)
    
    scores = {}
    scores[1] = 0
    scores[2] = 0

    turn = 1 # Player 1 goes first
    
    for msg in [conn_p1,conn_p2]:
        send(msg, {"type" : "CLUES", "clues" : crossword_clues})
        send(msg, {"type" : "START"} )

    send(conn_p1, {"type" : "TURN", "player":1})
    send(conn_p2, {"type" : "TURN", "player":1})

    # Map roles to their respective socket objects
    sockets = {1: conn_p1, 2: conn_p2}
    
    while True:
        active_socket = sockets[turn]
        # Block and wait for the active player to send their move
        try:
            data = active_socket.recv(1024).decode('utf-8')
        except ConnectionResetError:
            # If client crashes
            print("Client disconnected unexpectedly")
            break
        
        # If multiple messages arrive buffered together in the TCP stream, 
        # we only process the first valid one using the \n boundary.
        messages = data.split("\n")
        for msg_str in messages:
            msg_str = msg_str.strip()
            if not msg_str:
                continue
            try:
                msg = json.loads(msg_str)
            except json.JSONDecodeError:
                # an empty string was returned
                print(f"[WARNING] Incorrect formatted JSON: {msg_str}")
                continue
        
        # Protocol: Process the "GUESS" action
        if msg["type"] == "GUESS":
            row, col, letter = msg["row"], msg["col"], msg["letter"]
            # Update authoritative state
            if grid[row][col] != EMPTY:
                continue
            
            # If user guesses correctly
            if crossword_sol[row][col] == letter:
                grid[row][col] = letter
                scores[turn] += 1

                # update both players
                for conn in [conn_p1, conn_p2] :
                    send(conn, {"type" : "UPDATE", "row" : row, "col": col, "letter" : letter})

                # Check for game status, are there empty cells 
                #           or is grid complete (aka game over)
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
                        send(conn, {
                            "type": "GAME_END",
                            "scores": {"1": scores[1], "2": scores[2]}
                            }
                        )
                    return

                # switch player's turns
                if turn == 1: #p1 -> p2
                    turn = 2
                else: # p2->p1
                    turn = 1
                for conn in [conn_p1, conn_p2] :
                    send(conn, {"type" : "TURN", "player": turn})
            else :
                send(active_socket, {
                    "type": "ERROR",
                    "message": "Incorrect letter! Try again."
                })
    # Safely close the sockets when the session ends
    print("SESSION END Closing sockets safely, session has ended")
    conn_p1.close()
    conn_p2.close()

def start_server():
    """
    Main server event loop. 
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