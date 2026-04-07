"""
CMPT 371 A3: Multiplayer Crossword Client
Architecture: TCP Protocol
References: 
https://stackoverflow.com/questions/16332224/placing-a-crossword-puzzle-into-a-tkiner-in-python-3-2
https://docs.python.org/3/library/threading.html
https://stackoverflow.com/questions/42222425/python-sockets-multiple-messages-on-same-connection
"""

import json
import socket
import threading
import tkinter as tk
from tkinter import messagebox

HOST = '127.0.0.1'
PORT = 5050
# If 5050 doesn't work, try 5555
SIZE = 5
EMPTY = '_'

class Crossword:
    def __init__(self):
        # intialize the client by:
        # connecting to server, building gui, threading
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.client.connect((HOST, PORT))
            self.client.sendall("CONNECT\n".encode())
        except Exception as e:
            print("Unable to connect to server ", e)
            return
        
        # game vars
        self.player_num = 0
        self.my_turn = False
        self.selected_row = None
        self.selected_col = None
        # TODO : present clues
        self.clues = [""] *SIZE
        #tkinter vars
        self.root = tk.Tk()
        self.root.title("Multiplayer Crossword!")
        self.grid_buttons = []
        self.build_grid()
        self.build_controls()
        # receive messages, ref:https://docs.python.org/3/library/threading.html
        threader = threading.Thread(target=self.start_client)
        threader.start()

        self.root.mainloop()
    
    def build_grid(self):
        # crossword grid using buttons
        for row in range(SIZE):
            current_row = []
            for col in range(SIZE):
                btn = tk.Button(
                    self.root,
                    text = EMPTY,
                    width = SIZE,
                    height = 2,
                    font = ("Arial", 16),
                    command = lambda r= row, c= col: self.select_cell(r, c)
                )

                btn.grid(row= row, column= col, padx= SIZE, pady = SIZE)
                current_row.append(btn)
            self.grid_buttons.append(current_row)

    def build_controls(self):
        # TODO : Center input box and subit button
        # Input box
        self.entry = tk.Entry(self.root)
        self.entry.grid(row=SIZE, column=0, columnspan=2, pady=10)

        # Submit button
        self.submit_btn = tk.Button(self.root, text="Submit Letter", command=self.send_move)
        self.submit_btn.grid(row=SIZE, column=2, columnspan=2, pady=10)

        # Status label
        self.status_label = tk.Label(self.root, text="Waiting for game...")
        self.status_label.grid(row=SIZE + 1, column=0, columnspan=SIZE)

        # Clue display
        self.clue_label = tk.Label(self.root, text="Select a row to see clue", fg="blue")
        self.clue_label.grid(row=SIZE + 2, column=0, columnspan=SIZE)
    
    def update_clue(self):
        if self.selected_row is not None:
            clue_text = self.clues[self.selected_row]
            self.clue_label.config(text=f"Clue: {clue_text}")

    def select_cell(self, row, col):
        self.selected_row = row
        self.selected_col = col
        self.update_clue_display()
        self.update_status() # update player status, current selected cell

    def update_clue_display(self):
        if self.selected_row is not None:
            clue_text = self.clues[self.selected_row]
            self.clue_label.config(text=f"Clue : {clue_text}")

    def update_status(self):
        if self.my_turn:
            turn_text = "Your Turn"
        else:
            turn_text = "Opponent's Turn"

        if self.selected_row is not None:
            self.status_label.config(
                text = f"Player {self.player_num} | {turn_text} | Selected : ({self.selected_row}, {self.selected_col})"
            )
        else:
            self.status_label.config(
                text = f"Player {self.player_num} | {turn_text}"
            )

    def send_move(self):
        # TODO: improve checking (only one letter should be allowed)
        if not self.my_turn:
            self.status_label.config(text="Not your turn!")
            return

        if self.selected_row is None:
            return

        letter = self.entry.get().upper()
        if letter == "": # empty
            return

        try:
            message = f"GUESS {self.selected_row} {self.selected_col} {letter}\n"
            self.client.send(message.encode())
            # clear input box after sending
            self.entry.delete(0, tk.END)

        except:
            self.status_label.config(text = "Failed to send move")

    def start_client(self):
        while True:
            try:
                # Await data broadcasted from the GameSession server thread
                data = self.client.recv(1024).decode()

                # TCP STREAM BUFFERING FIX:
                # OS-level TCP buffers might combine multiple JSON packets into one string.
                # We split by the predefined '\n' boundary to process them sequentially.
                # handle multiple messages
                messages = data.strip().split("\n")
                for msg in messages:
                    if not msg: break

                    #Deserialize the JSON packet
                    # msg = json.loads(msg)
                    
                    # Action: Waiting for another opponent to join
                    if msg.startswith("WAIT"):
                        self.status_label.config(text=f"Connected! Waiting for opponents to join...")

                    # Action: Initial Role Assignment
                    elif msg.startswith("WELCOME"):
                        print("Received WELCOME")
                        parts = msg.split()
                        if len(parts) >= 2:
                            player_number_string = parts[1]   # get the second part
                            self.player_num = int(player_number_string)  # convert to integer
                            # Determine if it's this player's turn
                            if self.player_num == 1:
                                # Player 1 always starts first
                                self.my_turn = True
                            else:
                                self.my_turn = False
                            # Update UI to reflect player + turn
                            self.update_status()
                        else:
                            print("ERROR: Incorrect formatted WELCOME message :", msg)

                    # Action: Game Start
                    elif msg.startswith("START"):
                        self.status_label.config(text=f"Game started! You are Player {self.player_num}")
                        self.update_status()
                    
                    # Action: Show clues
                    # TODO: implement clues properly, doesn't show down clues seperately
                    elif msg.startswith("CLUES"):
                        _, clues_str = msg.split(maxsplit=1)
                        self.clues = clues_str.split("|")
                        self.update_clue()

                    # Action: Game state Update
                    elif msg.startswith("UPDATE"):
                        parts = msg.split()
                        row = int(parts[1])
                        col = int(parts[2])
                        letter = parts[3]
                        self.grid_buttons[row][col].config(text = letter)

                    # Action: Change turn and update who turn it is
                    elif msg.startswith("TURN"):
                        turn_player = int(msg.split()[1])
                        self.my_turn = (turn_player == self.player_num)
                        self.update_status()

                    # Action: Game end and notify users
                    elif msg.startswith("GAME_END"):
                        print("Received Game over")
                        parts = msg.split()
                        if len(parts) >= 3:
                            score1_str = parts[1] # get score1 as string
                            score2_str = parts[2] # get score2 as string

                            # Convert scores from str -> int
                            score1 = int(score1_str)
                            score2 = int(score2_str)

                            if score1 > score2:
                                winner = "Player 1"
                            elif score2 > score1:
                                winner = "Player 2"
                            else:
                                winner = "Tie"

                            # TODO: Ipmrove the results popup window
                            messagebox.showinfo(
                                "Game Over!",
                                "Scores:\n"
                                + "Player 1: " + str(score1) + "\n"
                                + "Player 2: " + str(score2) + "\n"
                                + "Winner: " + winner + ", congrats!"
                            )
                            # TODO : Game doesn't close after user closes game over window
                            self.root.destroy() 

                        else:
                            print("WARNING: Incorrect formatted GAME_END message :", msg)

            except Exception as e:
                print("Error:", e)
                break

