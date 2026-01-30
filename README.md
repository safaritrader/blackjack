<div align="center">
  <h1>🃏 Multiplayer Blackjack (Flask + Socket.IO)</h1>
  <a href="https://github.com/safaritrader/blackjack" target="_blank">
    <img width="1000" src="https://github.com/safaritrader/blackjack/blob/main/blackjack.jpg">
  </a>
</div>

[![ License](https://img.shields.io/badge/BlackJack-1.0.0-blue&?color=red)](https://github.com/safaritrader/blackjack)

A real-time, multiplayer Blackjack game built with **Python (Flask + Flask-SocketIO)** on the backend and **HTML5 Canvas + JavaScript** on the frontend.  
Players join a shared table, place bets, take turns with timers, and play against an automated dealer following standard Blackjack rules.

---

## 🚀 Features

- 🎮 Multiplayer gameplay (up to 5 players per table)
- ⏱ Turn-based system with countdown timers
- 💬 Real-time updates via WebSockets
- 💰 Betting system with chips
- 🂡 Full Blackjack ruleset  
  - Hit / Stand  
  - Split  
  - Double Down  
  - Blackjack payouts (3:2)  
  - Dealer hits on soft 17
- 🖥 Canvas-based UI
- 🔊 Sound effects
- 🔄 Automatic round restart
- 🧹 Inactive player removal

---

## 🧠 Game Architecture

### Backend (Python)
- Flask web server
- Flask-SocketIO for real-time communication
- Event-driven game loop
- Server-authoritative game logic
- Background tasks for:
  - Betting timer
  - Player turn timer
  - Dealer play
  - Round settlement

### Frontend (JavaScript)
- HTML5 Canvas rendering
- WebSocket communication (Socket.IO client)
- Asset preloading (cards + sounds)
- Responsive scaling
- Client-side animations & sounds


---

## ⚙️ Installation & Setup

### 1️⃣ Clone the repository
```bash
git clone https://github.com/yourusername/blackjack-multiplayer.git
cd blackjack-multiplayer
```
### 2️⃣ Create a virtual environment (recommended)
```python
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
```
### 3️⃣ Install required Python packages
```python
pip install flask flask-socketio eventlet
```

Package	Purpose
Flask	Web server and routing
Flask-SocketIO	Real-time WebSocket communication
eventlet	Asynchronous networking (required by Socket.IO async mode)

### ▶️ Running the Game

```python
python server.py
```

Then open your browser and visit:

http://localhost:5000

Each browser tab represents a new player.


### 🎲 Game Rules Summary

- Each player starts with 1000 chips

- Betting phase lasts 10 seconds

- Each player has 10 seconds per turn

- Players who miss betting 3 times are removed

Dealer:
 - Hits until 17
 - Hits on soft 17
 - Blackjack payout: 3:2
 - Split and Double Down supported

### 🔁 Game Flow
 - Players join a table
 - Betting phase begins
 - Cards are dealt
 - Players take turns
 - Dealer plays
 - Bets are settled
 - Round ends and restarts automatically

### 🛠 Technical Highlights

 - Server-authoritative logic (prevents cheating)

 - Background threads for timers and dealer actions

 - State synchronization across all players

 - Graceful handling of asset loading failures

 - Automatic bet refunds on client-side asset errors

### 🔒 Security Notes

 - Change SECRET_KEY before production
 - This project is designed for learning and demos, not real money
 - No authentication system included

### 🧪 Known Limitations

 - No persistence (game resets on server restart)

 - Single table (table1) by default

 - No AI players

 - No reconnection recovery

### 📈 Future Improvements

 - Multiple tables / lobbies

 - Player authentication

 - Persistent player stats

 - Mobile-friendly UI

 - Chat system

 - Spectator mode

### 📜 License

This project is open-source and intended for educational purposes.
