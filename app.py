import streamlit as st
import random
import json
import os
from collections import deque

# ================= TERMINAL IO ================= #

class TerminalIO:
    def __init__(self):
        if "terminal" not in st.session_state:
            st.session_state.terminal = deque(maxlen=1200)
        if "pending_input" not in st.session_state:
            st.session_state.pending_input = None

    def write(self, text=""):
        st.session_state.terminal.append(text)

    def clear(self):
        st.session_state.terminal.clear()

    def consume_input(self):
        value = st.session_state.pending_input
        st.session_state.pending_input = None
        return value


# ================= GAME DATA ================= #

CARD_TYPES = {
    "Exploding Kitten": 1,
    "Defuse": 3,
    "Nope": 6,
    "Taco Cat": 7,
    "Beard Cat": 7,
    "Rainbow Ralphing Cat": 7,
    "Skip": 4,
    "Attack": 4,
    "See the Future": 4,
    "Favor": 3,
    "Shuffle": 3,
    "Peek": 1,
    "Unlucky": 2,
}

CAT_CARDS = ["Taco Cat", "Beard Cat", "Rainbow Ralphing Cat"]

def sort_hand(hand):
    order = [
        'Defuse', 'Nope', 'Skip', 'Attack', 'See the Future',
        'Favor', 'Shuffle', 'Peek', 'Unlucky',
        'Taco Cat', 'Beard Cat', 'Rainbow Ralphing Cat'
    ]
    return sorted(hand, key=lambda c: order.index(c) if c in order else 99)


# ================= GAME ENGINE ================= #

class ExplodingKittensGame:
    STATS_FILE = "ek_stats.json"

    def __init__(self, io):
        self.io = io
        self.reset_all()

    # ---------- persistence ----------

    def load_stats(self):
        if os.path.exists(self.STATS_FILE):
            with open(self.STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        return {"games_played": 0, "player_wins": 0, "ai_wins": 0}

    def save_stats(self, stats):
        with open(self.STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(stats, f)

    # ---------- setup ----------

    def reset_all(self):
        self.deck = []
        self.discard_pile = []
        self.players = {"Player": [], "AI": []}
        self.turn = "Player"
        self.attack_turns = 0
        self.game_over = False
        self.winner = None
        self.history = []
        self.seen_top_cards = []
        self.player_name = "Player"
        self.awaiting = "name"
        self.setup_game()

    def setup_game(self):
        temp = []
        for card, count in CARD_TYPES.items():
            if card not in ("Exploding Kitten", "Defuse"):
                temp += [card] * count
        random.shuffle(temp)

        for p in self.players:
            self.players[p] = [temp.pop() for _ in range(4)] + ["Defuse"]

        self.deck = temp + ["Exploding Kitten"]
        random.shuffle(self.deck)

        self.io.clear()
        self.io.write("💣 EXPLODING KITTENS — STREAMLIT TERMINAL")
        self.io.write("Enter your name:")

    # ---------- helpers ----------

    def log(self, msg):
        self.io.write(f"[GAME] {msg}")

    # ---------- command dispatcher ----------

    def step(self, cmd):
        if self.game_over:
            self.log("Game over. Refresh to restart.")
            return

        if self.awaiting == "name":
            if cmd:
                self.player_name = cmd.title()
                self.awaiting = "turn"
                self.log(f"Welcome, {self.player_name}")
            return

        if self.turn == "Player":
            self.player_command(cmd)

    # ---------- player logic ----------

    def player_command(self, cmd):
        self.log(f"> {cmd}")
        parts = cmd.lower().split(maxsplit=1)
        action = parts[0]
        arg = parts[1] if len(parts) > 1 else ""

        if action == "help":
            self.log("Commands: draw | play <card> | hand | pair <cat> | trio <cat>")
            return

        if action == "hand":
            self.log("Your hand:")
            for c in sort_hand(self.players["Player"]):
                self.io.write(f" - {c}")
            return

        if action == "draw":
            self.draw("Player")
            self.ai_turn()
            return

        if action == "play":
            card = arg.title()
            if card not in self.players["Player"]:
                self.log("You don't have that card.")
                return
            self.players["Player"].remove(card)
            self.resolve_card("Player", card)
            self.ai_turn()
            return

        self.log("Unknown command.")

    # ---------- card effects ----------

    def draw(self, who):
        card = self.deck.pop(0)
        self.log(f"{who} drew a card")

        if card == "Exploding Kitten":
            if "Defuse" in self.players[who]:
                self.players[who].remove("Defuse")
                self.discard_pile.append("Defuse")
                self.deck.insert(random.randint(0, len(self.deck)), "Exploding Kitten")
                self.log("DEFUSED!")
            else:
                self.log(f"{who} EXPLODED!")
                self.game_over = True
                self.winner = "AI" if who == "Player" else "Player"
        else:
            self.players[who].append(card)

    def resolve_card(self, player, card):
        self.discard_pile.append(card)
        self.log(f"{player} played {card}")

        if card == "Skip":
            self.log("Turn skipped.")
            return

        if card == "Attack":
            self.attack_turns = 2
            return

        if card == "Shuffle":
            random.shuffle(self.deck)
            self.log("Deck shuffled.")
            return

        if card == "See the Future":
            self.log(f"Future: {self.deck[:3]}")
            return

        if card == "Favor":
            if self.players["AI"]:
                stolen = random.choice(self.players["AI"])
                self.players["AI"].remove(stolen)
                self.players["Player"].append(stolen)
                self.log(f"AI gave you {stolen}")

    # ---------- AI ----------

    def ai_turn(self):
        if self.game_over:
            return
        self.log("--- AI TURN ---")
        self.draw("AI")


# ================= STREAMLIT UI ================= #

st.set_page_config(page_title="Exploding Kittens", layout="centered")

st.markdown("""
<style>
.terminal {
    background: black;
    color: #00ff66;
    font-family: monospace;
    padding: 15px;
    height: 480px;
    overflow-y: auto;
    border-radius: 8px;
}
</style>
""", unsafe_allow_html=True)

io = TerminalIO()

if "game" not in st.session_state:
    st.session_state.game = ExplodingKittensGame(io)

game = st.session_state.game

st.title("💣 Exploding Kittens")

terminal_text = "\n".join(st.session_state.terminal)
st.markdown(f"<div class='terminal'>{terminal_text}</div>", unsafe_allow_html=True)

cmd = st.text_input(
    "",
    key="cmd",
    placeholder="type command and press enter",
    label_visibility="collapsed"
)

if cmd:
    st.session_state.pending_input = cmd
    st.session_state.cmd = ""
    game.step(cmd)
    st.rerun()
