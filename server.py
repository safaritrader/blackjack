import random
import time
import threading
from flask import Flask, render_template
from flask_socketio import SocketIO, emit, join_room

app = Flask(__name__)
app.config["SECRET_KEY"] = "CHANGE_THIS_SECRET"
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet")

MAX_PLAYERS = 5
STARTING_CHIPS = 1000

# ------------------ GAME LOGIC ------------------
def player_turn_timer(table_id):
    table = tables[table_id]

    while table["state"] == "playing" and table["current_turn"] < len(table["player_order"]):
        while table["current_turn"] < len(table["player_order"]):
            pid = table["player_order"][table["current_turn"]]
            player = table["players"][pid]
            if player["busted"] or table["bets"].get(pid, 0) == 0:
                table["current_turn"] += 1
            else:
                break

        if table["current_turn"] >= len(table["player_order"]):
            break
        pid = table["player_order"][table["current_turn"]]
        player = table["players"][pid]

        if player["stood"] or player["busted"]:
            table["current_turn"] += 1
            continue

        seconds = 10
        player["acted"] = False
        hand = player["hands"][player["active_hand"]]
        if is_blackjack(hand):
            player["stood"] = True
            player["acted"] = True
            socketio.emit(
                "system_message",
                {"msg": f"{pid} has blackjack! Skipping turn."},
                room=table_id
            )
            table["current_turn"] += 1
            continue
        while seconds > 0:
            socketio.emit(
                "player_timer",
                {"player": pid, "seconds": seconds},
                room=table_id
            )
            socketio.sleep(1)

            if player["acted"] and not player["busted"] and not player["stood"]:
                player["acted"] = False
                seconds = 10
                continue

            if player["stood"] or player["busted"]:
                break

            seconds -= 1

        if not player["stood"] and not player["busted"]:
            player["stood"] = True
            socketio.emit(
                "system_message",
                {"msg": f"{pid} auto-stands"},
                room=table_id
            )

        table["current_turn"] += 1

    active_players_exist = any(
    not p["busted"] for p in table["players"].values() if table["bets"].get(p["name"]))

    if active_players_exist:
        dealer_play(table)
    settle_round_by_hands(table)
    socketio.start_background_task(restart_round, table_id)



def is_soft(hand):
    total = sum(card_value(c) for c in hand)
    aces = sum(1 for c in hand if c.startswith("1"))
    return aces > 0 and total + 10 <= 21

def create_deck():
    deck = []
    for suit in ["H", "D", "C", "S"]:
        for value in range(1, 14):
            deck.append(f"{value}{suit}")
    random.shuffle(deck)
    return deck

def card_value(card):
    value = int(card[:-1])
    return 10 if value > 10 else value

def hand_value(hand):
    total = sum(card_value(c) for c in hand)
    aces = sum(1 for c in hand if c.startswith("1"))
    while total <= 11 and aces:
        total += 10
        aces -= 1
    return total

def is_blackjack(hand):
    return len(hand) == 2 and hand_value(hand) == 21

# ------------------ DATA STRUCTURES ------------------

tables = {}

def create_table(table_id):
    tables[table_id] = {
        "players": {},
        "player_order": [],
        "current_turn": 0,
        "dealer": [],
        "deck": [],
        "state": "waiting",
        "bets": {},
    }

# ------------------ GAME FLOW ------------------

def start_round(table_id):
    table = tables.get(table_id)
    if not table:
        return

    table["state"] = "betting"
    table["bets"] = {}
    table["dealer"] = []
    table["deck"] = create_deck()
    table["current_turn"] = 0

    for i in range(10, 0, -1):
        socketio.emit("betting_timer", {"seconds": i}, room=table_id)
        socketio.sleep(1)
        if not table["players"]:
            table["state"] = "waiting"
            socketio.emit("table_state", serialize_table(table), room=table_id)
            return

    if not table["bets"]:
        table["state"] = "waiting"
        socketio.emit(
            "system_message",
            {"msg": "No bets placed. Waiting for players..."},
            room=table_id
        )
        socketio.start_background_task(start_round, table_id)
        return
    
    to_remove = []
    for pid, player in list(table["players"].items()):
        if pid not in table["bets"]:
            player["missed_bets"] += 1
            if player["missed_bets"] >= 3:
                to_remove.append(pid)

    for pid in to_remove:
        table["player_order"].remove(pid)
        del table["players"][pid]
        socketio.emit("system_message", {"msg": f"{pid} removed for inactivity"}, room=table_id)

    deal_cards(table_id)

