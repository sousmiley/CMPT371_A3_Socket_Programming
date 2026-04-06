"""
CMPT 371 A3: Multiplayer Crossword Server
Architecture: *CHANGE*TCP Sockets with Multithreaded Session Management
References: 
Socket boilerplate adapted from "TCP Echo Server" tutorial.
"""

import socket
import threading
import json

# Server configuration
HOST = '127.0.0.1'
PORT = 5050
# If 5050 doesn't work, try 5555
SIZE = 5
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
#     # Check rows and columns for a match
#     for i in range(3):
#         if board[i][0] == board[i][1] == board[i][2] != ' ': return board[i][0]
#         if board[0][i] == board[1][i] == board[2][i] != ' ': return board[0][i]

#     # Check diagonals
#     if board[0][0] == board[1][1] == board[2][2] != ' ': return board[0][0]
#     if board[0][2] == board[1][1] == board[2][0] != ' ': return board[0][2]

#     # Check for a draw (no empty spaces left)
#     if all(cell != ' ' for row in board for cell in row): return 'Draw'
#     return None

def game_session(conn_p1, conn_p2):
    """
    Isolated game loop for two matched players running on a background thread.
    This guarantees concurrent sessions do not block each other.
    """
    # Protocol: Assign roles using the "WELCOME" message.
    # Note: \n is appended to act as a TCP message boundary.
    conn_p1.sendall((json.dumps({"type": "WELCOME", "payload": "Player 1"}) + '\n').encode('utf-8'))
    conn_p2.sendall((json.dumps({"type": "WELCOME", "payload": "Player 2"}) + '\n').encode('utf-8'))
    
    # Initialize the game state
    # board = [[' ', ' ', ' '], [' ', ' ', ' '], [' ', ' ', ' ']]
    grid = []
    for row in range(SIZE):
        current_row = []
        for col in range(SIZE):
            current_row.append(EMPTY)  # '_' represents an empty cell
        grid.append(current_row)
    
    scores = {}
    scores[1] = 0
    scores[2] = 0

    turn = 1
    
    # Broadcast initial empty board to both players
    crossword_clues_msg = json.dumps({"type": "CLUES", "grid": grid, "turn": turn, "status": "ongoing"}) + "|".join(crossword_clues) + "\n"
    # crossword_clues_msg = "crossword_clues " + "|".join(crossword_clues) + "\n"

    # TODO: create a seperate function to send out messages since it's use so frequently
    conn_p1.sendall(crossword_clues_msg.encode('utf-8'))
    conn_p2.sendall(crossword_clues_msg.encode('utf-8'))

    # Start game message to conn_p1 and conn_p2?
    
    # Map roles to their respective socket objects
    sockets = {1: conn_p1, 2: conn_p2}
    
    while True:
        active_socket = sockets[turn]
        # Block and wait for the active player to send their move
        data = active_socket.recv(1024).decode('utf-8')
        if not data:
            break
        
        # If multiple messages arrive buffered together in the TCP stream, 
        # we only process the first valid one using the \n boundary.
        message = data.strip().split('\n')[0]
        msg = message.split()
        
        # Protocol: Process the "MOVE" action
        if msg[0] == "MOVE":
            row, col, letter = int(msg[1]), int(msg[2]), msg[3].upper()
            # Update authoritative state
            if grid[row][col] != EMPTY:
                active_socket.sendall("INVALID Cell already filled\n".encode())
                continue

            if crossword_sol[row][col] == letter:
                grid[row][col] = letter
                # How we measure score can be changed
                # Currently it adds a point for correct letter per player
                scores[turn] += 1

                # update both players
                conn_p1.sendall((f"UPDATE {row} {col} {letter}" + "\n").encode())
                conn_p2.sendall((f"UPDATE {row} {col} {letter}" + "\n").encode())

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

                # if grid has no empty cells, the game is finhised
                if all_filled:
                    conn_p1.sendall((f"GAME_OVER {scores[1]} {scores[2]}" + "\n").encode())
                    conn_p2.sendall((f"GAME_OVER {scores[1]} {scores[2]}" + "\n").encode())
                    break

                # switch player's turns
                if turn == 1: #p1 -> p2
                    turn = 2
                else: # p2->p1
                    turn = 1
                conn_p1.sendall((f"TURN {turn}" + "\n").encode())
                conn_p2.sendall((f"TURN {turn}" + "\n").encode())
            else :
                active_socket.sendall("INVALID! Wrong letter\n".encode())
    # Safely close the sockets when the session ends
    print("Closing sockets safely, session has ended")
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
    print(f"[STARTING] Server is listening on {HOST}:{PORT}")
    
    try:
        while True:
            # Block until a new client connects
            conn, addr = server.accept()
            print(f"[CONNECTED] {addr}")
            data = conn.recv(1024).decode('utf-8')
            
            # Protocol: Check for the initial "CONNECT" handshake
            # TODO : show handshaking
            if "CONNECT" in data:
                matchmaking_queue.append(conn)
                print(f"[QUEUE] Player added. Waiting # of players : {len(matchmaking_queue)}")
                
                # Session Management: When 2 players are queued, match them up
                if len(matchmaking_queue) >= 2:
                    player_1 = matchmaking_queue.pop(0)
                    player_2 = matchmaking_queue.pop(0)
                    # Spawn an isolated GameSession thread for the matched pair
                    print("[MATCH] 2 Players found. Spawning GameSession thread.")
                    threading.Thread(target=game_session, args=(player_1, player_2)).start()
    except KeyboardInterrupt:
        # Graceful shutdown on Ctrl+C
        print("\n[SHUTDOWN] Server closing...")
    finally:
        server.close()

if __name__ == "__main__":
    start_server()