# app.py
import streamlit as st
import random
import json
import os
from copy import deepcopy

# ---------------- CONFIG ----------------
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
STATS_FILE = "ek_stats.json"

def sort_hand(hand):
    order = [
        'Defuse', 'Nope', 'Skip', 'Attack', 'See the Future',
        'Favor', 'Shuffle', 'Peek', 'Unlucky',
        'Taco Cat', 'Beard Cat', 'Rainbow Ralphing Cat'
    ]
    return sorted(hand, key=lambda c: order.index(c) if c in order else 999)

# ---------------- SESSION STATE INIT ----------------
def init_session():
    if "game" not in st.session_state:
        st.session_state.game = {}
    g = st.session_state.game
    if not g:
        g.update({
            "deck": [],
            "discard": [],
            "players": {"Player": [], "AI": []},
            "turn": "Player",
            "attack_turns": 0,
            "history": [],
            "seen_top": [],
            "player_name": "Player",
            "game_over": False,
            "winner": None,
            "pending": None,   # dict describing pending action e.g. {'type':'defuse_prompt'}
            "stats": load_stats(),
        })

def load_stats():
    if os.path.exists(STATS_FILE):
        try:
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"games_played":0, "player_wins":0, "ai_wins":0}
    return {"games_played":0, "player_wins":0, "ai_wins":0}

def save_stats(s):
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(s, f)
    except Exception:
        pass

# ---------------- GAME BUILD ----------------
def new_game(name="Player"):
    g = st.session_state.game
    g["player_name"] = name.title() if name else "Player"
    # build deck excluding defuse and kittens for initial dealing
    pool = []
    for card, cnt in CARD_TYPES.items():
        if card not in ("Exploding Kitten", "Defuse"):
            pool += [card] * cnt
    random.shuffle(pool)
    # deal 4 + defuse
    g["players"]["Player"] = []
    g["players"]["AI"] = []
    for p in ["Player","AI"]:
        hand = []
        for _ in range(4):
            hand.append(pool.pop())
        hand.append("Defuse")
        random.shuffle(hand)
        g["players"][p] = hand
    # remaining deck: include remaining defuses and exploding kittens
    remaining = pool[:]
    kittens = 1  # 2-player -> 1 kitten (original game uses players-1)
    remaining += ["Exploding Kitten"] * kittens
    total_def = CARD_TYPES.get("Defuse", 0)
    remaining_def = max(0, total_def - 2)  # two defuses already given
    remaining += ["Defuse"] * remaining_def
    random.shuffle(remaining)
    g["deck"] = remaining
    g["discard"] = []
    g["turn"] = "Player"
    g["attack_turns"] = 0
    g["history"] = []
    g["seen_top"] = []
    g["game_over"] = False
    g["winner"] = None
    g["pending"] = None
    g["stats"] = load_stats()
    append_history(f"[GAME] Shuffling deck.... DONE!")
    append_history("--- WELCOME TO EXPLODING KITTENS (2 player) ---")
    append_history(f"Enter your player name: {g['player_name']}")
    append_history("")
    append_history_turn_header()

# ---------------- HISTORY / UI HELPERS ----------------
def append_history(msg):
    g = st.session_state.game
    g["history"].append(msg)

def append_history_turn_header():
    g = st.session_state.game
    header = f"---- {g['player_name'].upper()}'S TURN (1/1) ----"
    append_history(header)
    hand = sort_hand(g["players"]["Player"])
    append_history(f"Your hand: {', '.join(hand)}")
    append_history(f"DECK: {len(g['deck'])} cards remaining")
    append_history("[Type 'help' for all commands.]")
    append_history("> ")