def deal_cards(table_id):
    table = tables[table_id]
    if not table or not table["bets"]:
        table["state"] = "waiting"
        return
    table["state"] = "playing"

    table["current_turn"] = 0

    for pid in table["player_order"]:
        if pid in table["bets"]:
            hand = [table["deck"].pop(), table["deck"].pop()]
            table["players"][pid]["hands"] = [hand]
            table["players"][pid]["active_hand"] = 0
            table["players"][pid]["stood"] = False
            table["players"][pid]["busted"] = False
        else:
            table["players"][pid]["hands"] = []
            table["players"][pid]["stood"] = True
            table["players"][pid]["busted"] = True

    table["dealer"] = [table["deck"].pop(), table["deck"].pop()]

    socketio.emit("table_state", serialize_table(table), room=table_id)
    socketio.start_background_task(player_turn_timer, table_id)



def dealer_play(table):
    while True:
        total = hand_value(table["dealer"])
        soft = is_soft(table["dealer"])

        if total < 17 or (total == 17 and soft):
            table["dealer"].append(table["deck"].pop())

            socketio.emit(
                "table_state",
                serialize_table(table),
                room=table_id_from_table(table)
            )

            socketio.sleep(0.6)
        else:
            break


# ------------------ SOCKET EVENTS ------------------

@socketio.on("join")
def join(data):
    table_id = data["table"]
    pid = data["player"]

    if table_id not in tables:
        create_table(table_id)

    table = tables[table_id]

    if len(table["players"]) >= MAX_PLAYERS:
        emit("join_error", {"msg": "Table is full, cannot join."})
        return

    if pid not in table["players"]:
        table["players"][pid] = {
            "name": pid,
            "hands": [],
            "active_hand": 0,
            "chips": STARTING_CHIPS,
            "stood": False,
            "busted": False,
            "missed_bets": 0,
            "acted": False
        }
        table["player_order"].append(pid)

    join_room(table_id)

    socketio.emit("table_state", serialize_table(table), room=table_id)

    if table["state"] == "waiting" and table["players"]:
        socketio.start_background_task(start_round, table_id)


@socketio.on("bet")
def bet(data):
    if data['table'] not in tables:
        return
    table = tables[data["table"]]
    pid = data["player"]
    amount = int(data["amount"])
    if not table:
        return
    if table["state"] != "betting":
        return
    if amount <= 0:
        return
    if pid not in table["players"]:
        print(f"[WARN] Bet from invalid player {pid}")
        return
    if table["players"][pid]["chips"] >= amount:
        if pid not in table["bets"]:
            table["bets"][pid] = amount
            table["players"][pid]["chips"] -= amount
            table["players"][pid]["missed_bets"] = 0
        else:
            table["bets"][pid] += amount
            table["players"][pid]["chips"] -= amount
            table["players"][pid]["missed_bets"] = 0
        socketio.emit(
            "table_state",
            serialize_table(table),
            room=data["table"]
        )

def restart_round(table_id):
    socketio.sleep(5)
    table = tables[table_id]
    for pid in table["players"]:
        table["players"][pid]["hands"] = []
        table["players"][pid]["active_hand"] = 0
        table["players"][pid]["stood"] = False
        table["players"][pid]["busted"] = False
    table["dealer"] = []
    table["state"] = "waiting"
    socketio.emit(
            "table_state",
            serialize_table(table),
            room=table_id
        )
    socketio.start_background_task(start_round, table_id)

def serialize_table(table):
    return {
        "players": table["players"],
        "dealer": table["dealer"],
        "current_turn": table["current_turn"],
        "player_order": table["player_order"],
        "state": table["state"]
    }
