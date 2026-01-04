# Exploding Kittens — Streamlit Terminal Edition
# FULL conversion of terminal-based game to Streamlit-safe terminal UI
# No input(), no print(), no screen clearing, no Streamlit session_state errors

import streamlit as st
import random
import json
import os

# ---------------------- CONFIG ----------------------
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
}
CAT_CARDS = ["Taco Cat", "Beard Cat", "Rainbow Ralphing Cat"]

# ---------------------- INIT STATE ----------------------
for key, default in {
    "log": [],
    "cmd": "",
    "deck": [],
    "discard": [],
    "player": [],
    "ai": [],
    "turn": "Player",
    "game_over": False,
    "winner": None,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default

# ---------------------- TERMINAL HELPERS ----------------------
def tprint(msg):
    st.session_state.log.append(msg)

# ---------------------- GAME SETUP ----------------------
def setup_game():
    deck = []
    for card, count in CARD_TYPES.items():
        if card not in ("Exploding Kitten", "Defuse"):
            deck += [card] * count
    random.shuffle(deck)

    st.session_state.player = [deck.pop() for _ in range(4)] + ["Defuse"]
    st.session_state.ai = [deck.pop() for _ in range(4)] + ["Defuse"]

    deck.append("Exploding Kitten")
    random.shuffle(deck)

    st.session_state.deck = deck
    st.session_state.discard = []
    st.session_state.turn = "Player"
    st.session_state.game_over = False
    st.session_state.winner = None
    st.session_state.log = []

    tprint("--- EXPLODING KITTENS TERMINAL MODE ---")
    tprint("Type: draw | play <card> | hand | help")

# ---------------------- COMMAND HANDLER ----------------------
def handle_command(cmd):
    if st.session_state.game_over:
        tprint("Game over. Refresh page to restart.")
        return

    tprint(f"> {cmd}")
    parts = cmd.lower().split(maxsplit=1)
    action = parts[0]
    arg = parts[1] if len(parts) > 1 else None

    if action == "help":
        tprint("Commands: draw, play <card>, hand")
        return

    if action == "hand":
        tprint("Your hand: " + ", ".join(st.session_state.player))
        return

    if action == "draw":
        draw_card("Player")
        ai_turn()
        return

    if action == "play" and arg:
        card = arg.title()
        if card not in st.session_state.player:
            tprint("You don't have that card")
            return
        play_card("Player", card)
        ai_turn()
        return

    tprint("Unknown command")

# ---------------------- GAME LOGIC ----------------------
def draw_card(who):
    if not st.session_state.deck:
        tprint("Deck empty")
        return

    card = st.session_state.deck.pop(0)
    tprint(f"{who} drew a card")

    if card == "Exploding Kitten":
        if "Defuse" in st.session_state.player:
            st.session_state.player.remove("Defuse")
            st.session_state.discard.append("Defuse")
            idx = random.randint(0, len(st.session_state.deck))
            st.session_state.deck.insert(idx, "Exploding Kitten")
            tprint("DEFUSED! Kitten returned to deck")
        else:
            tprint("BOOM! You exploded")
            st.session_state.game_over = True
            st.session_state.winner = "AI"
        return

    if who == "Player":
        st.session_state.player.append(card)
        tprint(f"You safely drew {card}")
    else:
        st.session_state.ai.append(card)


def play_card(who, card):
    st.session_state.player.remove(card)
    st.session_state.discard.append(card)
    tprint(f"You played {card}")

    if card == "Skip":
        tprint("Turn skipped")
    elif card == "Shuffle":
        random.shuffle(st.session_state.deck)
        tprint("Deck shuffled")
    elif card == "See the Future":
        tprint("Top cards: " + ", ".join(st.session_state.deck[:3]))


def ai_turn():
    if st.session_state.game_over:
        return

    tprint("--- AI TURN ---")
    if "Skip" in st.session_state.ai:
        st.session_state.ai.remove("Skip")
        tprint("AI used Skip")
        return
    draw_card("AI")

# ---------------------- UI ----------------------
st.markdown("""
<style>
.terminal {
    background:#0b0f14;
    color:#33ff33;
    font-family:monospace;
    padding:12px;
    height:420px;
    overflow-y:auto;
    border-radius:8px;
}
</style>
""", unsafe_allow_html=True)

st.title("💣 Exploding Kittens — Terminal")

if not st.session_state.deck:
    setup_game()

st.markdown(
    "<div class='terminal'>" + "<br>".join(st.session_state.log) + "</div>",
    unsafe_allow_html=True
)

st.text_input(
    "",
    key="cmd",
    placeholder="type command and press enter",
    on_change=lambda: (handle_command(st.session_state.cmd), st.session_state.__setitem__('cmd',''))
)