# ---------------- CORE ACTIONS ----------------
def draw_card(player):
    g = st.session_state.game
    if g["game_over"]:
        return
    if not g["deck"]:
        if not g["discard"]:
            append_history("[GAME] Deck and discard pile are empty! Cannot continue.")
            g["game_over"] = True
            g["winner"] = "AI" if player == "Player" else "Player"
            return
        append_history("[GAME] Deck empty! Shuffling discard into deck.")
        g["deck"] = g["discard"][:]
        g["discard"] = []
        random.shuffle(g["deck"])
    # draw
    card = g["deck"].pop(0)
    append_history(f"[GAME] {display_name(player)} drew a card.")
    # handle Unlucky
    if card == "Unlucky":
        append_history(f"{display_name(player)} drew an Unlucky card! Must discard a card.")
        hand = g["players"][player]
        if not hand:
            append_history(f"{display_name(player)} has no cards to lose!")
            return
        if player == "AI":
            non_def = [c for c in hand if c != "Defuse"]
            preferred = [c for c in non_def if c not in ("Nope","Attack","Favor","Peek")]
            lost = random.choice(preferred) if preferred else (non_def[0] if non_def else hand[0])
            hand.remove(lost)
            g["discard"].append(lost)
            append_history(f"AI discarded {lost} due to Unlucky.")
        else:
            # auto-discard first non-defuse for UI simplicity
            non_def = [c for c in hand if c != "Defuse"]
            lost = non_def[0] if non_def else hand[0]
            hand.remove(lost)
            g["discard"].append(lost)
            append_history(f"You discarded {lost} due to Unlucky.")
        return
    if card == "Exploding Kitten":
        # if have defuse, prompt player or auto-defuse for AI
        if "Defuse" in g["players"][player]:
            if player == "Player":
                # present prompt in UI: pending defuse with returned kitten placement
                g["players"][player].remove("Defuse")
                g["discard"].append("Defuse")
                idx = random.randint(0, len(g["deck"]))
                g["deck"].insert(idx, "Exploding Kitten")
                g["seen_top"] = []
                append_history("Defuse used! Kitten returned to deck.")
            else:
                g["players"][player].remove("Defuse")
                g["discard"].append("Defuse")
                idx = random.randint(0, len(g["deck"]))
                g["deck"].insert(idx, "Exploding Kitten")
                g["seen_top"] = []
                append_history("AI used Defuse.")
            return
        else:
            append_history("BOOOOOOOM! EXPLODED.")
            g["game_over"] = True
            g["winner"] = "Player" if player == "AI" else "AI"
            return
    else:
        g["players"][player].append(card)
        if player == "Player":
            append_history(f"You drew safely: {card}")
        else:
            append_history(f"AI drew a card.")
        return

def display_name(key):
    g = st.session_state.game
    return g["player_name"] if key == "Player" else "AI"

def play_card_player(card):
    g = st.session_state.game
    # pre-checks
    if card not in g["players"]["Player"]:
        append_history(f"You don't have {card}.")
        return
    if card in CAT_CARDS:
        append_history(f"Error: {card} must be played as a pair or trio.")
        return
    if card == "Nope":
        append_history("Error: 'Nope' is reaction-only.")
        return
    if card == "Defuse":
        append_history("Error: 'Defuse' only used automatically on Exploding Kitten.")
        return
    # remove card and apply
    g["players"]["Player"].remove(card)
    g["discard"].append(card)
    append_history(f"You played {card}.")
    resolve_card_effect("Player", card)
    # after play if not game over, AI turn
    if not g["game_over"]:
        ai_turn()

def resolve_card_effect(player, card):
    g = st.session_state.game
    opponent = "AI" if player == "Player" else "Player"
    if card == "Peek":
        peek_hand = g["players"][opponent][:3]
        append_history(f"You peek at {display_name(opponent)}'s first 3 cards: {peek_hand}")
        return
    if card == "Skip":
        append_history("Turn skipped!")
        # skip next draw by switching turn; in this simplified UI, just set turn to AI
        g["turn"] = opponent
        return
    if card == "Attack":
        append_history("ATTACK! Opponent must take 2 turns.")
        g["attack_turns"] = 2
        g["turn"] = opponent
        return
    if card == "See the Future":
        top3 = g["deck"][:3]
        g["seen_top"] = top3.copy()
        append_history(f"THE FUTURE: {top3}")
        return
    if card == "Favor":
        if g["players"][opponent]:
            if opponent == "AI":
                ai_hand_non = [c for c in g["players"]["AI"] if c not in ("Defuse","Nope")]
                chosen = random.choice(ai_hand_non) if ai_hand_non else random.choice(g["players"]["AI"])
                g["players"]["AI"].remove(chosen)
                g["players"]["Player"].append(chosen)
                append_history(f"AI gives you {chosen}.")
            else:
                # not used
                pass
        return
    if card == "Shuffle":
        random.shuffle(g["deck"])
        append_history("Deck shuffled.")
        return
    # default: no effect
    return

