"""
CMPT 371 A3: Multiplayer Crossword Server
Architecture: *CHANGE*TCP Sockets with Multithreaded Session Management
References: 
Socket boilerplate adapted from "TCP Echo Server" tutorial.
"""

import json
import socket
import threading

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
    ['S', 'H', 'A', 'N', 'T'],
    ['C', 'E', 'D', 'A', 'R'],
    ['O', 'L', 'I', 'V', 'E'],
    ['F', 'L', 'E', 'E', 'S'],
    ['F', 'O', 'U', 'L', 'S']
]

# TODO: Clues need to show up serperately for down 
crossword_clues = [
    "ACROSS: Not to. DOWN: Disdain",
    "ACROSS: Aromatic wood. DOWN: Hi",
    "ACROSS: Oil. DOWN: Bye",
    "ACROSS: Itchy dog. DOWN: Belly button",
    "ACROSS: Basketball offenses. DOWN: Long locks"
]

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
    conn_p1.sendall((json.dumps({"type": "WELCOME", "player": 1}) + '\n').encode('utf-8'))
    conn_p2.sendall((json.dumps({"type": "WELCOME", "player": 2}) + '\n').encode('utf-8'))
    
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
    
    # Broadcast clues to both players
    crossword_clues_msg = json.dumps({"type": "CLUES", "clues": "|".join(crossword_clues)}) + '\n'

    conn_p1.sendall(crossword_clues_msg.encode('utf-8'))
    conn_p2.sendall(crossword_clues_msg.encode('utf-8'))

    # Encapsulate message send outs into broadcast function since it's use so frequently
    def broadcast_message(msg: dict):
        conn_p1.sendall((json.dumps(msg) + "\n").encode('utf-8'))
        conn_p2.sendall((json.dumps(msg) + "\n").encode('utf-8'))
    
    broadcast_message({"type": "START"})
    broadcast_message({"type": "TURN", "player": 1})

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
        message = data.strip().split('\n')[0]
        msg = json.loads(message)
        
        # Protocol: Process the "UPDATE" action
        if msg['type'] == "UPDATE":
            # This matches the : {“type”: "UPDATE", “row”: 1, “col”: 2, “letter”: “A”}
            row, col, letter = int(msg['row']), int(msg['col']), msg['letter'].upper()
            # Update authoritative state
            if grid[row][col] != EMPTY:
                active_socket.sendall("INVALID Cell already filled\n".encode())
                continue
            
            # If user guesses correctly
            if crossword_sol[row][col] == letter:
                grid[row][col] = letter
                # How we measure score can be changed
                # Currently it adds a point for correct letter per player
                scores[turn] += 1

                # update both players
                # {“type”: “UPDATE”, “row”: 1, “col”: 2, “letter”: A}
                broadcast_message({"type": "UPDATE", "row": row, "col": col, "letter": letter})
            else:
                # Notify users if they guess wrong
                broadcast_message({"type": "INVALID", "message": "Invalid guess! Try again"})

            # Check for game status, are there empty cells 
            #           or is grid complete (aka game over)
            all_filled = True
            for row in range(SIZE):          # go through each row
                for col in range(SIZE):      # go through each column
                    if grid[row][col] == EMPTY:  # an empty cell was located
                        all_filled = False
                        break              # stop checking row

                if not all_filled:
                    break                  # stop checking the grid

            # if grid has no empty cells, the game is finished
            if all_filled:
                broadcast_message({"type": "GAME_END", "player1_score": scores[1], "player2_score": scores[2]})
                break

            # switch player's turns
            if turn == 1: #p1 -> p2
                turn = 2
            else: # p2->p1
                turn = 1
            broadcast_message({"type": "TURN", "player": turn})
        else :
            active_socket.sendall("ERROR Invalid Move! Try again\n".encode())
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
            

            try:
                if "CONNECT" in data:
                    # Add the client to the matchmaking queue
                    matchmaking_queue.append(conn)
                    print(f"[QUEUE] Player added. Waiting # of players : {NUM_PLAYERS - len(matchmaking_queue)}")

                    #Protocol: "WAIT" for opponent when only 1 player is in the queue
                    if len(matchmaking_queue) == 1:
                        conn.sendall((json.dumps({"type": "WAIT"}) + '\n').encode('utf-8'))
                    
                    # Session Management: When 2 players are queued, match them up
                    if len(matchmaking_queue) >= 2:
                        player_1 = matchmaking_queue.pop(0)
                        player_2 = matchmaking_queue.pop(0)
                        # Spawn an isolated GameSession thread for the matched pair
                        print("[MATCH] 2 Players found. Starting new game session.")
                        threading.Thread(target=game_session, args=(player_1, player_2)).start()
                else:
                    raise ValueError("ERROR! Invalid handshake.")
            except Exception:
                # Send error when it's not CONNECTED
                conn.sendall("ERROR! Invalid handshake\n".encode())
                conn.close()
    except KeyboardInterrupt:
        # Graceful shutdown on Ctrl+C
        print("\n[SHUTDOWN] Server closing...")
    finally:
        server.close()

if __name__ == "__main__":
    start_server()