def table_id_from_table(table):
    for tid, t in tables.items():
        if t is table:
            return tid

def settle_round_by_hands(table):
    if not any(table["bets"].values()):
        table["state"] = "round_end"
        socketio.emit(
            "round_end",
            {"dealer": table["dealer"], "dealer_total": 0, "results": {}},
            room=table_id_from_table(table)
        )
        return
    dealer_total = hand_value(table["dealer"])
    dealer_blackjack = is_blackjack(table["dealer"])
    dealer_bust = dealer_total > 21

    results = {}

    for pid in table["player_order"]:
        if pid not in table["bets"]:
            continue

        player = table["players"][pid]
        base_bet = table["bets"][pid]
        results[pid] = []

        for hand in player["hands"]:
            total = hand_value(hand)
            blackjack = is_blackjack(hand)

            if blackjack and not dealer_blackjack:
                win = int(base_bet * 1.5)
            elif dealer_blackjack and not blackjack:
                win = -base_bet
            elif blackjack and dealer_blackjack:
                win = 0
            elif total > 21:
                win = -base_bet
            elif dealer_bust or total > dealer_total:
                win = base_bet
            elif total == dealer_total:
                win = 0
            else:
                win = -base_bet

            player["chips"] += base_bet + win
            results[pid].append({
                "hand": hand,
                "total": total,
                "win": win
            })

    table["state"] = "round_end"

    socketio.emit("round_end", {
        "dealer": table["dealer"],
        "dealer_total": dealer_total,
        "results": results
    }, room=table_id_from_table(table))

def next_hand_or_player(table):
    pid = table["player_order"][table["current_turn"]]
    player = table["players"][pid]

    if player["active_hand"] + 1 < len(player["hands"]):
        player["active_hand"] += 1
    else:
        player["stood"] = True

@socketio.on("action")
def action(data):
    table = tables.get(data["table"])
    if not table or table["state"] != "playing":
        return

    if table["current_turn"] >= len(table["player_order"]):
        return

    while table["current_turn"] < len(table["player_order"]):
        pid = table["player_order"][table["current_turn"]]
        player = table["players"][pid]
        if player["busted"] or table["bets"].get(pid, 0) == 0:
            table["current_turn"] += 1
        else:
            break

    if table["current_turn"] >= len(table["player_order"]):
        return

    pid = table["player_order"][table["current_turn"]]
    player = table["players"][pid]

    if data["player"] != pid:
        return

    if not player["hands"]:
        return
    hand = player["hands"][player["active_hand"]]

    if data["action"] == "hit":
        hand.append(table["deck"].pop())
        if hand_value(hand) > 21:
            next_hand_or_player(table)
        else:
            player["acted"] = True

    elif data["action"] == "stand":
        next_hand_or_player(table)

    elif data["action"] == "split":
        if len(hand) == 2 and card_value(hand[0]) == card_value(hand[1]):
            bet = table["bets"][pid]
            if player["chips"] >= bet:
                player["chips"] -= bet
                table["bets"][pid] += bet
                player["hands"] = [
                    [hand[0], table["deck"].pop()],
                    [hand[1], table["deck"].pop()]
                ]
                player["active_hand"] = 0
                player["acted"] = True

    elif data["action"] == "double":
        if len(hand) == 2:
            bet = table["bets"][pid]
            if player["chips"] >= bet:
                player["chips"] -= bet
                table["bets"][pid] += bet
                hand.append(table["deck"].pop())
                next_hand_or_player(table)

    elif data["action"] == "error_loading_cards":
        print(f'Error Loading Card for {pid}')
        bet_amount = table["bets"].get(pid, 0)
        if bet_amount > 0:
            table["players"][pid]["chips"] += bet_amount
            del table["bets"][pid]
            socketio.emit(
                "system_message",
                {"msg": f"{pid} had a card loading error. Bet refunded and removed from round."},
                room=data["table"]
            )
        player["busted"] = True
        player["stood"] = True

    socketio.emit("table_state", serialize_table(table), room=data["table"])


@app.route("/")
def index():
    return render_template("index.html")

if __name__ == "__main__":
    socketio.run(app, debug=True)
