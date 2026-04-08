"""
CMPT 371 A3: Multiplayer Crossword Client
Architecture: TCP Protocol
References: 
https://stackoverflow.com/questions/16332224/placing-a-crossword-puzzle-into-a-tkiner-in-python-3-2
https://docs.python.org/3/library/threading.html
https://stackoverflow.com/questions/42222425/python-sockets-multiple-messages-on-same-connection
https://oneuptime.com/blog/post/2026-03-20-json-over-ipv4-sockets-python/view
https://beej.us/guide/bgnet/html/#close-and-shutdownget-outta-my-face
"""

import json
import socket
import threading
import tkinter as tk
from tkinter import messagebox
import json

HOST = '127.0.0.1'
PORT = 5050
# If 5050 doesn't work, try 5555
SIZE = 5
EMPTY = '_'

class Crossword:
    def send_json(self, data):
        self.client.sendall((json.dumps(data) + "\n").encode())

    def __init__(self):
        # intialize the client by:
        # connecting to server, building gui, threading
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.client.connect((HOST, PORT))
            # TODO: a proper handshake
            self.send_json({"type": "CONNECT"})
        except:
            print("Unable to connect to server")
            return
        
        # game vars
        self.player_num = 0
        self.my_turn = False
        self.selected_row = None
        self.selected_col = None
        self.clues = [""] *SIZE
        #tkinter vars
        self.root = tk.Tk()
        self.root.title("Multiplayer Crossword!")
        self.grid_buttons = []
        self.build_grid()
        self.build_controls()
        # receive messages, ref:https://docs.python.org/3/library/threading.html
        self.running = True
        self.threader = threading.Thread(target=self.start_client)
        self.threader.start()

        self.root.protocol("WM_DELETE_WINDOW", self.on_close) # for when game window closes
        self.root.mainloop()

    def on_close(self):
        self.running = False
        try:
            if self.client:
                try:
                    # shutdown() affects all copies of the socket
                    self.client.shutdown(socket.SHUT_WR) # no more writes
                except :
                    pass
                self.client.close() # releases socket
                # socket may not be immediately reusable
        finally:
            self.root.destroy()

    def build_grid(self):
        """ 
        Function builds crossword grid GUI using Tkinter. 
        """
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
        self.update_clue()
        self.update_status() # update player status, current selected cell

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
            self.status_label.config(text = "Not your turn!")
            return

        # If users don't select any cells
        if self.selected_row is None or self.selected_col is None:
            return

        #Check if it's only 1 character and letter only
        letter = self.entry.get().upper()
        if len(letter) > 1 or not letter.isalpha() or letter == "":
            self.status_label.config(text="Invalid guess! Please type only 1 letter")
            return
        
        self.send_json({
            "type": "GUESS",
            "row": self.selected_row,
            "col": self.selected_col,
            "letter": letter
        })
        # clear input box after sending
        self.entry.delete(0, tk.END)

    def start_client(self):
        while True:
            try:
                # Await data broadcasted from the GameSession server thread
                data = self.client.recv(1024).decode()
                if not data:
                    print("[INFO] Server closed connection")
                    break

                # TCP STREAM BUFFERING FIX:
                # OS-level TCP buffers might combine multiple JSON packets into one string.
                # We split by the predefined '\n' boundary to process them sequentially.
                messages = data.split("\n")
                for msg_str in messages:
                    msg_str = msg_str.strip()
                    if not msg_str:
                        continue
                    msg = json.loads(msg_str)

                    #TODO : encapsulate this if loop logic to a seperate function
                    if msg["type"] == "WELCOME":
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
                        self.clues = msg["clues"]
                        self.update_clue()

                    elif msg["type"] == "UPDATE":
                        row= msg["row"]
                        col = msg["col"]
                        self.grid_buttons[row][col].config(text=msg["letter"])

                    elif msg["type"] == "TURN":
                        self.my_turn = (msg["player"] == self.player_num)
                        self.update_status()
                    
                    elif msg["type"] == "ERROR":
                        self.status_label.config(text=msg["message"])

                    elif msg["type"] == "DISCONNECTED":
                        print(msg['message'])
                        print("Opponent left. Closing game...")
                        self.running = False

                        # close the socket
                        try:
                            self.client.shutdown(socket.SHUT_RDWR)
                        except:
                            pass
                        self.client.close()
                        self.root.after(0, self.on_close)
                        return

                    elif msg["type"] == "GAME_END":
                        # TODO: Ipmrove the results popup window
                        print("Received Game over")
                        score1 = msg["scores"]["1"]
                        score2 = msg["scores"]["2"]
                        if score1 > score2:
                            winner = "Player 1"
                        elif score2 > score1:
                            winner = "Player 2"
                        else:
                            winner = "Tie"
                        
                        messagebox.showinfo("Game Over!", 
                            f"Scores:\nPlayer 1: {score1}\nPlayer 2: {score2}\nWinner: {winner}, congrats!"
                        )
                        self.root.destroy() 

            except Exception as e:
                if self.running:  # only report errors if we didn't intentionally close
                    print("Error:", e)
                break

        # Close the connect and destroy the window
        self.client.close()
        self.root.destroy() 

if __name__ == "__main__":
    Crossword()