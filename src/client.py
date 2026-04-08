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
            self.client.sendall((json.dumps({"type": "CONNECT"}) + '\n').encode('utf-8'))
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
        # If it's opponent turn, display the text
        if not self.my_turn:
            self.status_label.config(text="Not your turn!")
            return

        # If users don't select any cells
        if self.selected_row is None or self.selected_col is None:
            return

        #Check if it's only 1 character and letter only
        letter = self.entry.get().upper()
        if len(letter) > 1 or not letter.isalpha() or letter == "":
            self.status_label.config(text="Invalid guess! Please type only 1 letter")
            return

        # Users attempt to guess a letter
        try:
            message = json.dumps({"type": "UPDATE", "row": self.selected_row, "col": self.selected_col, "letter": letter}) + '\n'
            self.client.sendall(message.encode('utf-8'))
            # clear input box after sending
            self.entry.delete(0, tk.END)
        except:
            self.status_label.config(text = "Failed to send move")

    def start_client(self):
        while True:
            try:
                # Await data broadcasted from the GameSession server thread
                data = self.client.recv(1024).decode('utf-8')
                if not data: continue

                # TCP STREAM BUFFERING FIX:
                # OS-level TCP buffers might combine multiple JSON packets into one string.
                # We split by the predefined '\n' boundary to process them sequentially.
                # handle multiple messages
                messages = data.strip().split("\n")
                for msg in messages:
                    if not msg: break

                    #Deserialize the JSON packet
                    msg = json.loads(msg)
                    
                    # Action: Waiting for another opponent to join
                    if msg["type"] == "WAIT":
                        self.status_label.config(text=f"Connected! Waiting for opponents to join...")

                    # Action: Initial Role Assignment
                    elif msg["type"] == "WELCOME":
                        print("Received WELCOME")
                        self.player_num = int(msg["player"])
                        self.my_turn = (self.player_num == 1)
                        self.update_status()

                    # Action: Game Start
                    elif msg["type"] == "START":
                        self.status_label.config(text=f"Game started! You are Player {self.player_num}")
                        self.update_status()
                    
                    # Action: Show clues
                    # TODO: implement clues properly, doesn't show down clues seperately
                    elif msg["type"] == "CLUES":
                        clues_str = msg["clues"]
                        self.clues = clues_str.split("|")
                        self.update_clue()

                    # Action: Game state Update
                    elif msg["type"] == "UPDATE":
                        row = msg['row']
                        col = msg['col']
                        letter = msg['letter']
                        self.grid_buttons[row][col].config(text = letter)

                    # Action: Change turn and update who turn it is
                    elif msg["type"] == "TURN":
                        turn_player = msg['player']
                        self.my_turn = (turn_player == self.player_num)
                        self.update_status()

                    # Action: Notify the incorrect guess
                    elif msg["type"] == "ERROR":
                        self.status_label.config(text=msg['message'])

                    # Action: Game end and notify users
                    elif msg["type"] == "GAME_END":
                        # Convert scores from str -> int
                        score1 = int(msg['player1_score'])
                        score2 = int(msg['player2_score'])

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
            except Exception as e:
                print("Error:", e)
                break

        # Close the connect and destroy the window
        self.client.close()
        self.root.destroy() 

if __name__ == "__main__":
    Crossword()