if __name__ == "__main__":
    Crossword()

# def print_board(board):
#     """
#     Displays the board with coordinates and clean Unicode box-drawing characters.
#     """
#     # Column headers
#     print("\n    0   1   2 ")
#     print("  ┌───┬───┬───┐")
    
#     for i, row in enumerate(board):
#         # Row data with the row index on the left
#         print(f"{i} │ {row[0]} │ {row[1]} │ {row[2]} │")
        
#         # Row separators or the bottom border
#         if i < 2:
#             print("  ├───┼───┼───┤")
#         else:
#             print("  └───┴───┴───┘\n")

# def start_client():
#     """
#     Main client execution loop. Handles connection, JSON serialization/deserialization,
#     and user input routing.
#     """
#     # Initialize an IPv4 (AF_INET) TCP (SOCK_STREAM) socket
#     client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
#     client.connect((HOST, PORT))
    
#     # Handshake Protocol: Send initial connection request to join matchmaking
#     client.sendall(json.dumps({"type": "CONNECT"}).encode('utf-8'))
#     print("Connected. Waiting for opponent...")
    
#     my_role = None
    
#     while True:
#         # Await data broadcasted from the GameSession server thread
#         data = client.recv(1024).decode('utf-8')
            
#         # TCP STREAM BUFFERING FIX:
#         # OS-level TCP buffers might combine multiple JSON packets into one string.
#         # We split by the predefined '\n' boundary to process them sequentially.
#         for chunk in data.strip().split('\n'):
#             if not chunk: continue
#             # Deserialize the JSON packet
#             msg = json.loads(chunk)
            
#             # Action: Initial Role Assignment
#             if msg["type"] == "WELCOME":
#                 # Payload format is "Player X" or "Player O"
#                 my_role = msg["payload"][-1]
#                 print(f"Match found! You are Player {my_role}.")
                
#             # Action: Game State Update
#             elif msg["type"] == "UPDATE":
#                 print_board(msg["board"])
                
#                 # Check for termination conditions broadcasted by the server
#                 if msg["status"] != "ongoing":
#                     print(f"Game Over: {msg['status']}")
#                     client.close()
#                     sys.exit(0)
                    
#                 # Print whose turn it is
#                 if msg["turn"] == my_role:
#                     print("It's your turn!")
#                     # State Validation: Prompt for input only if the server says it is our turn
#                     r_str, c_str = input("Enter row and col (e.g., '1 1'): ").split()
                    
#                     # Protocol: Package coordinates into a MOVE packet.
#                     # Always append the \n boundary before encoding to bytes.
#                     move_msg = json.dumps({"type": "MOVE", "row": int(r_str), "col": int(c_str)}) + '\n'
#                     client.sendall(move_msg.encode('utf-8'))
#                 else:
#                     print("Waiting for opponent...")

#     client.close()

# if __name__ == "__main__":
#     start_client()