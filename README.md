# **CMPT 371 A3 Socket Programming - Multiplayer Crossword `Name`**

**Course:** CMPT 371 \- Data Communications & Networking  
**Instructor:** Mirza Zaeem Baig  
**Semester:** Spring 2026  
<span style="color: purple;">**_RUBRIC NOTE: As per submission guidelines, only one group member will submit the link to this repository on Canvas._**

## **Group Members**

| Name               | Student ID | Email                 |
| :----------------- | :--------- | :-------------------- |
| Soumya Parmar      | 301558406  | spa222@sfu.ca         |
| Thu Hoai An Nguyen | 301563556  | hoai_an_nguyen@sfu.ca |

## **1\. Project Overview & Description**

This project is a real-time two-player Crossword game built using Python's Socket API (TCP) and Tkinter for the GUI. Players connect to a central server and they are matched into session to compete to fill a 5x5 crossword grid.

## **2\. System Limitations & Edge Cases**

As required by the project specifications, we have identified and handled (or defined) the following limitations and potential issues within our application scope:

- **Turn-based disconnect detection**
  - <span style="color: green;">_Solution:_</span> We set up a protocol once one of the client leaves, it will disconnect the game session since the session requires two people to play.
  - <span style="color: red;">_Limitation:_</span> Server reads only from the active player socket each loop, so if the idle player quits, server won't notice until it become their turn

- **Cell Validation**
  - <span style="color: green;">_Solution:_</span> We detect if users click a row or column or not to display a text to let them know that they should select a cell first before guessing.
  - <span style="color: red;">_Limitation:_</span> Server reads only from the active player socket each loop, so if the idle player quits, server won't notice until it become their turn. If a client disconnects, there's no rejoin, state restore or session resume.
- **Input Validation:**
  - <span style="color: green;">\_Solution</span>: We check if user enter any letters and it should be only 1 alphabet. </span>
  - <span style="color: red;">_Limitation:_</span> The client side uses a basic test with checking the length to be 1 with isalpha() for letter only or an empty string to avoid empty input. This is to prevent invalid input but the server assumes row, column and letter exists. Out-of range indices can crash the session thread.
- **Handling Multiple Clients Concurrently:**
  - <span style="color: green;">_Solution:_</span> We utilized Python's threading module. When two clients connect, they are popped from the matchmaking_queue and assigned to an isolated game_session daemon thread. This ensures concurrent games do not block the main server event listener.
  - <span style="color: red;">_Limitation:_</span> Thread creation is limited by system resources. An enterprise application would eventually need a thread pool or asynchronous I/O (like asyncio) to handle tens of thousands of connections.
- **TCP Stream Buffering:**
  - <span style="color: green;">_Solution:_</span> TCP is a continuous byte stream, meaning multiple JSON messages can be mashed together if sent rapidly. We implemented an application-layer fix by appending a newline \\n to all JSON payloads and splitting the buffer on the client/server side to process them atomically.

## **3\. Video Demo**

<span style="color: purple;">**_RUBRIC NOTE: Include a clickable link._**</span>  
Our 2-minute video demonstration covering connection establishment, data exchange, real-time gameplay, and process termination can be viewed below:  
[**▶️ Watch Project Demo on YouTube**](https://www.youtube.com/watch?v=dQw4w9WgXcQ)

## **4\. Prerequisites (Fresh Environment)**

To run this project, you need:

- **Python 3.10** or higher.
- No external pip installations are required (uses standard socket, threading, json, sys libraries).
- (Optional) VS Code or Terminal.

<span style="color: purple;">**_RUBRIC NOTE: No external libraries are required. Therefore, a requirements.txt file is not strictly necessary for dependency installation, though one might be included for environment completeness._**</span>

## **4\. Step-by-Step Run Guide**

<span style="color: purple;">**_RUBRIC NOTE: The grader must be able to copy-paste these commands._**</span>

### **Step 1: Start the Server**

Open your terminal and navigate to the project folder. The server binds to 127.0.0.1 on port 5050\.

```bash
python server.py
# Console output: "[STARTING] Server is listening on 127.0.0.1:5050"
```

### **Step 2: Connect Player 1**

Open a **new** terminal window (keep the server running). Run the client script to start the first client.

```bash
python client.py
# Console output: "Connected. Waiting for opponent..."
```

### **Step 3: Connect Player 2**

Open a **third** terminal window. Run the client script again to start the second client.

```bash
python client.py
# Console output: "Connected. Waiting for opponent..."
# Console output: "Match found! You are Player O."
```

### **Step 4: Gameplay**

1. Player 1 joins the lobby and waits for the 2nd player to join
2. Connect once 2 players join the matchmaking queue
3. Game starts
4. Player 1 selects a cell and types a letter
5. The server accepts or rejects the move
6. Board update broadcast and change to the opponent's turn. Player will get a point if they guess it correctly
7. Player 2 selects a cell and types a letter
8. The server accepts or rejects the move
9. Board update broadcast and change to the opponent's turn. Player will get a point if they guess it correctly
10. Once all words are solved, the game ends and selects the winner

## **5\. Technical Protocol Details (JSON over TCP)**

We designed a custom application-layer protocol for data exchange usin JSON over TCP:

- **Message Format:** `{"type": <string>, "payload": <data>}`
- **Handshake Phase:** \* Client sends: `{"type": "CONNECT"}`
  - Server responds: `{"type": "WELCOME", "player": 1}`
- **Gameplay Phase:**
  - Client sends to submit a letter for a specific cell: `{"type": "GUESS", "row": 1, "col": 1, "letter": A}`
  - Board gives clue: `{"type": "CLUES", "clues": [ACROSS: Not to. DOWN:...]}`
  - Game begins: `{"type": "START"}`
  - Indicate whose turn it is: `{"type": "TURN", "player": 1}`
  - Server broadcasts: `{"type": "UPDATE", "row":1, "col": 1, "letter": A}`
  - Send to client when a move is invalid: `{"type": "ERROR", "message": "Invalid move..."}`
  - Send when the grid is completed and correctly filled: `{"type": "GAME_END", "1": 3, "2": 5}`
  - When their opponent disconnects unexpectedly: `{"type": "DISCONNECTED", "message": "Opponent disconnected!"}`

## **6\. Academic Integrity & References**

<span style="color: purple;">**_RUBRIC NOTE: List all references used and help you got. Below is an example._**</span>

- **Code Origin:**
  - The socket boilerplate was adapted from the course tutorial "TCP Echo Server". The core multithreaded game logic, protocol, and state management were written by the group.
- **References:**
  - [Python Socket Programming HOWTO](https://docs.python.org/3/howto/sockets.html)
  - [Real Python: Intro to Python Threading](https://realpython.com/intro-to-python-threading/)
  - [Placing a Crossword Puzzle into a TKinder](https://stackoverflow.com/questions/16332224/placing-a-crossword-puzzle-into-a-tkiner-in-python-3-2)
  - [Threading in Python](https://docs.python.org/3/library/threading.html)
  - [python sockets multiple messages on same connection](https://stackoverflow.com/questions/42222425/python-sockets-multiple-messages-on-same-connection)
  - [How to Send and Receive JSON Data over IPv4 Sockets in Python](https://oneuptime.com/blog/post/2026-03-20-json-over-ipv4-sockets-python/view)
  - [Beej's Guide to Network Programming](https://beej.us/guide/bgnet3/html/#close-and-shutdownget-outta-my-face)