def play_pair_player(cat):
    g = st.session_state.game
    if g["players"]["Player"].count(cat) < 2:
        append_history(f"You need two {cat}s.")
        return
    for _ in range(2):
        g["players"]["Player"].remove(cat)
        g["discard"].append(cat)
    # steal a random AI card
    if g["players"]["AI"]:
        stolen = random.choice(g["players"]["AI"])
        g["players"]["AI"].remove(stolen)
        g["players"]["Player"].append(stolen)
        append_history(f"You played pair of {cat}s and stole {stolen} from AI.")
    else:
        append_history("AI has no cards to steal.")
    ai_turn()

def play_trio_player(cat, requested):
    g = st.session_state.game
    if g["players"]["Player"].count(cat) < 3:
        append_history(f"You need three {cat}s.")
        return
    for _ in range(3):
        g["players"]["Player"].remove(cat)
        g["discard"].append(cat)
    found = None
    for c in g["players"]["AI"]:
        if requested.lower() in c.lower():
            found = c
            break
    if found:
        g["players"]["AI"].remove(found)
        g["players"]["Player"].append(found)
        append_history(f"AI had {found}. You take it.")
    else:
        append_history("AI does not have that card.")
    ai_turn()

# ---------------- AI logic (simplified but functional) ----------------
def ai_turn():
    g = st.session_state.game
    if g["game_over"]:
        return
    append_history("[AI] is thinking...")
    hand = g["players"]["AI"]
    # if kitten suspected in top3 and have safety card, use it
    top3 = g["seen_top"] if g["seen_top"] else g["deck"][:3]
    prob_kitten = "Exploding Kitten" in top3
    for danger in ("Skip","Shuffle","Attack"):
        if prob_kitten and danger in hand:
            hand.remove(danger)
            g["discard"].append(danger)
            append_history(f"AI uses {danger} to avoid danger!")
            if danger == "Skip":
                return
            if danger == "Shuffle":
                random.shuffle(g["deck"])
                return
            if danger == "Attack":
                g["attack_turns"] = 2
                return
    # sometimes see the future
    if "See the Future" in hand and not g["seen_top"] and random.random() < 0.6:
        hand.remove("See the Future")
        g["discard"].append("See the Future")
        g["seen_top"] = g["deck"][:3]
        append_history(f"AI views top cards: {g['seen_top']}")
        return
    # try pair steal if possible
    for cat in CAT_CARDS:
        if hand.count(cat) >= 2:
            for _ in range(2):
                hand.remove(cat)
                g["discard"].append(cat)
            # steal priority
            priority = ["Defuse","Nope","Attack","Favor","Peek"]
            stolen = None
            for p in priority:
                if p in g["players"]["Player"]:
                    g["players"]["Player"].remove(p)
                    hand.append(p)
                    stolen = p
                    break
            if not stolen and g["players"]["Player"]:
                stolen = g["players"]["Player"].pop(0)
                hand.append(stolen)
            append_history(f"AI played pair of {cat}s and stole {stolen}.")
            return
    # Favor
    if "Favor" in hand and (len(hand) < 8 or random.random() < 0.2):
        hand.remove("Favor")
        g["discard"].append("Favor")
        if g["players"]["Player"]:
            nonp = [c for c in g["players"]["Player"] if c not in ("Defuse","Nope")]
            stolen = random.choice(nonp) if nonp else g["players"]["Player"].pop(0)
            g["players"]["Player"].remove(stolen)
            hand.append(stolen)
            append_history(f"AI played Favor and took your {stolen}.")
            return
    # Shuffle if deck low
    if "Shuffle" in hand and len(g["deck"]) < 5:
        hand.remove("Shuffle")
        g["discard"].append("Shuffle")
        random.shuffle(g["deck"])
        append_history("AI shuffled the deck.")
        return
    # else draw
    draw_card("AI")

# ---------------- UI ----------------
st.set_page_config(page_title="Exploding Kittens — Cards", layout="wide")
st.title("Exploding Kittens — Card Mode")

init_session()
g = st.session_state.game

# Start / reset controls
col_top = st.columns([1,3,1])
with col_top[0]:
    if st.button("New Game"):
        name = st.text_input("Player name", value=g.get("player_name","Player"), key="newname")
        # If user entered a name in text_input above, use that; else use existing
        new_game(name if name else g.get("player_name","Player"))
        st.experimental_rerun()
with col_top[1]:
    st.subheader(f"Player: {g['player_name']}")
with col_top[2]:
    stats = g["stats"]
    st.write(f"Games: {stats.get('games_played',0)} | Wins: {stats.get('player_wins',0)} / AI: {stats.get('ai_wins',0)}")

# Main layout: left = player's hand, center = board & deck, right = AI & history
left, center, right = st.columns([3,2,2])

with left:
    st.subheader("Your hand (click to play)")
    hand = sort_hand(g["players"]["Player"])
    # display clickable cards
    rows = []
    cols = st.columns(4)
    for i, card in enumerate(hand):
        with cols[i % 4]:
            if st.button(card, key=f"play_{i}"):
                # handle playing card (non-cat)
                if card in CAT_CARDS:
                    append_history(f"You clicked {card}. Use Pair/Trio controls to play cat cards.")
                else:
                    play_card_player(card)
                    st.experimental_rerun()
    st.markdown("---")
    st.subheader("Cat combos")
    cats_available_pair = [c for c in CAT_CARDS if g["players"]["Player"].count(c) >= 2]
    cats_available_trio = [c for c in CAT_CARDS if g["players"]["Player"].count(c) >= 3]
    if cats_available_pair:
        st.write("Pairs available:")
        for c in cats_available_pair:
            if st.button(f"Play pair {c}", key=f"pair_{c}"):
                play_pair_player(c)
                st.experimental_rerun()
    else:
        st.write("No pairs available.")
    if cats_available_trio:
        st.write("Trios available:")
        for c in cats_available_trio:
            req = st.text_input(f"Request card for trio {c}", key=f"trio_req_{c}")
            if st.button(f"Play trio {c}", key=f"trio_{c}"):
                play_trio_player(c, req.strip())
                st.experimental_rerun()
    else:
        st.write("No trios available.")

with center:
    st.subheader("Table")
    st.write(f"Deck: {len(g['deck'])} | Discard: {len(g['discard'])}")
    if st.button("Draw a card"):
        draw_card("Player")
        st.experimental_rerun()
    st.markdown("---")
    st.subheader("Seen top cards")
    st.write(g["seen_top"] if g["seen_top"] else "None")
    st.markdown("---")
    st.subheader("Actions")
    if st.button("Show hand (log)"):
        append_history(f"Hand: {', '.join(sort_hand(g['players']['Player']))}")
    if st.button("AI turn"):
        ai_turn()
        st.experimental_rerun()

with right:
    st.subheader("Opponent")
    st.write(f"AI has {len(g['players']['AI'])} cards (hidden).")
    st.write(f"AI Defuse: {g['players']['AI'].count('Defuse')}")
    st.markdown("---")
    st.subheader("Game log")
    # show last 25 messages
    for entry in g["history"][-40:]:
        st.markdown(entry)

# Game over handling
if g["game_over"]:
    st.success(f"Game over — {g['winner']} wins!")
    # update stats once
    if not st.session_state.get("counted_end", False):
        s = g["stats"]
        s["games_played"] = s.get("games_played",0) + 1
        if g["winner"] == "Player":
            s["player_wins"] = s.get("player_wins",0) + 1
        else:
            s["ai_wins"] = s.get("ai_wins",0) + 1
        save_stats(s)
        st.session_state.game["stats"] = s
        st.session_state["counted_end"] = True
    if st.button("Restart game"):
        new_game(g["player_name"])
        st.experimental_rerun()
